import json
import pytest
from unittest.mock import patch


def _make_cfg(enabled=True, max_history=6, max_clarifications=1):
    """Build a minimal config dict for query engine tests."""
    return {
        "chatbot": {"name": "TestBot", "domain": "human rights research"},
        "llm": {"provider": "openai", "model": "gpt-4o", "temperature": 0.0, "max_tokens": 2048},
        "api_keys": {"openai": "fake-key"},
        "query_understanding": {
            "enabled": enabled,
            "max_history": max_history,
            "max_clarifications": max_clarifications,
        },
    }


def _mock_generate_search(system_prompt, user_message, cfg, **kwargs):
    """Mock LLM that always returns a search reformulation."""
    return json.dumps({
        "action": "search",
        "search_query": "reformulated test query about human rights",
        "display_query": "What are the key human rights issues in this test query?",
        "reasoning": "expanded for better retrieval",
    })


def _mock_generate_clarify(system_prompt, user_message, cfg, **kwargs):
    """Mock LLM that always returns a clarification request."""
    return json.dumps({
        "action": "clarify",
        "clarification_question": "Are you asking about X or Y?",
        "reasoning": "ambiguous query",
    })


def _mock_generate_error(system_prompt, user_message, cfg, **kwargs):
    """Mock LLM that raises an exception."""
    raise RuntimeError("LLM unavailable")


def test_understand_query_reformulates():
    from src.query_engine import understand_query
    with patch("src.query_engine.generate", _mock_generate_search):
        result = understand_query("test query", _make_cfg())
    assert result["action"] == "search"
    assert result["search_query"] == "reformulated test query about human rights"
    assert result["display_query"] == "What are the key human rights issues in this test query?"
    assert result["original_query"] == "test query"


def test_understand_query_clarifies():
    from src.query_engine import understand_query
    with patch("src.query_engine.generate", _mock_generate_clarify):
        result = understand_query("AI", _make_cfg())
    assert result["action"] == "clarify"
    assert "clarification_question" in result
    assert result["original_query"] == "AI"
    # search_query and display_query should still be present as fallback
    assert "search_query" in result
    assert "display_query" in result


def test_understand_query_preserves_original():
    from src.query_engine import understand_query
    original = "What happened in China?"
    with patch("src.query_engine.generate", _mock_generate_search):
        result = understand_query(original, _make_cfg())
    assert result["original_query"] == original


def test_understand_query_with_history():
    from src.query_engine import understand_query
    history = [
        {"role": "user", "content": "Tell me about China"},
        {"role": "assistant", "content": "China has various human rights issues..."},
    ]
    with patch("src.query_engine.generate", _mock_generate_search):
        result = understand_query("what about 2023?", _make_cfg(), history)
    assert result["action"] == "search"


def test_understand_query_disabled():
    from src.query_engine import understand_query
    result = understand_query("test query", _make_cfg(enabled=False))
    assert result["action"] == "search"
    assert result["search_query"] == "test query"
    assert result["display_query"] == "test query"
    assert result["original_query"] == "test query"


def test_understand_query_fallback_on_error():
    from src.query_engine import understand_query
    with patch("src.query_engine.generate", _mock_generate_error):
        result = understand_query("test query", _make_cfg())
    assert result["action"] == "search"
    assert result["search_query"] == "test query"
    assert result["display_query"] == "test query"


def test_parse_qu_result_malformed_json():
    from src.query_engine import _parse_qu_result
    result = _parse_qu_result("not json at all", "original query")
    assert result["action"] == "search"
    assert result["search_query"] == "original query"
    assert result["display_query"] == "original query"


def test_parse_qu_result_embedded_json():
    from src.query_engine import _parse_qu_result
    raw = 'Here is the result: {"action": "search", "search_query": "better query", "reasoning": "test"} end'
    result = _parse_qu_result(raw, "original")
    assert result["action"] == "search"
    assert result["search_query"] == "better query"
    # display_query falls back to original when not in JSON
    assert result["display_query"] == "original"


def test_parse_qu_result_with_display_query():
    from src.query_engine import _parse_qu_result
    raw = json.dumps({
        "action": "search",
        "search_query": "keyword optimized query",
        "display_query": "What is the effect of AI on human rights?",
        "reasoning": "clarified and expanded",
    })
    result = _parse_qu_result(raw, "AI human rights")
    assert result["search_query"] == "keyword optimized query"
    assert result["display_query"] == "What is the effect of AI on human rights?"
    assert result["original_query"] == "AI human rights"


def test_parse_qu_result_with_route_and_sql():
    from src.query_engine import _parse_qu_result
    raw = '{"action": "search", "route": "sql", "search_query": "PTS China", "display_query": "PTS scores for China?", "sql_query": "SELECT * FROM t", "reasoning": "data lookup"}'
    result = _parse_qu_result(raw, "original")
    assert result["route"] == "sql"
    assert result["sql_query"] == "SELECT * FROM t"


def test_parse_qu_result_defaults_route_to_vector():
    from src.query_engine import _parse_qu_result
    raw = '{"action": "search", "search_query": "test", "display_query": "test?"}'
    result = _parse_qu_result(raw, "original")
    assert result["route"] == "vector"
    assert result.get("sql_query") is None


def test_parse_qu_result_normalizes_route_case():
    """Bug: LLM returning uppercase route like 'SQL' was silently ignored."""
    from src.query_engine import _parse_qu_result
    raw = '{"action": "search", "route": "SQL", "search_query": "q", "display_query": "q?", "sql_query": "SELECT 1"}'
    result = _parse_qu_result(raw, "q")
    assert result["route"] == "sql"
    assert result["sql_query"] == "SELECT 1"


def test_parse_qu_result_strips_route_whitespace():
    """Bug: LLM returning route with trailing whitespace was silently ignored."""
    from src.query_engine import _parse_qu_result
    raw = '{"action": "search", "route": "both ", "search_query": "q", "display_query": "q?", "sql_query": "SELECT 1"}'
    result = _parse_qu_result(raw, "q")
    assert result["route"] == "both"
    assert result["sql_query"] == "SELECT 1"


def test_load_sql_schema_missing_file():
    from src.query_engine import _load_sql_schema_summary
    result = _load_sql_schema_summary("/nonexistent/path/sql_db")
    assert result == ""


def test_load_sql_schema_valid_file(tmp_path):
    import json
    from src.query_engine import _load_sql_schema_summary
    schema_dir = tmp_path / "sql_db"
    schema_dir.mkdir()
    schema = {
        "test_table": {
            "source_file": "data.csv",
            "columns": [{"name": "x", "type": "TEXT", "sample": ["a"]}],
            "row_count": 10,
        }
    }
    (schema_dir / "sql_schemas.json").write_text(json.dumps(schema))
    result = _load_sql_schema_summary(str(schema_dir))
    assert "test_table" in result
    assert "10 rows" in result
