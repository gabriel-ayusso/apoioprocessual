import os
import re
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.config import get_settings
from app.models.models import User, Document, Processo
from app.schemas.document import DocumentResponse, DocumentListResponse, DocumentSearchResponse, DocumentSearchResult, DocumentUpdate
from app.api.deps import get_current_user, get_processo_with_access
from app.services.document_processor import process_document
from app.services.s3_storage import S3Storage

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


def sanitize_filename(filename: str) -> str:
    """Remove potentially dangerous characters from filename."""
    # Keep only alphanumeric, dots, hyphens, underscores
    name = re.sub(r'[^\w\-.]', '_', filename)
    # Prevent directory traversal
    name = name.replace('..', '_')
    return name


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    processo_id: UUID,
    tipo: Optional[str] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify access to processo
    await get_processo_with_access(processo_id, db, current_user)

    query = select(Document).where(Document.processo_id == processo_id)

    if tipo:
        query = query.where(Document.tipo == tipo)
    if status_filter:
        query = query.where(Document.status == status_filter)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get documents
    result = await db.execute(
        query.order_by(Document.created_at.desc()).offset(skip).limit(limit)
    )
    documents = result.scalars().all()

    return DocumentListResponse(documents=documents, total=total)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    processo_id: UUID = Form(...),
    tipo: str = Form(...),
    titulo: str = Form(...),
    descricao: Optional[str] = Form(None),
    participantes: Optional[str] = Form(None),  # comma-separated
    data_referencia: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify access to processo
    await get_processo_with_access(processo_id, db, current_user)

    # Validate file size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande. Maximo: {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB",
        )

    # Validate mime type
    allowed_mimes = [
        'application/pdf',
        'image/png', 'image/jpeg', 'image/webp', 'image/bmp',
        'text/plain', 'text/csv',
        'audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/m4a',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ]
    if file.content_type and file.content_type not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo nao permitido: {file.content_type}",
        )

    # Upload to S3
    s3 = S3Storage()
    safe_filename = sanitize_filename(file.filename or "document")
    s3_key = await s3.upload_file(content, safe_filename, processo_id)

    # Parse participantes
    participantes_list = None
    if participantes:
        participantes_list = [p.strip() for p in participantes.split(',') if p.strip()]

    # Parse data_referencia
    data_ref = None
    if data_referencia:
        from datetime import datetime
        try:
            data_ref = datetime.strptime(data_referencia, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Create document record
    document = Document(
        processo_id=processo_id,
        user_id=current_user.id,
        tipo=tipo,
        titulo=titulo,
        descricao=descricao,
        participantes=participantes_list,
        data_referencia=data_ref,
        arquivo_original=s3_key,
        arquivo_nome=safe_filename,
        arquivo_mime=file.content_type,
        arquivo_tamanho=len(content),
        status="uploaded",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Process document in background
    background_tasks.add_task(process_document_task, document.id)

    return document


async def process_document_task(document_id: UUID):
    """Background task to process document."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await process_document(document_id, db)
        except Exception as e:
            # Update document with error
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "error"
                doc.error_message = str(e)
                await db.commit()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")

    # Verify access
    await get_processo_with_access(document.processo_id, db, current_user)

    return document


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")

    # Verify access
    await get_processo_with_access(document.processo_id, db, current_user)

    # Track tipo change for financial analysis
    old_tipo = document.tipo
    new_tipo = payload.tipo

    # Apply non-None fields
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        return document

    for field, value in update_data.items():
        setattr(document, field, value)

    await db.flush()

    # Propagate changes to chunk metadata_
    metadata_updates = {}
    if payload.titulo is not None:
        metadata_updates["doc_titulo"] = payload.titulo
    if payload.tipo is not None:
        metadata_updates["doc_tipo"] = payload.tipo
    if payload.data_referencia is not None:
        metadata_updates["data_referencia"] = str(payload.data_referencia)

    if metadata_updates:
        import json
        from sqlalchemy import text as sa_text
        # Use metadata || jsonb overlay to update specific keys in one shot
        await db.execute(
            sa_text(
                "UPDATE chunks SET metadata = metadata || CAST(:patch AS jsonb) WHERE documento_id = :doc_id"
            ),
            {"patch": json.dumps(metadata_updates), "doc_id": str(document_id)},
        )

    await db.commit()
    await db.refresh(document)

    # Run financial analysis if tipo changed to a financial type
    financial_types = ("extrato_bancario", "comprovante")
    if (
        new_tipo is not None
        and new_tipo in financial_types
        and old_tipo not in financial_types
        and document.status == "processed"
    ):
        try:
            from app.services.financial_analyzer import FinancialAnalyzer

            proc_result = await db.execute(
                select(Processo).where(Processo.id == document.processo_id)
            )
            processo = proc_result.scalar_one_or_none()
            processo_contexto = processo.contexto if processo else None

            analyzer = FinancialAnalyzer(db)
            await analyzer.analyze_document(
                documento_id=document.id,
                processo_id=document.processo_id,
                processo_contexto=processo_contexto,
            )
        except Exception as e:
            print(f"Financial analysis failed for document {document.id}: {e}")

    return document


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")

    # Verify access
    await get_processo_with_access(document.processo_id, db, current_user)

    # Generate presigned URL or stream file
    s3 = S3Storage()
    url = await s3.get_presigned_url(document.arquivo_original)

    return {"download_url": url, "filename": document.arquivo_nome}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")

    # Verify access (need to be owner or editor)
    processo_result = await db.execute(select(Processo).where(Processo.id == document.processo_id))
    processo = processo_result.scalar_one_or_none()

    if processo.owner_id != current_user.id and document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Sem permissao para excluir este documento")

    # Delete from S3
    s3 = S3Storage()
    await s3.delete_file(document.arquivo_original)

    # Delete from database (chunks will cascade)
    await db.delete(document)
    await db.commit()


@router.get("/search", response_model=DocumentSearchResponse)
async def search_documents(
    processo_id: UUID,
    q: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search for exact text within documents."""
    # Verify access
    await get_processo_with_access(processo_id, db, current_user)

    # Search in texto_extraido
    result = await db.execute(
        select(Document)
        .where(
            Document.processo_id == processo_id,
            Document.texto_extraido.ilike(f"%{q}%"),
        )
        .limit(20)
    )
    documents = result.scalars().all()

    results = []
    for doc in documents:
        # Find excerpt around match
        text = doc.texto_extraido or ""
        lower_text = text.lower()
        lower_q = q.lower()
        pos = lower_text.find(lower_q)

        if pos >= 0:
            start = max(0, pos - 100)
            end = min(len(text), pos + len(q) + 100)
            excerpt = "..." + text[start:end] + "..."
        else:
            excerpt = text[:200] + "..."

        results.append(DocumentSearchResult(
            document_id=doc.id,
            titulo=doc.titulo,
            tipo=doc.tipo,
            excerpt=excerpt,
            relevance=1.0,
        ))

    return DocumentSearchResponse(results=results, query=q, total=len(results))
