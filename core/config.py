import os
from pathlib import Path
from pydantic_settings import BaseSettings

# China HF mirror — set before any model import
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from pydantic import model_validator


class Settings(BaseSettings):
    # PostgreSQL
    DB_HOST: str = "192.168.100.128"
    DB_PORT: int = 5432
    DB_USER: str = "rag_user"
    DB_PASSWORD: str = "rag_password"
    DB_NAME: str = "enterprise_rag"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # JWT
    JWT_SECRET: str = "change-me-in-production-use-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours

    # DeepSeek
    DEEPSEEK_API_KEY: str = ""  # Must be set in .env
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"
    EMBEDDING_DEVICE: str = "cpu"

    # Reranker
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_DEVICE: str = "cpu"

    # Chroma
    CHROMA_PERSIST_DIR: str = str(Path(__file__).parent.parent / "chroma_db")
    CHROMA_COLLECTION: str = "doc_chunks"

    # Retrieval
    RETRIEVER_TOP_K: int = 20
    RERANKER_TOP_K: int = 5

    # Chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 128

    @model_validator(mode="after")
    def _check_secrets(self):
        if not self.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY must be set in .env file")
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
