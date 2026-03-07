import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Helper: base config for retrieve() tests
# ---------------------------------------------------------------------------
_BASE_CFG = {
    "sql": {"enabled": True, "max_rows": 200},
    "retrieval": {"top_k": 50, "max_distance": 0.55},
    "web_search": {"enabled": False},
    "paths": {"sql_db": "sql_db"},
}


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


# ---------------------------------------------------------------------------
# Tests for retrieve() SQL fallback logic
# ---------------------------------------------------------------------------

@patch("src.retriever.search", return_value=[])
@patch("src.retriever.retrieve_from_vectordb", return_value=[])
@patch("src.retriever._run_sql_retrieval")
@patch("src.retriever._build_fallback_sql_query")
def test_retrieve_sql_route_llm_query_fails_keyword_fallback_runs(
    mock_build_fallback, mock_run_sql, mock_vectordb, mock_search,
):
    """When route='sql' and LLM sql_query returns nothing, keyword fallback SQL runs."""
    from src.retriever import retrieve

    # First call: LLM sql_query fails (returns empty)
    # Second call: keyword fallback succeeds
    mock_run_sql.side_effect = [
        ([], "", ""),  # LLM-generated query fails
        ([{"col": "val"}], "=== SQL Query Results ===\n[CHUNK-SQL-001] col = val", "fuzzy"),
    ]
    mock_build_fallback.return_value = 'SELECT * FROM "t" WHERE "c" LIKE \'%test%\' LIMIT 200'

    result = retrieve("test data query", _BASE_CFG, route="sql", sql_query="SELECT * FROM t WHERE id=99")

    # Keyword fallback should have been called
    mock_build_fallback.assert_called_once_with("test data query", _BASE_CFG)
    # _run_sql_retrieval called twice: once for LLM query, once for fallback
    assert mock_run_sql.call_count == 2
    assert result["has_sources"] is True
    assert result["sql_results"] == [{"col": "val"}]


@patch("src.retriever.search", return_value=[])
@patch("src.retriever.retrieve_from_vectordb", return_value=[])
@patch("src.retriever._run_sql_retrieval")
@patch("src.retriever._build_fallback_sql_query")
def test_retrieve_sql_route_llm_query_succeeds_no_fallback(
    mock_build_fallback, mock_run_sql, mock_vectordb, mock_search,
):
    """When route='sql' and LLM sql_query returns results, no fallback needed."""
    from src.retriever import retrieve

    mock_run_sql.return_value = (
        [{"country": "CN", "score": 5}],
        "=== SQL Query Results ===\n[CHUNK-SQL-001] country = CN, score = 5",
        "exact",
    )

    result = retrieve("China PTS score", _BASE_CFG, route="sql", sql_query="SELECT * FROM pts WHERE country='CN'")

    # No fallback should be attempted
    mock_build_fallback.assert_not_called()
    # SQL ran once (LLM query succeeded)
    assert mock_run_sql.call_count == 1
    # Vector should NOT have run (route="sql" and sql_rows is non-empty)
    mock_vectordb.assert_not_called()
    assert result["has_sources"] is True
    assert result["sql_results"] == [{"country": "CN", "score": 5}]


@patch("src.retriever.search", return_value=[])
@patch("src.retriever.retrieve_from_vectordb", return_value=[])
@patch("src.retriever._run_sql_retrieval", return_value=([], "", ""))
@patch("src.retriever._build_fallback_sql_query")
def test_retrieve_vector_route_fallback_still_works(
    mock_build_fallback, mock_run_sql, mock_vectordb, mock_search,
):
    """Existing behavior: route='vector', vector empty, keyword SQL fallback runs."""
    from src.retriever import retrieve

    mock_build_fallback.return_value = 'SELECT * FROM "t" WHERE "c" LIKE \'%protest%\' LIMIT 200'

    result = retrieve("protest data", _BASE_CFG, route="vector")

    # Keyword fallback should have been built
    mock_build_fallback.assert_called_once_with("protest data", _BASE_CFG)
    # _run_sql_retrieval called once for the fallback (no LLM query for route="vector")
    assert mock_run_sql.call_count == 1
    # Vector was called (route="vector")
    mock_vectordb.assert_called_once()


@patch("src.retriever.search", return_value=[])
@patch("src.retriever.retrieve_from_vectordb", return_value=[])
@patch("src.retriever._run_sql_retrieval")
@patch("src.retriever._build_fallback_sql_query")
def test_retrieve_both_route_fallback_builds_fresh_query(
    mock_build_fallback, mock_run_sql, mock_vectordb, mock_search,
):
    """When route='both' and LLM sql_query failed, build a fresh keyword query."""
    from src.retriever import retrieve

    # First call: LLM sql_query fails; second call: keyword fallback also fails
    mock_run_sql.return_value = ([], "", "")
    mock_build_fallback.return_value = 'SELECT * FROM "t" WHERE "c" LIKE \'%data%\' LIMIT 200'

    result = retrieve("some data", _BASE_CFG, route="both", sql_query="SELECT * FROM t WHERE x=1")

    # T2-03 fix: _build_fallback_sql_query IS called to build a fresh keyword
    # query instead of re-using the already-failed LLM sql_query
    mock_build_fallback.assert_called_once_with("some data", _BASE_CFG)
    # _run_sql_retrieval called twice: once for LLM query, once for fresh fallback
    assert mock_run_sql.call_count == 2


@patch("src.retriever.search", return_value=[])
@patch("src.retriever.retrieve_from_vectordb", return_value=[])
@patch("src.retriever._run_sql_retrieval")
@patch("src.retriever._build_fallback_sql_query")
def test_retrieve_sql_route_no_sql_query_keyword_fallback_runs(
    mock_build_fallback, mock_run_sql, mock_vectordb, mock_search,
):
    """When route='sql' but no sql_query provided, keyword fallback SQL runs."""
    from src.retriever import retrieve

    mock_run_sql.return_value = (
        [{"col": "val"}],
        "=== SQL Query Results ===\n[CHUNK-SQL-001] col = val",
        "fuzzy",
    )
    mock_build_fallback.return_value = 'SELECT * FROM "t" WHERE "c" LIKE \'%test%\' LIMIT 200'

    result = retrieve("test query", _BASE_CFG, route="sql", sql_query=None)

    # No LLM sql_query → keyword fallback should fire
    mock_build_fallback.assert_called_once()
    assert mock_run_sql.call_count == 1
    assert result["has_sources"] is True
