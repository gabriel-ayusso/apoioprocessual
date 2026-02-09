from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.models import User, Conversation, Message
from app.schemas.chat import (
    ConversationCreate, ConversationResponse, ConversationListResponse,
    MessageCreate, MessageResponse, ChatResponse, MessageHistoryResponse, SourceInfo
)
from app.api.deps import get_current_user, get_processo_with_access
from app.services.rag_engine import chat as rag_chat

router = APIRouter(prefix="/chat", tags=["chat"])


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


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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

    # Get RAG response
    rag_result = await rag_chat(
        query=request.content,
        conversation_history=history,
        db=db,
        processo_id=conversation.processo_id,
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

    # Update conversation title if first message
    if not conversation.titulo:
        conversation.titulo = request.content[:100]

    await db.commit()
    await db.refresh(assistant_message)

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
