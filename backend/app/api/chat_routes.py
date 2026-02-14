import asyncio
import json
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import User, Conversation, Message, Processo
from app.schemas.chat import (
    ConversationCreate, ConversationUpdate, ConversationResponse, ConversationListResponse,
    MessageCreate, MessageResponse, ChatResponse, MessageHistoryResponse, SourceInfo
)
from app.api.deps import get_current_user, get_processo_with_access
from app.services.rag_engine import chat as rag_chat, chat_stream as rag_chat_stream

router = APIRouter(prefix="/chat", tags=["chat"])

settings = get_settings()


async def _generate_title(conversation_id: UUID, content: str):
    """Generate conversation title in background (separate DB session)."""
    from app.core.database import AsyncSessionLocal
    from openai import AsyncOpenAI

    _openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                return

            if conversation.titulo and conversation.titulo != "Nova conversa":
                return

            title_resp = await _openai.chat.completions.create(
                model=settings.PROCESSING_MODEL,
                messages=[
                    {"role": "system", "content": "Gere um titulo curto (maximo 6 palavras) em portugues para uma conversa que comeca com a seguinte pergunta. Responda APENAS com o titulo, sem aspas ou pontuacao final."},
                    {"role": "user", "content": content},
                ],
                temperature=1,
                max_completion_tokens=30,
            )
            raw_title = title_resp.choices[0].message.content
            if isinstance(raw_title, list):
                raw_title = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p)
                    for p in raw_title
                )
            conversation.titulo = (raw_title or content[:60]).strip()
            await db.commit()
        except Exception:
            conversation.titulo = content[:60]
            try:
                await db.commit()
            except Exception:
                pass


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    processo_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Conversation).where(Conversation.user_id == current_user.id)

    if processo_id:
        # Verify access to processo
        await get_processo_with_access(processo_id, db, current_user)
        query = query.where(Conversation.processo_id == processo_id)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get conversations with message count
    result = await db.execute(
        query.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit)
    )
    conversations = result.scalars().all()

    # Build responses with message counts
    responses = []
    for conv in conversations:
        msg_count = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        responses.append(ConversationResponse(
            id=conv.id,
            processo_id=conv.processo_id,
            user_id=conv.user_id,
            canal=conv.canal,
            titulo=conv.titulo,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count.scalar() or 0,
        ))

    return ConversationListResponse(conversations=responses, total=total)


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify access to processo
    await get_processo_with_access(request.processo_id, db, current_user)

    conversation = Conversation(
        processo_id=request.processo_id,
        user_id=current_user.id,
        titulo=request.titulo,
        canal="web",
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    return ConversationResponse(
        id=conversation.id,
        processo_id=conversation.processo_id,
        user_id=conversation.user_id,
        canal=conversation.canal,
        titulo=conversation.titulo,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@router.get("/conversations/{conversation_id}", response_model=MessageHistoryResponse)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")

    # Verify access
    await get_processo_with_access(conversation.processo_id, db, current_user)

    # Get messages
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    msg_count = len(messages)

    return MessageHistoryResponse(
        messages=[MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            tokens_input=m.tokens_input,
            tokens_output=m.tokens_output,
            custo_estimado=m.custo_estimado,
            created_at=m.created_at,
            sources=m.metadata_.get("sources", []) if m.metadata_ else [],
        ) for m in messages],
        conversation=ConversationResponse(
            id=conversation.id,
            processo_id=conversation.processo_id,
            user_id=conversation.user_id,
            canal=conversation.canal,
            titulo=conversation.titulo,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=msg_count,
        ),
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")

    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissao")

    conversation.titulo = payload.titulo
    await db.commit()
    await db.refresh(conversation)

    msg_count = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conversation.id)
    )

    return ConversationResponse(
        id=conversation.id,
        processo_id=conversation.processo_id,
        user_id=conversation.user_id,
        canal=conversation.canal,
        titulo=conversation.titulo,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=msg_count.scalar() or 0,
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")

    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissao")

    await db.delete(conversation)
    await db.commit()


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Non-streaming message endpoint (kept for Telegram and backward compatibility)."""
    # Get conversation
    result = await db.execute(
        select(Conversation).where(Conversation.id == request.conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")

    # Verify access
    await get_processo_with_access(conversation.processo_id, db, current_user)

    # Get conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == request.conversation_id)
        .order_by(Message.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
    ]

    # Save user message
    user_message = Message(
        conversation_id=request.conversation_id,
        role="user",
        content=request.content,
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)

    # Fetch processo contexto
    processo_result = await db.execute(
        select(Processo).where(Processo.id == conversation.processo_id)
    )
    processo = processo_result.scalar_one_or_none()
    processo_contexto = processo.contexto if processo else None

    # Get RAG response
    rag_result = await rag_chat(
        query=request.content,
        conversation_history=history,
        db=db,
        processo_id=conversation.processo_id,
        processo_contexto=processo_contexto,
    )

    # Convert sources to SourceInfo
    sources = [
        SourceInfo(
            doc_titulo=s["doc_titulo"],
            doc_tipo=s["doc_tipo"],
            documento_id=s["documento_id"],
            similarity=s["similarity"],
        )
        for s in rag_result["sources"]
    ]

    # Save assistant message
    assistant_message = Message(
        conversation_id=request.conversation_id,
        role="assistant",
        content=rag_result["answer"],
        chunks_usados=[UUID(c) for c in rag_result["chunks_used"]],
        tokens_input=rag_result["tokens_input"],
        tokens_output=rag_result["tokens_output"],
        custo_estimado=rag_result["cost_usd"],
        metadata_={"sources": [s.model_dump() for s in sources]},
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    # Generate title in background
    asyncio.create_task(_generate_title(conversation.id, request.content))

    return ChatResponse(
        user_message=MessageResponse(
            id=user_message.id,
            conversation_id=user_message.conversation_id,
            role=user_message.role,
            content=user_message.content,
            tokens_input=None,
            tokens_output=None,
            custo_estimado=None,
            created_at=user_message.created_at,
        ),
        assistant_message=MessageResponse(
            id=assistant_message.id,
            conversation_id=assistant_message.conversation_id,
            role=assistant_message.role,
            content=assistant_message.content,
            tokens_input=assistant_message.tokens_input,
            tokens_output=assistant_message.tokens_output,
            custo_estimado=assistant_message.custo_estimado,
            created_at=assistant_message.created_at,
            sources=sources,
        ),
        sources=sources,
    )


@router.post("/message/stream")
async def send_message_stream(
    request: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streaming message endpoint using Server-Sent Events."""
    # Get conversation
    result = await db.execute(
        select(Conversation).where(Conversation.id == request.conversation_id)
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")

    # Verify access
    await get_processo_with_access(conversation.processo_id, db, current_user)

    # Get conversation history
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == request.conversation_id)
        .order_by(Message.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in history_result.scalars().all()
    ]

    # Save user message
    user_message = Message(
        conversation_id=request.conversation_id,
        role="user",
        content=request.content,
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)

    # Fetch processo contexto
    processo_result = await db.execute(
        select(Processo).where(Processo.id == conversation.processo_id)
    )
    processo = processo_result.scalar_one_or_none()
    processo_contexto = processo.contexto if processo else None

    async def event_generator():
        rag_result_data = None

        async for event in rag_chat_stream(
            query=request.content,
            conversation_history=history,
            db=db,
            processo_id=conversation.processo_id,
            processo_contexto=processo_contexto,
        ):
            # Capture the done event data for saving
            if event.startswith("event: done"):
                lines = event.strip().split("\n")
                for line in lines:
                    if line.startswith("data: "):
                        rag_result_data = json.loads(line[6:])
                        break

            yield event

        # Save assistant message after streaming completes
        if rag_result_data:
            sources = [
                SourceInfo(
                    doc_titulo=s["doc_titulo"],
                    doc_tipo=s["doc_tipo"],
                    documento_id=s["documento_id"],
                    similarity=s["similarity"],
                )
                for s in rag_result_data["sources"]
            ]

            assistant_message = Message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=rag_result_data["answer"],
                chunks_usados=[UUID(c) for c in rag_result_data["chunks_used"]],
                tokens_input=rag_result_data["tokens_input"],
                tokens_output=rag_result_data["tokens_output"],
                custo_estimado=rag_result_data["cost_usd"],
                metadata_={"sources": [s.model_dump() for s in sources]},
            )
            db.add(assistant_message)
            await db.commit()

        # Generate title in background
        asyncio.create_task(_generate_title(conversation.id, request.content))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sources/{message_id}")
async def get_message_sources(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Message).where(Message.id == message_id))
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Mensagem nao encontrada")

    # Verify access through conversation
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == message.conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    await get_processo_with_access(conversation.processo_id, db, current_user)

    return {"sources": message.metadata_.get("sources", []) if message.metadata_ else []}
