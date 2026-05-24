import uuid
from datetime import datetime
from pydantic import BaseModel


# === Auth ===
class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# === Documents ===
class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: str
    status: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# === Conversations ===
class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    sources: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


# === QA ===
class QARequest(BaseModel):
    question: str
    conversation_id: str | None = None


class SourceItem(BaseModel):
    filename: str
    chunk_text: str
    score: float


class QAResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    conversation_id: str
