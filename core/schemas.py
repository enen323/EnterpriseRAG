import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


# === Auth ===
class UserRegister(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("Username must be at least 2 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


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
    message_id: str = ""
    suggested_questions: list[str] | None = None


# === Feedback ===
class FeedbackCreate(BaseModel):
    message_id: str
    feedback: str = ""
    comment: str | None = None

    @field_validator("feedback")
    @classmethod
    def feedback_valid(cls, v: str) -> str:
        if v not in ("up", "down"):
            raise ValueError("feedback must be 'up' or 'down'")
        return v


class FeedbackOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    feedback: str
    comment: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# === Categories ===
class CategoryCreate(BaseModel):
    name: str


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    model_config = {"from_attributes": True}


# === Admin ===
class UserAdminOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    doc_count: int
    conv_count: int
    created_at: datetime


class StatsOut(BaseModel):
    user_count: int
    doc_count: int
    message_count: int
    new_users_7d: int


# === Document Preview ===
class PreviewOut(BaseModel):
    content: str
    filename: str
    file_type: str
