from datetime import datetime, date
from typing import Optional, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel


class TransacaoUpdate(BaseModel):
    data: Optional[date] = None
    pagador: Optional[str] = None
    beneficiario: Optional[str] = None
    categoria: Optional[str] = None


class TransacaoResponse(BaseModel):
    id: UUID
    processo_id: UUID
    descricao: str
    valor: Optional[Decimal]
    data: Optional[date]
    pagador: Optional[str]
    beneficiario: Optional[str]
    categoria: Optional[str]
    confianca: Optional[float]
    revisado_humano: bool
    trecho_evidencia: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TransacaoListResponse(BaseModel):
    transacoes: List[TransacaoResponse]
    total: int


class TransacaoSummaryItem(BaseModel):
    categoria: Optional[str]
    pagador: Optional[str]
    total: Decimal
    count: int


class TransacaoSummaryResponse(BaseModel):
    by_categoria: List[TransacaoSummaryItem]
    by_pagador: List[TransacaoSummaryItem]
    total_geral: Decimal
    total_transacoes: int
