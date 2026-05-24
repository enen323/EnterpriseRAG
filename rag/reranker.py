import logging
from typing import List, Tuple

from langchain.schema import Document as LCDocument

from core.config import settings

logger = logging.getLogger(__name__)

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from FlagEmbedding import FlagReranker

        logger.info(f"Loading reranker model: {settings.RERANKER_MODEL}")
        _reranker = FlagReranker(
            settings.RERANKER_MODEL,
            use_fp16=False,
            device=settings.RERANKER_DEVICE,
        )
    return _reranker


def rerank(
    query: str,
    documents: List[Tuple[LCDocument, float]],
    top_k: int = settings.RERANKER_TOP_K,
) -> List[Tuple[LCDocument, float]]:
    """
    Rerank documents using BGE Reranker.

    Args:
        query: Original user query
        documents: List of (doc, similarity_score) from vector search
        top_k: Number of results to return after reranking

    Returns:
        List of (doc, reranker_score) sorted by score descending
    """
    if not documents:
        return []

    reranker = _get_reranker()
    pairs = [(query, doc.page_content) for doc, _ in documents]
    scores = reranker.compute_score(pairs)

    scored = [(doc, float(score)) for (doc, _), score in zip(documents, scores)]
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[:top_k]
