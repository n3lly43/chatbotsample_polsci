"""Query understanding layer: reformulates user queries for better retrieval."""

import json
import os
import re

from src.llm import generate
from src.prompts import build_query_understanding_prompt


def _load_sql_schema_summary(sql_db_dir: str) -> str:
    """Load SQL schema summary from sql_schemas.json if it exists."""
    schema_path = os.path.join(sql_db_dir, "sql_schemas.json")
    if not os.path.exists(schema_path):
        return ""
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        from src.sql_retriever import build_schema_summary
        return build_schema_summary(schema)
    except Exception:
        return ""


def understand_query(
    user_query: str,
    cfg: dict,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Analyze and reformulate a user query for better retrieval.

    Uses the LLM to either:
    - SEARCH: Rewrite the query into a search-optimized form
    - CLARIFY: Ask the user a clarification question

    Args:
        user_query: Raw user input.
        cfg: App config (provides domain, LLM settings).
        conversation_history: Recent messages for pronoun/reference resolution.

    Returns:
        Dict with keys:
        - ``action``: ``"search"`` or ``"clarify"``
        - ``search_query``: Keyword-optimized query for retrieval (always present)
        - ``display_query``: Clear natural-language question for response generation
        - ``original_query``: The raw user input
        - ``clarification_question``: Question to ask (only if action is "clarify")
    """
    qu_cfg = cfg.get("query_understanding", {})

    # Disabled: pass through raw query
    if not qu_cfg.get("enabled", True):
        return {
            "action": "search",
            "search_query": user_query,
            "display_query": user_query,
            "original_query": user_query,
            "route": "vector",
            "sql_query": None,
        }

    domain = cfg.get("chatbot", {}).get("domain", "research")
    max_history = qu_cfg.get("max_history", 6)

    # Trim conversation history
    history = conversation_history or []
    if len(history) > max_history:
        history = history[-max_history:]

    # Load SQL schema summary for prompt injection
    sql_enabled = cfg.get("sql", {}).get("enabled", True)
    schema_summary = ""
    if sql_enabled:
        sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
        if not os.path.isabs(sql_db_dir):
            from pathlib import Path as _Path
            project_root = _Path(__file__).resolve().parent.parent
            sql_db_dir = os.path.join(str(project_root), sql_db_dir)
        schema_summary = _load_sql_schema_summary(sql_db_dir)

    # Load KB meta overview for routing awareness
    from src.kb_meta import load_kb_meta
    kb_overview = load_kb_meta(cfg)

    prompt = build_query_understanding_prompt(
        user_query, domain, history,
        sql_schema_summary=schema_summary,
        kb_overview=kb_overview,
    )

    try:
        raw = generate(
            "You are a query reformulation assistant. Return only JSON.",
            prompt,
            cfg,
            max_tokens=512,
        )
        result = _parse_qu_result(raw, user_query)
    except Exception:
        # LLM failure: fall back to raw query
        result = {
            "action": "search",
            "search_query": user_query,
            "display_query": user_query,
            "original_query": user_query,
            "route": "vector",
            "sql_query": None,
        }

    return result


def _parse_qu_result(raw: str, original_query: str) -> dict:
    """Parse the LLM's JSON response into a structured result.

    Falls back to raw query passthrough if parsing fails.
    """
    parsed = None

    # Try direct parse
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: scan for the first valid JSON object using raw_decode
    if parsed is None:
        decoder = json.JSONDecoder()
        for i, ch in enumerate(raw):
            if ch == '{':
                try:
                    parsed, _ = decoder.raw_decode(raw, i)
                    break
                except json.JSONDecodeError:
                    continue

    # Unparseable: fall back to raw query
    if not isinstance(parsed, dict) or "action" not in parsed:
        return {
            "action": "search",
            "search_query": original_query,
            "display_query": original_query,
            "original_query": original_query,
            "route": "vector",
            "sql_query": None,
        }

    action = parsed.get("action", "search")

    if action == "clarify":
        return {
            "action": "clarify",
            "search_query": original_query,  # fallback if clarification is skipped
            "display_query": original_query,  # fallback if clarification is skipped
            "original_query": original_query,
            "clarification_question": parsed.get(
                "clarification_question", "Could you be more specific?"
            ),
            "route": "vector",
            "sql_query": None,
        }

    # action == "search"
    search_query = parsed.get("search_query", original_query)
    if not isinstance(search_query, str):
        search_query = original_query

    display_query = parsed.get("display_query", original_query)
    if not isinstance(display_query, str):
        display_query = original_query

    route = parsed.get("route", "vector")
    if isinstance(route, str):
        route = route.strip().lower()
    if route not in ("sql", "vector", "both"):
        route = "vector"

    sql_query = parsed.get("sql_query") or None
    if sql_query is not None and not isinstance(sql_query, str):
        sql_query = None
    return {
        "action": "search",
        "search_query": search_query,
        "display_query": display_query,
        "original_query": original_query,
        "route": route,
        "sql_query": sql_query,
    }
