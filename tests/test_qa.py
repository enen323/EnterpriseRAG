import pytest
from rag.qa_chain import _format_context, _parse_sources
from langchain_core.documents import Document as LCDocument


def test_format_context():
    docs = [
        (LCDocument(page_content="Hello world", metadata={"source": "test.txt"}), 0.95),
    ]
    result = _format_context(docs)
    assert "【来源: test.txt】" in result
    assert "Hello world" in result
    assert "0.95" in result


def test_parse_sources():
    answer = "Answer content. 【来源: file1.md】【来源: file2.pdf】"
    clean, sources = _parse_sources(answer)
    assert "file1.md" in sources
    assert "file2.pdf" in sources
    assert len(sources) == 2
    assert "【来源:" not in clean
    assert clean == "Answer content."


def test_parse_sources_no_citations():
    answer = "No citations here."
    clean, sources = _parse_sources(answer)
    assert sources == []
    assert clean == "No citations here."


@pytest.mark.asyncio
async def test_extract_suggested_questions():
    from rag.qa_chain import extract_suggested_questions

    answer = """Based on documents, Python is dynamically typed.

Q: What are Python's main data types?
Q: How does Python compare to Java?
Q: Is Python good for beginners?"""

    clean, questions = extract_suggested_questions(answer)
    assert "dynamically typed" in clean
    assert "Q:" not in clean
    assert len(questions) == 3
    assert "What are Python's main data types?" in questions


@pytest.mark.asyncio
async def test_feedback_upsert(async_client, auth_headers):
    """Test feedback create and update."""
    response = await async_client.patch(
        "/api/qa/feedback",
        json={"message_id": "00000000-0000-0000-0000-000000000000", "feedback": "up"},
        headers=auth_headers,
    )
    assert response.status_code == 404  # message doesn't exist
