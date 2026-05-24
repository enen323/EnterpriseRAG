import pytest
from rag.memory import ConversationMemory


@pytest.mark.asyncio
async def test_memory_initial_empty():
    memory = ConversationMemory()
    assert memory.get_summary() == ""


@pytest.mark.asyncio
async def test_memory_first_turn():
    memory = ConversationMemory()
    summary = await memory.update_summary("What is RAG?", "RAG is retrieval augmented generation.")
    assert "RAG" in summary
    assert "retrieval" in summary
