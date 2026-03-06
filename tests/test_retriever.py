import pytest

def test_format_db_results_as_context_empty():
    from src.retriever import format_db_results_as_context
    assert format_db_results_as_context([]) == ""

def test_format_db_results_as_context_with_chunks():
    from src.retriever import format_db_results_as_context
    chunks = [{
        "text": "Test content here.",
        "metadata": {"source": "Dataset1/paper.pdf", "dataset": "Dataset1", "page": "3"},
        "distance": 0.1,
    }]
    context = format_db_results_as_context(chunks)
    assert "[CHUNK-LOCAL-001]" in context
    assert "paper.pdf" in context
    assert "Test content here." in context
    assert "PRIMARY" in context


def test_format_db_results_no_hardcoded_kb_prefix():
    """M6: Path should use source metadata, not hardcoded 'knowledge_base/' prefix."""
    from src.retriever import format_db_results_as_context
    chunks = [{
        "text": "Content",
        "metadata": {"source": "MyData/report.pdf", "dataset": "MyData", "page": "1"},
        "distance": 0.1,
    }]
    context = format_db_results_as_context(chunks)
    assert "MyData/report.pdf" in context
    assert "knowledge_base/MyData/report.pdf" not in context

def test_build_combined_context_no_sources():
    from src.retriever import build_combined_context
    result = build_combined_context([], [])
    assert "No relevant" in result or "don't have" in result

def test_build_combined_context_local_only():
    from src.retriever import build_combined_context
    db = [{"text": "data", "metadata": {"source": "f.pdf", "dataset": "d", "page": "1"}, "distance": 0.1}]
    result = build_combined_context(db, [])
    assert "ONLY" in result or "local" in result.lower()

def test_build_combined_context_both():
    from src.retriever import build_combined_context
    db = [{"text": "data", "metadata": {"source": "f.pdf", "dataset": "d", "page": "1"}, "distance": 0.1}]
    web = [{"title": "P", "authors": "A", "year": 2020, "abstract": "abs", "url": "http://x", "citation_count": 1, "source_type": "web_search"}]
    result = build_combined_context(db, web)
    assert "PRIMARY" in result
    assert "SUPPLEMENTARY" in result


def test_build_combined_context_with_sql():
    from src.retriever import build_combined_context
    sql = "=== SQL Query Results (PRIMARY) ===\n[CHUNK-SQL-001] x = 1"
    db = [{"text": "data", "metadata": {"source": "f.pdf", "dataset": "d", "page": "1"}, "distance": 0.1}]
    result = build_combined_context(db, [], sql_context=sql)
    assert "SQL Query Results" in result
    assert "CHUNK-LOCAL" in result


def test_build_combined_context_sql_only():
    from src.retriever import build_combined_context
    sql = "=== SQL Query Results (PRIMARY) ===\n[CHUNK-SQL-001] x = 1"
    result = build_combined_context([], [], sql_context=sql)
    assert "SQL Query Results" in result


def test_build_combined_context_sql_no_sources():
    from src.retriever import build_combined_context
    result = build_combined_context([], [], sql_context="")
    assert "No relevant" in result or "don't have" in result


def test_retrieve_from_vectordb_fallback_to_meta():
    """When no chunks pass distance filter, KB meta overview is returned."""
    import chromadb
    from src.kb_meta import META_CHUNK_ID, META_SOURCE, META_DATASET

    client = chromadb.Client()
    collection = client.get_or_create_collection("test_meta_fallback")

    # Add only the meta overview chunk
    collection.add(
        ids=[META_CHUNK_ID],
        documents=["This KB contains PTS data and Amnesty reports."],
        metadatas=[{"source": META_SOURCE, "dataset": META_DATASET, "page": "1", "chunk_index": 0}],
    )

    # Patch get_chroma_collection to return our test collection
    import src.retriever as retriever_mod
    import src.ingest as ingest_mod
    original = ingest_mod.get_chroma_collection

    try:
        ingest_mod.get_chroma_collection = lambda cfg: collection
        # Use a query that won't match well + strict distance threshold
        cfg = {"retrieval": {"top_k": 50, "max_distance": 0.01}}
        chunks = retriever_mod.retrieve_from_vectordb("xyzzy gibberish query", cfg)
        # Meta chunk should be included as fallback
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["source"] == META_SOURCE
    finally:
        ingest_mod.get_chroma_collection = original
        client.delete_collection("test_meta_fallback")
