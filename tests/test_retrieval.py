from unittest.mock import patch, MagicMock

import pytest

from rag.vector_store import search_documents


@pytest.fixture(autouse=True)
def mock_embedding():
    """Mock the embedding model to avoid downloading heavy BGE models."""
    with patch("rag.vector_store.get_embedding_model") as mock:
        mock_instance = MagicMock()
        # Chroma expects embed_query to return a list of floats and embed_documents to return list of list of floats
        mock_instance.embed_query.return_value = [0.0] * 768
        mock_instance.embed_documents.return_value = [[0.0] * 768]
        mock.return_value = mock_instance
        yield mock


def test_search_no_results():
    """Should return empty list when no documents exist in collection."""
    results = search_documents("test query", k=5, collection_name="test_empty_retrieval")
    assert len(results) == 0


def test_rerank_empty_list():
    """Reranking empty list should return empty list."""
    from rag.reranker import rerank

    result = rerank("test query", [])
    assert result == []


@pytest.mark.asyncio
async def test_rerank_diversity_reduces_duplicates():
    """rerank_with_diversity should select diverse chunks over similar ones."""
    from rag.reranker import rerank_with_diversity
    from langchain_core.documents import Document as LCDocument
    import numpy as np

    docs = [
        (LCDocument(page_content="Python is a programming language", metadata={"source": "a.md"}), 0.9),
        (LCDocument(page_content="Python supports OOP and functional programming", metadata={"source": "a.md"}), 0.85),
        (LCDocument(page_content="Java is a compiled language", metadata={"source": "b.md"}), 0.8),
    ]

    # Mock cross-encoder reranker: return scores matching the input order
    mock_reranker = MagicMock()
    mock_reranker.compute_score.return_value = [0.9, 0.85, 0.8]

    # Mock diversity embedder: two similar docs (a.md) and one different doc (b.md)
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.array([
        [1.0, 0.0, 0.0],
        [0.98, 0.02, 0.0],
        [0.0, 0.0, 1.0],
    ])

    with patch("rag.reranker._get_reranker", return_value=mock_reranker):
        with patch("rag.reranker._get_diversity_embedder", return_value=mock_embedder):
            result = rerank_with_diversity("tell me about python", docs, top_k=2, diversity_lambda=0.5)

    assert len(result) == 2
    sources = [doc.metadata["source"] for doc, _ in result]
    assert "b.md" in sources  # diverse doc should be selected over similar ones
