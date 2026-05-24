from unittest.mock import patch, MagicMock

import numpy as np
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
