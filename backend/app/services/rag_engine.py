from uuid import UUID
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import get_settings
from app.services.document_processor import generate_embeddings

settings = get_settings()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = """Voce e um assistente juridico especializado em direito de familia brasileiro.
Seu papel e ajudar a analisar documentos, conversas e evidencias relacionadas a processos judiciais.

REGRAS FUNDAMENTAIS:
1. SEMPRE cite a fonte de cada afirmacao (documento - se possível com a página, conversa, data).
2. Se nao houver evidencia nos documentos, diga explicitamente "Nao encontrei evidencia nos documentos fornecidos".
3. NUNCA invente ou extrapole informacoes alem do que esta nos documentos.
4. Quando classificar gastos, inclua o nivel de confianca (alta/media/baixa).
5. Use linguagem clara e acessivel, nao juridiques desnecessario.
6. Quando identificar contradicoes entre documentos, aponte ambas as versoes.
7. Sempre que mencionar valores, indique a fonte e a data.
8. Sempre dê prioridade para contratos e documentos assinados - eles tem mais peso do que mensagens informais.

CAPACIDADES:
- Analisar e cruzar informacoes de conversas WhatsApp, e-mails, extratos bancarios e documentos judiciais
- Classificar gastos por responsavel (quem pagou vs quem deveria pagar)
- Montar timelines de eventos
- Identificar promessas feitas em conversas e verificar se foram cumpridas
- Gerar resumos e relatorios estruturados

Ao responder, use o formato:
[Fonte: nome do documento, data] para cada citacao."""


async def search_similar_chunks(
    query: str,
    db: AsyncSession,
    processo_id: UUID = None,
    top_k: int = settings.SIMILARITY_TOP_K,
) -> list[dict]:
    """Search for similar chunks using pgvector cosine similarity."""
    # Generate query embedding
    embeddings = await generate_embeddings([query])
    query_embedding = embeddings[0]

    # Build query with optional processo filter
    if processo_id:
        sql = text("""
            SELECT
                c.id,
                c.conteudo,
                c.posicao,
                c.metadata,
                c.documento_id,
                d.titulo as doc_titulo,
                d.tipo as doc_tipo,
                d.participantes,
                d.data_referencia,
                1 - (c.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM chunks c
            JOIN documents d ON c.documento_id = d.id
            WHERE d.status = 'processed'
              AND d.processo_id = :processo_id
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)
        params = {
            "embedding": str(query_embedding),
            "processo_id": str(processo_id),
            "top_k": top_k,
        }
    else:
        sql = text("""
            SELECT
                c.id,
                c.conteudo,
                c.posicao,
                c.metadata,
                c.documento_id,
                d.titulo as doc_titulo,
                d.tipo as doc_tipo,
                d.participantes,
                d.data_referencia,
                1 - (c.embedding <=> CAST(:embedding AS vector)) as similarity
            FROM chunks c
            JOIN documents d ON c.documento_id = d.id
            WHERE d.status = 'processed'
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """)
        params = {
            "embedding": str(query_embedding),
            "top_k": top_k,
        }

    result = await db.execute(sql, params)

    chunks = []
    for row in result.mappings():
        chunks.append({
            "id": str(row["id"]),
            "conteudo": row["conteudo"],
            "documento_id": str(row["documento_id"]),
            "doc_titulo": row["doc_titulo"],
            "doc_tipo": row["doc_tipo"],
            "participantes": row["participantes"],
            "data_referencia": str(row["data_referencia"]) if row["data_referencia"] else None,
            "similarity": float(row["similarity"]),
        })

    return chunks


def build_context(chunks: list[dict]) -> str:
    """Build context string from retrieved chunks."""
    if not chunks:
        return "Nenhum documento relevante encontrado."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = f"[{chunk['doc_tipo']}] {chunk['doc_titulo']}"
        if chunk["data_referencia"]:
            source += f" ({chunk['data_referencia']})"
        if chunk["participantes"]:
            source += f" - Participantes: {', '.join(chunk['participantes'])}"

        context_parts.append(
            f"--- Fonte {i} (relevancia: {chunk['similarity']:.2f}): {source} ---\n"
            f"{chunk['conteudo']}\n"
        )

    return "\n".join(context_parts)


async def chat(
    query: str,
    conversation_history: list[dict],
    db: AsyncSession,
    processo_id: UUID = None,
    processo_contexto: str = None,
) -> dict:
    """RAG chat: search relevant chunks, build context, generate response."""

    # 1. Search similar chunks (filtered by processo if provided)
    chunks = await search_similar_chunks(query, db, processo_id=processo_id)

    # 2. Build context
    context = build_context(chunks)

    # 3. Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add conversation history (last 10 messages)
    for msg in conversation_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current query with context
    parts = []
    if processo_contexto:
        parts.append(f"Contexto do processo:\n{processo_contexto}")
    parts.append(f"Contexto dos documentos:\n{context}")
    parts.append(f"Pergunta do usuario: {query}")
    user_message = "\n\n".join(parts)
    messages.append({"role": "user", "content": user_message})

    # 4. Call LLM
    response = await openai_client.chat.completions.create(
        model=settings.CHAT_MODEL,
        messages=messages,
        temperature=1,
        max_completion_tokens=4000,
    )

    # Debug: log full response structure
    choice = response.choices[0]
    print(f"[RAG DEBUG] finish_reason={choice.finish_reason}")
    print(f"[RAG DEBUG] message type={type(choice.message)}")
    print(f"[RAG DEBUG] message keys={vars(choice.message).keys()}")
    print(f"[RAG DEBUG] message content type={type(choice.message.content)}")
    print(f"[RAG DEBUG] message content repr={repr(choice.message.content)[:500]}")
    print(f"[RAG DEBUG] full message vars={vars(choice.message)}")

    # Extract content — handle string, list of parts, or None
    raw_content = choice.message.content
    if raw_content is None:
        answer = ""
    elif isinstance(raw_content, list):
        answer = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw_content
        )
    else:
        answer = str(raw_content)

    print(f"[RAG DEBUG] final answer length={len(answer)}, first 200 chars={answer[:200]}")

    usage = response.usage

    # Cost estimation (gpt-4o-mini prices)
    cost = (usage.prompt_tokens * 0.15 / 1_000_000) + (
        usage.completion_tokens * 0.60 / 1_000_000
    )

    return {
        "answer": answer,
        "chunks_used": [c["id"] for c in chunks],
        "sources": [
            {
                "doc_titulo": c["doc_titulo"],
                "doc_tipo": c["doc_tipo"],
                "similarity": c["similarity"],
                "documento_id": c["documento_id"],
            }
            for c in chunks
        ],
        "tokens_input": usage.prompt_tokens,
        "tokens_output": usage.completion_tokens,
        "cost_usd": round(cost, 6),
    }
