from datetime import datetime
from typing import Optional, List
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    processo_id: UUID
    titulo: Optional[str] = None


class ConversationResponse(BaseModel):
    id: UUID
    processo_id: UUID
    user_id: UUID
    canal: str
    titulo: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int


class SourceInfo(BaseModel):
    doc_titulo: str
    doc_tipo: str
    documento_id: str
    similarity: float


class MessageCreate(BaseModel):
    conversation_id: UUID
    content: str


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    custo_estimado: Optional[Decimal]
    created_at: datetime
    sources: List[SourceInfo] = []

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    sources: List[SourceInfo]


class MessageHistoryResponse(BaseModel):
    messages: List[MessageResponse]
    conversation: ConversationResponse
