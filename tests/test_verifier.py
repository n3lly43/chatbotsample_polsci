import pytest
import json

def test_scan_warning_phrases_clean():
    from src.verifier import scan_warning_phrases
    flags = scan_warning_phrases("The data shows a 53% success rate. [1]")
    assert flags == []

def test_scan_warning_phrases_flagged():
    from src.verifier import scan_warning_phrases
    flags = scan_warning_phrases("It is well known that nonviolent movements work.")
    assert len(flags) == 1
    assert flags[0]["severity"] == "advisory"

def test_compute_soft_max_tokens():
    from src.verifier import compute_soft_max_tokens
    assert compute_soft_max_tokens(100, 2048) == 1024
    assert compute_soft_max_tokens(1500, 2048) == 1536
    assert compute_soft_max_tokens(5000, 2048) == 2048

def test_parse_verification_result_pass():
    from src.verifier import parse_verification_result
    json_str = '{"errors": [], "error_count": 0, "pass": true}'
    result = parse_verification_result(json_str)
    assert result["pass"] is True
    assert result["error_count"] == 0

def test_parse_verification_result_fail():
    from src.verifier import parse_verification_result
    json_str = json.dumps({
        "errors": [{"claim": "test", "issue": "not found in sources"}],
        "error_count": 1, "pass": False,
    })
    result = parse_verification_result(json_str)
    assert result["pass"] is False
    assert result["error_count"] == 1

def test_parse_verification_result_malformed():
    from src.verifier import parse_verification_result
    result = parse_verification_result("not json at all")
    assert result["pass"] is False

def test_gemini_blocked_response_returns_refusal():
    """Provider-level content blocks must short-circuit verification."""
    from unittest.mock import patch
    from src.verifier import verify_and_respond

    def mock_generate(system_prompt, user_message, cfg, **kwargs):
        return "[Gemini blocked: response filtered by safety settings]"

    retrieval_result = {
        "context": "some context here",
        "db_results": [{"text": "chunk"}],
        "web_results": [],
        "has_sources": True,
    }
    cfg = {
        "llm": {"provider": "gemini", "model": "gemini-2.5-flash",
                "temperature": 0.0, "max_tokens": 2048},
        "api_keys": {"gemini": "fake"},
        "verification": {"enabled": True, "max_iterations": 3, "strict_mode": True},
        "chatbot": {"name": "Test", "domain": "test"},
        "paths": {"vector_db": "/nonexistent"},
    }
    with patch("src.verifier.generate", mock_generate), \
         patch("src.kb_meta.load_kb_meta", return_value=""):
        result = verify_and_respond("test query", retrieval_result, cfg)
    assert result["refused"] is True
    assert "blocked" in result["response"].lower() or "safety" in result["response"].lower()
    assert result["iterations"] == 0


def test_max_iterations_zero_skips_verification():
    """M4: max_iterations=0 with enabled=true must return response, not refuse."""
    from unittest.mock import patch
    from src.verifier import verify_and_respond

    def mock_generate(system_prompt, user_message, cfg, **kwargs):
        return "Some grounded response. [1]"

    retrieval_result = {
        "context": "some context here",
        "db_results": [{"text": "chunk"}],
        "web_results": [],
        "has_sources": True,
    }
    cfg = {
        "llm": {"provider": "openai", "model": "gpt-4o",
                "temperature": 0.0, "max_tokens": 2048},
        "api_keys": {"openai": "fake"},
        "verification": {"enabled": True, "max_iterations": 0, "strict_mode": True},
        "chatbot": {"name": "Test", "domain": "test"},
        "paths": {"vector_db": "/nonexistent"},
    }
    with patch("src.verifier.generate", mock_generate), \
         patch("src.kb_meta.load_kb_meta", return_value=""):
        result = verify_and_respond("test query", retrieval_result, cfg)
    assert result["refused"] is False
    assert result["verification_passed"] is None
    assert result["iterations"] == 0
    assert "grounded response" in result["response"]


def test_no_sources_returns_refusal():
    from src.verifier import verify_and_respond
    result = verify_and_respond(
        query="test",
        retrieval_result={"context": "", "db_results": [], "web_results": [], "has_sources": False},
        cfg={"llm": {"provider": "openai", "model": "gpt-4o", "temperature": 0.0, "max_tokens": 2048},
             "api_keys": {"openai": "fake"},
             "verification": {"enabled": True, "max_iterations": 3, "strict_mode": True},
             "chatbot": {"name": "Test", "domain": "test"}},
    )
    assert result["refused"] is True
    assert "don't have any information" in result["response"]
