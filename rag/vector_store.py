import logging
import uuid
from typing import List, Optional, Tuple

from langchain_core.documents import Document as LCDocument
from langchain_chroma import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

from core.config import settings

logger = logging.getLogger(__name__)

_vector_store: Chroma | None = None

BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class BGEEmbeddings(HuggingFaceEmbeddings):
    """HuggingFaceEmbeddings with BGE query instruction prepended."""

    query_instruction: str = BGE_QUERY_INSTRUCTION

    def embed_query(self, text: str) -> List[float]:
        return super().embed_query(self.query_instruction + text)


def get_embedding_model() -> HuggingFaceEmbeddings:
    return BGEEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": settings.EMBEDDING_DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )


def get_vector_store(collection_name: Optional[str] = None) -> Chroma:
    global _vector_store
    if _vector_store is None:
        embedding = get_embedding_model()
        _vector_store = Chroma(
            collection_name=collection_name or settings.CHROMA_COLLECTION,
            persist_directory=settings.CHROMA_PERSIST_DIR,
            embedding_function=embedding,
        )
    return _vector_store


def add_documents(docs: List[LCDocument], doc_id: str, user_id: str = "", collection_name: Optional[str] = None) -> int:
    """Add documents to Chroma. Returns chunk count."""
    for d in docs:
        d.metadata["doc_id"] = doc_id
        d.metadata["user_id"] = user_id

    vector_store = get_vector_store(collection_name)
    vector_store.add_documents(docs)
    return len(docs)


def delete_document_chunks(doc_id: str, collection_name: Optional[str] = None):
    """Delete all chunks belonging to a document."""
    vector_store = get_vector_store(collection_name)
    vector_store.delete(where={"doc_id": doc_id})


def search_documents(query: str, k: int = settings.RETRIEVER_TOP_K, collection_name: Optional[str] = None, filter: Optional[dict] = None) -> List[Tuple[LCDocument, float]]:
    """Search Chroma and return top-k documents with relevance scores."""
    vector_store = get_vector_store(collection_name)
    return vector_store.similarity_search_with_relevance_scores(query, k=k, filter=filter)
