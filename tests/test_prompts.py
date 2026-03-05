import pytest


def test_build_prompt_includes_anti_hallucination():
    from src.prompts import build_prompt
    prompt = build_prompt("some context", "Test Bot", "testing domain")
    assert "ZERO TOLERANCE" in prompt
    assert "NEVER use your training data" in prompt
    assert "REFUSE" in prompt


def test_build_prompt_includes_citation_rules():
    from src.prompts import build_prompt
    prompt = build_prompt("some context", "Test Bot", "testing")
    assert "[N]" in prompt or "endnote" in prompt.lower()
    assert "References" in prompt
    assert "direct quote" in prompt.lower() or "Direct quote" in prompt


def test_build_prompt_includes_context():
    from src.prompts import build_prompt
    prompt = build_prompt("MY_UNIQUE_CONTEXT_STRING", "Bot", "domain")
    assert "MY_UNIQUE_CONTEXT_STRING" in prompt


def test_build_prompt_includes_bot_identity():
    from src.prompts import build_prompt
    prompt = build_prompt("ctx", "ResearchHelper", "political science")
    assert "ResearchHelper" in prompt
    assert "political science" in prompt


def test_build_verification_prompt():
    from src.prompts import build_verification_prompt
    prompt = build_verification_prompt("response text", "context text", [], [])
    assert "citation" in prompt.lower()
    assert "JSON" in prompt or "json" in prompt
    assert "error_count" in prompt
