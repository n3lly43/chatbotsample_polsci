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
