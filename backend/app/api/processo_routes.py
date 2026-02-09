from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db
from app.models.models import User, Processo, ProcessoUser, Document
from app.schemas.processo import (
    ProcessoCreate, ProcessoUpdate, ProcessoShareRequest,
    ProcessoResponse, ProcessoListResponse, SharedUserResponse
)
from app.api.deps import get_current_user, get_processo_with_access

router = APIRouter(prefix="/processos", tags=["processos"])


async def build_processo_response(processo: Processo, db: AsyncSession) -> ProcessoResponse:
    # Count documents
    doc_count = await db.execute(
        select(func.count(Document.id)).where(Document.processo_id == processo.id)
    )
    document_count = doc_count.scalar() or 0

    # Get shared users
    shared_result = await db.execute(
        select(ProcessoUser, User)
        .join(User, ProcessoUser.user_id == User.id)
        .where(ProcessoUser.processo_id == processo.id)
    )
    shared_users = [
        SharedUserResponse(
            user_id=pu.user_id,
            user_name=user.name,
            user_email=user.email,
            role=pu.role,
            shared_at=pu.created_at,
        )
        for pu, user in shared_result.all()
    ]

    return ProcessoResponse(
        id=processo.id,
        owner_id=processo.owner_id,
        numero=processo.numero,
        titulo=processo.titulo,
        descricao=processo.descricao,
        status=processo.status,
        created_at=processo.created_at,
        updated_at=processo.updated_at,
        document_count=document_count,
        shared_users=shared_users,
    )


@router.get("/", response_model=ProcessoListResponse)
async def list_processos(
    status_filter: str = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get processos where user is owner or has shared access
    query = (
        select(Processo)
        .outerjoin(ProcessoUser, Processo.id == ProcessoUser.processo_id)
        .where(
            or_(
                Processo.owner_id == current_user.id,
                ProcessoUser.user_id == current_user.id,
            )
        )
        .distinct()
    )

    if status_filter:
        query = query.where(Processo.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get processos
    result = await db.execute(
        query.order_by(Processo.updated_at.desc()).offset(skip).limit(limit)
    )
    processos = result.scalars().all()

    # Build responses
    responses = [await build_processo_response(p, db) for p in processos]

    return ProcessoListResponse(processos=responses, total=total)


@router.post("/", response_model=ProcessoResponse, status_code=status.HTTP_201_CREATED)
async def create_processo(
    request: ProcessoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    processo = Processo(
        owner_id=current_user.id,
        numero=request.numero,
        titulo=request.titulo,
        descricao=request.descricao,
    )
    db.add(processo)
    await db.commit()
    await db.refresh(processo)

    return await build_processo_response(processo, db)


@router.get("/{processo_id}", response_model=ProcessoResponse)
async def get_processo(
    processo: Processo = Depends(get_processo_with_access),
    db: AsyncSession = Depends(get_db),
):
    return await build_processo_response(processo, db)


@router.put("/{processo_id}", response_model=ProcessoResponse)
async def update_processo(
    request: ProcessoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    processo_id: UUID = None,
):
    # Only owner can update
    result = await db.execute(select(Processo).where(Processo.id == processo_id))
    processo = result.scalar_one_or_none()

    if not processo:
        raise HTTPException(status_code=404, detail="Processo nao encontrado")

    if processo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o proprietario pode atualizar")

    if request.numero is not None:
        processo.numero = request.numero
    if request.titulo is not None:
        processo.titulo = request.titulo
    if request.descricao is not None:
        processo.descricao = request.descricao
    if request.status is not None:
        processo.status = request.status

    await db.commit()
    await db.refresh(processo)

    return await build_processo_response(processo, db)


@router.delete("/{processo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_processo(
    processo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Processo).where(Processo.id == processo_id))
    processo = result.scalar_one_or_none()

    if not processo:
        raise HTTPException(status_code=404, detail="Processo nao encontrado")

    if processo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o proprietario pode excluir")

    await db.delete(processo)
    await db.commit()


@router.post("/{processo_id}/share", response_model=SharedUserResponse)
async def share_processo(
    processo_id: UUID,
    request: ProcessoShareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    result = await db.execute(select(Processo).where(Processo.id == processo_id))
    processo = result.scalar_one_or_none()

    if not processo:
        raise HTTPException(status_code=404, detail="Processo nao encontrado")

    if processo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o proprietario pode compartilhar")

    # Verify target user exists
    user_result = await db.execute(select(User).where(User.id == request.user_id))
    target_user = user_result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Nao e possivel compartilhar consigo mesmo")

    # Check if already shared
    existing = await db.execute(
        select(ProcessoUser).where(
            ProcessoUser.processo_id == processo_id,
            ProcessoUser.user_id == request.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Processo ja compartilhado com este usuario")

    # Create share
    share = ProcessoUser(
        processo_id=processo_id,
        user_id=request.user_id,
        role=request.role,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)

    return SharedUserResponse(
        user_id=target_user.id,
        user_name=target_user.name,
        user_email=target_user.email,
        role=share.role,
        shared_at=share.created_at,
    )


@router.delete("/{processo_id}/share/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unshare_processo(
    processo_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify ownership
    result = await db.execute(select(Processo).where(Processo.id == processo_id))
    processo = result.scalar_one_or_none()

    if not processo:
        raise HTTPException(status_code=404, detail="Processo nao encontrado")

    if processo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Apenas o proprietario pode remover compartilhamento")

    # Find and delete share
    share_result = await db.execute(
        select(ProcessoUser).where(
            ProcessoUser.processo_id == processo_id,
            ProcessoUser.user_id == user_id,
        )
    )
    share = share_result.scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="Compartilhamento nao encontrado")

    await db.delete(share)
    await db.commit()
