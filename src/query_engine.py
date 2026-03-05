"""Query understanding layer: reformulates user queries for better retrieval."""

import json
import re

from src.llm import generate
from src.prompts import build_query_understanding_prompt


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
        - ``search_query``: Reformulated query (always present)
        - ``original_query``: The raw user input
        - ``clarification_question``: Question to ask (only if action is "clarify")
    """
    qu_cfg = cfg.get("query_understanding", {})

    # Disabled: pass through raw query
    if not qu_cfg.get("enabled", True):
        return {
            "action": "search",
            "search_query": user_query,
            "original_query": user_query,
        }

    domain = cfg.get("chatbot", {}).get("domain", "research")
    max_history = qu_cfg.get("max_history", 6)

    # Trim conversation history
    history = conversation_history or []
    if len(history) > max_history:
        history = history[-max_history:]

    prompt = build_query_understanding_prompt(user_query, domain, history)

    try:
        raw = generate(
            "You are a query reformulation assistant. Return only JSON.",
            prompt,
            cfg,
            max_tokens=256,
        )
        result = _parse_qu_result(raw, user_query)
    except Exception:
        # LLM failure: fall back to raw query
        result = {
            "action": "search",
            "search_query": user_query,
            "original_query": user_query,
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

    # Regex fallback: find first { ... } block
    if parsed is None:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                parsed = json.loads(match.group())
            except (json.JSONDecodeError, TypeError):
                pass

    # Unparseable: fall back to raw query
    if not isinstance(parsed, dict) or "action" not in parsed:
        return {
            "action": "search",
            "search_query": original_query,
            "original_query": original_query,
        }

    action = parsed.get("action", "search")

    if action == "clarify":
        return {
            "action": "clarify",
            "search_query": original_query,  # fallback if clarification is skipped
            "original_query": original_query,
            "clarification_question": parsed.get(
                "clarification_question", "Could you be more specific?"
            ),
        }

    # action == "search"
    return {
        "action": "search",
        "search_query": parsed.get("search_query", original_query),
        "original_query": original_query,
    }
