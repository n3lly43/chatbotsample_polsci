import pytest


def test_build_prompt_includes_anti_hallucination():
    from src.prompts import build_prompt
    prompt = build_prompt("some context", "Test Bot", "testing domain")
    assert "ZERO TOLERANCE" in prompt
    assert "NEVER use your training data" in prompt
    assert "refuse" in prompt.lower()


def test_build_prompt_includes_citation_rules():
    from src.prompts import build_prompt
    prompt = build_prompt("some context", "Test Bot", "testing")
    assert "endnote" in prompt.lower()
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


def test_build_query_understanding_prompt():
    from src.prompts import build_query_understanding_prompt
    prompt = build_query_understanding_prompt(
        "What happened in China?",
        "human rights",
        [{"role": "user", "content": "prior question"}],
    )
    assert "human rights" in prompt
    assert "What happened in China?" in prompt
    assert "prior question" in prompt
    assert "SEARCH" in prompt or "search" in prompt
    assert "CLARIFY" in prompt or "clarify" in prompt


def test_build_query_understanding_prompt_no_history():
    from src.prompts import build_query_understanding_prompt
    prompt = build_query_understanding_prompt("test query", "research", [])
    assert "No prior conversation" in prompt
    assert "test query" in prompt


def test_build_prompt_with_curly_braces_in_context():
    """Braces in context must pass through as single braces, not doubled."""
    from src.prompts import build_prompt
    context = 'JSON data: {"key": "value", "count": 42}'
    prompt = build_prompt(context, "Bot", "testing")
    assert '{"key": "value", "count": 42}' in prompt
    assert '{{"key"' not in prompt  # no double-bracing


def test_build_verification_prompt_with_curly_braces():
    """Braces in response/context must pass through as single braces."""
    from src.prompts import build_verification_prompt
    prompt = build_verification_prompt(
        "The {result} showed improvement.",
        "Data: {raw_value} was recorded.",
        ["flag with {braces}"],
        [],
    )
    assert "{result}" in prompt
    assert "{{result}}" not in prompt  # no double-bracing
    assert "{raw_value}" in prompt
    assert "{braces}" in prompt


def test_qu_prompt_includes_schema_when_provided():
    from src.prompts import build_query_understanding_prompt
    schema_summary = "Available SQL tables:\n- t (100 rows): x (TEXT)"
    prompt = build_query_understanding_prompt(
        "test query", "research", [], sql_schema_summary=schema_summary,
    )
    assert "Available SQL tables" in prompt
    assert "route" in prompt
    assert "sql_query" in prompt


def test_qu_prompt_no_schema_no_sql_fields():
    from src.prompts import build_query_understanding_prompt
    prompt = build_query_understanding_prompt("test query", "research", [])
    assert "Available SQL tables" not in prompt


def test_system_prompt_mentions_chunk_sql():
    from src.prompts import build_prompt
    prompt = build_prompt("context", "Bot", "research")
    assert "CHUNK-SQL" in prompt


def test_verification_prompt_sql_priority():
    from src.prompts import build_verification_prompt
    prompt = build_verification_prompt("resp", "ctx", [], [])
    assert "SQL results" in prompt


def test_qu_prompt_schema_with_curly_braces():
    """Schema text containing {braces} must pass through as single braces."""
    from src.prompts import build_query_understanding_prompt
    schema = "Table t (10 rows):\n  status (TEXT) e.g. \"{N/A}\", \"{pending}\""
    prompt = build_query_understanding_prompt(
        "test query", "research", [], sql_schema_summary=schema,
    )
    assert "{N/A}" in prompt
    assert "{pending}" in prompt
    assert "{{N/A}}" not in prompt  # no double-bracing
    assert "{{{{N/A}}}}" not in prompt  # no quadruple-bracing
