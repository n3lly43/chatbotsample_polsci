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


def test_ingest_clamps_overlap_when_gte_chunk_size(tmp_path, capsys):
    """Overlap >= chunk_size must be clamped to prevent explosive chunk generation."""
    from src.ingest import ingest_documents

    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    (kb_dir / "notes.txt").write_text("Hello world. " * 100)

    cfg = {
        "paths": {
            "knowledge_base": str(kb_dir),
            "vector_db": str(tmp_path / "chroma_db"),
            "sql_db": str(tmp_path / "sql_db"),
        },
        "retrieval": {"chunk_size": 100, "chunk_overlap": 200},  # overlap > chunk_size
        "embeddings": {"provider": "local"},
        "sql": {"enabled": False},
    }
    count = ingest_documents(cfg, documents_dir=str(kb_dir))
    assert count > 0
    captured = capsys.readouterr()
    assert "Warning: chunk_overlap >= chunk_size" in captured.out
    # Verify we didn't get an explosive number of chunks
    assert count < 100


def test_ingest_deferred_clear_preserves_data_on_total_failure(tmp_path):
    """M2: If all file reads fail, existing data must NOT be cleared."""
    from src.ingest import ingest_documents, get_chroma_collection

    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()

    cfg = {
        "paths": {
            "knowledge_base": str(kb_dir),
            "vector_db": str(tmp_path / "chroma_db"),
            "sql_db": str(tmp_path / "sql_db"),
        },
        "retrieval": {"chunk_size": 1000, "chunk_overlap": 100},
        "embeddings": {"provider": "local"},
        "sql": {"enabled": False},
    }

    # First ingestion: add a real file
    (kb_dir / "good.txt").write_text("Existing important data. " * 20)
    count1 = ingest_documents(cfg, documents_dir=str(kb_dir))
    assert count1 > 0

    # Verify data exists
    col = get_chroma_collection(cfg)
    before_count = col.count()
    assert before_count > 0

    # Remove the good file, add only an unreadable file
    (kb_dir / "good.txt").unlink()
    bad_file = kb_dir / "corrupt.pdf"
    bad_file.write_bytes(b"not a real pdf")

    # Second ingestion: all reads should fail
    count2 = ingest_documents(cfg, documents_dir=str(kb_dir))
    assert count2 == 0

    # Existing data should be preserved (deferred clearing)
    col2 = get_chroma_collection(cfg)
    after_count = col2.count()
    assert after_count == before_count


def test_ingest_preserves_subdirectory_paths(tmp_path):
    """Source names must preserve full relative path, not just dataset/filename."""
    from src.ingest import ingest_documents

    kb_dir = tmp_path / "knowledge_base"
    sub = kb_dir / "DS" / "subdir"
    sub.mkdir(parents=True)
    (sub / "notes.txt").write_text("Nested file content.")

    cfg = {
        "paths": {
            "knowledge_base": str(kb_dir),
            "vector_db": str(tmp_path / "chroma_db"),
            "sql_db": str(tmp_path / "sql_db"),
        },
        "retrieval": {"chunk_size": 1000, "chunk_overlap": 100},
        "embeddings": {"provider": "local"},
        "sql": {"enabled": False},
    }
    count = ingest_documents(cfg, documents_dir=str(kb_dir))
    assert count > 0

    from src.ingest import get_chroma_collection
    col = get_chroma_collection(cfg)
    data = col.get(include=["metadatas"])
    sources = [m["source"] for m in data["metadatas"]
               if m.get("source") != "Knowledge Base Overview"]
    # Should be "DS/subdir/notes.txt", not "DS/notes.txt"
    assert any("subdir" in s for s in sources)
