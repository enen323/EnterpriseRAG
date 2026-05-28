import logging
from typing import List, Tuple

import numpy as np
from langchain_core.documents import Document as LCDocument

from core.config import settings

logger = logging.getLogger(__name__)

_reranker = None
_diversity_embedder = None


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


def _get_diversity_embedder():
    global _diversity_embedder
    if _diversity_embedder is None:
        from sentence_transformers import SentenceTransformer

        _diversity_embedder = SentenceTransformer(settings.EMBEDDING_MODEL, device=settings.EMBEDDING_DEVICE)
    return _diversity_embedder


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


def rerank_with_diversity(
    query: str,
    documents: List[Tuple[LCDocument, float]],
    top_k: int = settings.RERANKER_TOP_K,
    diversity_lambda: float = settings.RERANKER_DIVERSITY_LAMBDA,
) -> List[Tuple[LCDocument, float]]:
    """
    Rerank with diversity penalty.
    1. Score all docs with cross-encoder reranker
    2. Greedy selection: pick highest-scoring, then penalize remaining by similarity to selected set
    """
    if not documents:
        return []

    # Step 1: Cross-encoder scores
    reranker = _get_reranker()
    pairs = [(query, doc.page_content) for doc, _ in documents]
    scores = reranker.compute_score(pairs)
    scored = [(doc, float(score)) for (doc, _), score in zip(documents, scores)]

    # Step 2: Greedy diversity selection
    embedder = _get_diversity_embedder()
    texts = [doc.page_content for doc, _ in scored]
    embeddings = embedder.encode(texts, normalize_embeddings=True)

    selected_indices = []
    remaining = list(range(len(scored)))

    for _ in range(min(top_k, len(scored))):
        if not remaining:
            break

        best_idx = None
        best_score = -float("inf")

        for idx in remaining:
            rerank_score = scored[idx][1]

            # Diversity penalty: max cosine similarity to already selected
            penalty = 0.0
            if selected_indices:
                similarities = np.dot(embeddings[selected_indices], embeddings[idx])
                penalty = float(np.max(similarities))

            adjusted = rerank_score - diversity_lambda * penalty

            if adjusted > best_score:
                best_score = adjusted
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)

    return [scored[i] for i in selected_indices]
