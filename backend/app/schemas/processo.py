from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel


class ProcessoCreate(BaseModel):
    numero: Optional[str] = None
    titulo: str
    descricao: Optional[str] = None
    contexto: Optional[str] = None


class ProcessoUpdate(BaseModel):
    numero: Optional[str] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    contexto: Optional[str] = None
    status: Optional[str] = None


class ProcessoShareRequest(BaseModel):
    user_id: UUID
    role: str = "viewer"  # 'viewer' or 'editor'


class SharedUserResponse(BaseModel):
    user_id: UUID
    user_name: str
    user_email: str
    role: str
    shared_at: datetime


class ProcessoResponse(BaseModel):
    id: UUID
    owner_id: UUID
    numero: Optional[str]
    titulo: str
    descricao: Optional[str]
    contexto: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    shared_users: List[SharedUserResponse] = []

    class Config:
        from_attributes = True


class ProcessoListResponse(BaseModel):
    processos: List[ProcessoResponse]
    total: int
