import os
import re
import tempfile
from uuid import UUID
from typing import Optional

import tiktoken
import pdfplumber
import pytesseract
from PIL import Image
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.models import Document, Chunk, Processo
from app.services.s3_storage import S3Storage

settings = get_settings()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")


# ============================================
# TEXT EXTRACTION
# ============================================

def extract_text_from_pdf(filepath: str) -> str:
    text_parts = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                text_parts.append(text)

    # Se pdfplumber não extraiu texto, tentar OCR (PDF escaneado)
    if not text_parts:
        from pdf2image import convert_from_path
        images = convert_from_path(filepath, dpi=300)
        for image in images:
            ocr_text = pytesseract.image_to_string(image, lang="por")
            if ocr_text and ocr_text.strip():
                text_parts.append(ocr_text)

    return "\n\n".join(text_parts)


def extract_text_from_image(filepath: str) -> str:
    image = Image.open(filepath)
    return pytesseract.image_to_string(image, lang="por")


def extract_text_from_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def parse_whatsapp_export(filepath: str) -> str:
    """Parse WhatsApp exported chat .txt file."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


async def transcribe_audio(filepath: str) -> str:
    """Transcribe audio using OpenAI Whisper API."""
    with open(filepath, "rb") as audio_file:
        response = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="pt",
        )
    return response.text


def extract_text(filepath: str, mime_type: str, doc_type: str) -> str:
    """Route to appropriate extractor based on file type."""
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return extract_text_from_image(filepath)
    elif ext in (".txt", ".csv"):
        return extract_text_from_txt(filepath)
    elif ext in (".doc", ".docx"):
        import docx
        doc = docx.Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(filepath)
        text_parts = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join(str(cell) if cell else "" for cell in row)
                if row_text.strip():
                    text_parts.append(row_text)
        return "\n".join(text_parts)
    else:
        return extract_text_from_txt(filepath)


# ============================================
# CHUNKING
# ============================================

def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))


def chunk_text(
    text: str,
    chunk_size: int = settings.CHUNK_SIZE,
    overlap: int = settings.CHUNK_OVERLAP,
) -> list[dict]:
    """Split text into overlapping chunks by token count."""
    sentences = re.split(r'(?<=[.!?\n])\s+', text)
    chunks = []
    current_chunk = []
    current_tokens = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sent_tokens = count_tokens(sentence)

        if current_tokens + sent_tokens > chunk_size and current_chunk:
            chunk_text_content = " ".join(current_chunk)
            chunks.append({
                "conteudo": chunk_text_content,
                "token_count": count_tokens(chunk_text_content),
            })

            # Keep last sentences for overlap
            overlap_tokens = 0
            overlap_sentences = []
            for s in reversed(current_chunk):
                t = count_tokens(s)
                if overlap_tokens + t > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += t

            current_chunk = overlap_sentences
            current_tokens = overlap_tokens

        current_chunk.append(sentence)
        current_tokens += sent_tokens

    # Last chunk
    if current_chunk:
        chunk_text_content = " ".join(current_chunk)
        chunks.append({
            "conteudo": chunk_text_content,
            "token_count": count_tokens(chunk_text_content),
        })

    return chunks


# ============================================
# EMBEDDINGS
# ============================================

async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings in batches."""
    batch_size = 100
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = await openai_client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=batch,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
        all_embeddings.extend([item.embedding for item in response.data])

    return all_embeddings


# ============================================
# FULL PIPELINE
# ============================================

async def process_document(document_id: UUID, db: AsyncSession):
    """Full pipeline: download from S3 → extract → chunk → embed → store."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        return

    try:
        # Update status
        doc.status = "processing"
        await db.commit()

        # Download from S3
        s3 = S3Storage()
        content = await s3.download_file(doc.arquivo_original)

        # Save to temp file for processing
        ext = os.path.splitext(doc.arquivo_nome)[1]
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # 1. Extract text
            if doc.tipo in ("whatsapp_audio", "audio") and ext.lower() in (
                ".ogg", ".mp3", ".m4a", ".wav"
            ):
                text = await transcribe_audio(tmp_path)
            else:
                text = extract_text(tmp_path, doc.arquivo_mime, doc.tipo)

            doc.texto_extraido = text

            # 2. Chunk
            chunks_data = chunk_text(text)
            if not chunks_data:
                doc.status = "processed"
                await db.commit()
                return

            # 3. Generate embeddings
            chunk_texts = [c["conteudo"] for c in chunks_data]
            embeddings = await generate_embeddings(chunk_texts)

            # 4. Store chunks
            for i, (chunk_data, embedding) in enumerate(zip(chunks_data, embeddings)):
                chunk = Chunk(
                    documento_id=doc.id,
                    conteudo=chunk_data["conteudo"],
                    posicao=i,
                    token_count=chunk_data["token_count"],
                    embedding=embedding,
                    metadata_={
                        "doc_tipo": doc.tipo,
                        "doc_titulo": doc.titulo,
                        "participantes": doc.participantes or [],
                        "data_referencia": str(doc.data_referencia) if doc.data_referencia else None,
                    },
                )
                db.add(chunk)

            doc.status = "processed"
            await db.commit()

            # Run financial analysis for financial documents
            if doc.tipo in ("extrato_bancario", "comprovante"):
                try:
                    from app.services.financial_analyzer import FinancialAnalyzer

                    # Fetch processo contexto
                    proc_result = await db.execute(
                        select(Processo).where(Processo.id == doc.processo_id)
                    )
                    processo = proc_result.scalar_one_or_none()
                    processo_contexto = processo.contexto if processo else None

                    analyzer = FinancialAnalyzer(db)
                    await analyzer.analyze_document(
                        documento_id=doc.id,
                        processo_id=doc.processo_id,
                        processo_contexto=processo_contexto,
                    )
                except Exception as e:
                    print(f"Financial analysis failed for document {doc.id}: {e}")

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        await db.commit()
        raise
