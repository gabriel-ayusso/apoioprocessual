from uuid import UUID
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.models import User, Transacao
from app.schemas.transacao import (
    TransacaoUpdate, TransacaoResponse, TransacaoListResponse,
    TransacaoSummaryResponse, TransacaoSummaryItem
)
from app.api.deps import get_current_user, get_processo_with_access

router = APIRouter(prefix="/transacoes", tags=["transacoes"])


@router.get("", response_model=TransacaoListResponse)
async def list_transacoes(
    processo_id: UUID,
    categoria: Optional[str] = None,
    pagador: Optional[str] = None,
    revisado: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify access
    await get_processo_with_access(processo_id, db, current_user)

    query = select(Transacao).where(Transacao.processo_id == processo_id)

    if categoria:
        query = query.where(Transacao.categoria == categoria)
    if pagador:
        query = query.where(Transacao.pagador == pagador)
    if revisado is not None:
        query = query.where(Transacao.revisado_humano == revisado)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get transacoes
    result = await db.execute(
        query.order_by(Transacao.data.desc().nullslast()).offset(skip).limit(limit)
    )
    transacoes = result.scalars().all()

    return TransacaoListResponse(transacoes=transacoes, total=total)


@router.get("/summary", response_model=TransacaoSummaryResponse)
async def get_summary(
    processo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify access
    await get_processo_with_access(processo_id, db, current_user)

    # Summary by categoria
    cat_result = await db.execute(
        select(
            Transacao.categoria,
            func.sum(Transacao.valor).label("total"),
            func.count(Transacao.id).label("count"),
        )
        .where(Transacao.processo_id == processo_id)
        .group_by(Transacao.categoria)
    )
    by_categoria = [
        TransacaoSummaryItem(
            categoria=row.categoria,
            pagador=None,
            total=row.total or Decimal(0),
            count=row.count,
        )
        for row in cat_result.all()
    ]

    # Summary by pagador
    pag_result = await db.execute(
        select(
            Transacao.pagador,
            func.sum(Transacao.valor).label("total"),
            func.count(Transacao.id).label("count"),
        )
        .where(Transacao.processo_id == processo_id)
        .group_by(Transacao.pagador)
    )
    by_pagador = [
        TransacaoSummaryItem(
            categoria=None,
            pagador=row.pagador,
            total=row.total or Decimal(0),
            count=row.count,
        )
        for row in pag_result.all()
    ]

    # Total
    total_result = await db.execute(
        select(
            func.sum(Transacao.valor).label("total"),
            func.count(Transacao.id).label("count"),
        )
        .where(Transacao.processo_id == processo_id)
    )
    total_row = total_result.one()

    return TransacaoSummaryResponse(
        by_categoria=by_categoria,
        by_pagador=by_pagador,
        total_geral=total_row.total or Decimal(0),
        total_transacoes=total_row.count,
    )


@router.get("/{transacao_id}", response_model=TransacaoResponse)
async def get_transacao(
    transacao_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Transacao).where(Transacao.id == transacao_id))
    transacao = result.scalar_one_or_none()

    if not transacao:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")

    # Verify access
    await get_processo_with_access(transacao.processo_id, db, current_user)

    return transacao


@router.put("/{transacao_id}", response_model=TransacaoResponse)
async def update_transacao(
    transacao_id: UUID,
    request: TransacaoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Transacao).where(Transacao.id == transacao_id))
    transacao = result.scalar_one_or_none()

    if not transacao:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")

    # Verify access
    await get_processo_with_access(transacao.processo_id, db, current_user)

    if request.data is not None:
        transacao.data = request.data
    if request.pagador is not None:
        transacao.pagador = request.pagador
    if request.beneficiario is not None:
        transacao.beneficiario = request.beneficiario
    if request.categoria is not None:
        transacao.categoria = request.categoria

    await db.commit()
    await db.refresh(transacao)

    return transacao


@router.post("/{transacao_id}/confirm", response_model=TransacaoResponse)
async def confirm_transacao(
    transacao_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Transacao).where(Transacao.id == transacao_id))
    transacao = result.scalar_one_or_none()

    if not transacao:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")

    # Verify access
    await get_processo_with_access(transacao.processo_id, db, current_user)

    transacao.revisado_humano = True
    transacao.revisado_por = current_user.id

    await db.commit()
    await db.refresh(transacao)

    return transacao
