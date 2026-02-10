from datetime import datetime, date
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel


class DocumentUpload(BaseModel):
    processo_id: UUID
    tipo: str
    titulo: str
    descricao: Optional[str] = None
    participantes: Optional[List[str]] = None
    data_referencia: Optional[date] = None


class DocumentUpdate(BaseModel):
    titulo: Optional[str] = None
    tipo: Optional[str] = None
    data_referencia: Optional[date] = None


class DocumentResponse(BaseModel):
    id: UUID
    processo_id: UUID
    user_id: UUID
    tipo: str
    titulo: str
    descricao: Optional[str]
    participantes: Optional[List[str]]
    data_referencia: Optional[date]
    arquivo_nome: str
    arquivo_mime: Optional[str]
    arquivo_tamanho: Optional[int]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


class DocumentSearchResult(BaseModel):
    document_id: UUID
    titulo: str
    tipo: str
    excerpt: str
    relevance: float


class DocumentSearchResponse(BaseModel):
    results: List[DocumentSearchResult]
    query: str
    total: int
