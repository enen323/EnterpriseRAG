import pytest
from rag.qa_chain import _format_context, _parse_sources
from langchain.schema import Document as LCDocument


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
