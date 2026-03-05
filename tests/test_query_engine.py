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
    assert result["original_query"] == "test query"


def test_understand_query_clarifies():
    from src.query_engine import understand_query
    with patch("src.query_engine.generate", _mock_generate_clarify):
        result = understand_query("AI", _make_cfg())
    assert result["action"] == "clarify"
    assert "clarification_question" in result
    assert result["original_query"] == "AI"
    # search_query should still be present as fallback
    assert "search_query" in result


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
    assert result["original_query"] == "test query"


def test_understand_query_fallback_on_error():
    from src.query_engine import understand_query
    with patch("src.query_engine.generate", _mock_generate_error):
        result = understand_query("test query", _make_cfg())
    assert result["action"] == "search"
    assert result["search_query"] == "test query"


def test_parse_qu_result_malformed_json():
    from src.query_engine import _parse_qu_result
    result = _parse_qu_result("not json at all", "original query")
    assert result["action"] == "search"
    assert result["search_query"] == "original query"


def test_parse_qu_result_embedded_json():
    from src.query_engine import _parse_qu_result
    raw = 'Here is the result: {"action": "search", "search_query": "better query", "reasoning": "test"} end'
    result = _parse_qu_result(raw, "original")
    assert result["action"] == "search"
    assert result["search_query"] == "better query"
