import pytest
from rag.document_loader import load_document, split_documents


def test_load_txt(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Hello world. This is a test document.")
    docs = load_document(str(f))
    assert len(docs) == 1
    assert "Hello world" in docs[0].page_content
    assert docs[0].metadata["source"] == "test.txt"


def test_load_md(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("# Title\n\nSome markdown content.")
    docs = load_document(str(f))
    assert len(docs) == 1
    assert "Title" in docs[0].page_content


def test_split_documents(tmp_path):
    f = tmp_path / "split_test.txt"
    f.write_text("A. " * 1000)
    docs = load_document(str(f))
    chunks = split_documents(docs)
    assert len(chunks) > 1
    assert all(len(c.page_content) <= 512 for c in chunks)


def test_unsupported_type(tmp_path):
    f = tmp_path / "test.xyz"
    f.write_text("content")
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_document(str(f))
