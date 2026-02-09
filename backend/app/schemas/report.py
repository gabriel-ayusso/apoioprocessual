from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel


class ReportGenerateRequest(BaseModel):
    processo_id: UUID
    tipo: str  # 'transacoes', 'timeline', 'evidencias'
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    categorias: Optional[List[str]] = None
    pagadores: Optional[List[str]] = None


class ReportResponse(BaseModel):
    id: UUID
    processo_id: UUID
    tipo: str
    arquivo_nome: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    reports: List[ReportResponse]
    total: int


class ReportTemplateResponse(BaseModel):
    tipo: str
    nome: str
    descricao: str
    parametros: List[str]
