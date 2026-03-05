import pytest


def test_split_text_recursive_short():
    """Short text returns as single chunk."""
    from src.ingest import split_text_recursive
    chunks = split_text_recursive("Hello world", 1000, 100)
    assert chunks == ["Hello world"]


def test_split_text_recursive_long():
    """Long text is split into overlapping chunks."""
    from src.ingest import split_text_recursive
    text = "Paragraph one. " * 100 + "\n\n" + "Paragraph two. " * 100
    chunks = split_text_recursive(text, 500, 50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 600  # allow some overflow at boundaries


def test_chunk_documents():
    """Pages are chunked with correct metadata."""
    from src.ingest import chunk_documents
    pages = [{"page": 1, "text": "A short page of text."}]
    chunks = chunk_documents(pages, "test.pdf", "general")
    assert len(chunks) >= 1
    assert chunks[0]["metadata"]["source"] == "test.pdf"
    assert chunks[0]["metadata"]["dataset"] == "general"


def test_discover_files(tmp_path):
    """discover_files finds supported files recursively."""
    from src.ingest import discover_files

    # Create test files
    sub = tmp_path / "Dataset1"
    sub.mkdir()
    (sub / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
    (sub / "data.csv").write_text("a,b\n1,2\n")
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "photo.jpg").write_bytes(b"fake jpg")  # unsupported

    files = discover_files(str(tmp_path))
    extensions = {f[0].suffix for f in files}
    assert ".pdf" in extensions
    assert ".csv" in extensions
    assert ".txt" in extensions
    assert ".jpg" not in extensions

    # Check dataset names
    datasets = {f[1] for f in files}
    assert "Dataset1" in datasets
    assert "general" in datasets
