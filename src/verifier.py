"""
6-Layer Anti-Hallucination Verification Pipeline.

Layers:
    0 — No-source refusal (pre-LLM gate)
    1 — System prompt guardrails (handled by src.prompts)
    2 — Soft max-token cap (proportional to context length)
    3 — LLM-as-verifier (structured JSON audit)
    4 — Semantic similarity cross-check (term-overlap heuristic)
    5 — Warning-phrase scanner (advisory flags)

The main entry point is ``verify_and_respond``.
"""

import json
import re

from src.prompts import build_prompt, build_verification_prompt
from src.llm import generate
from src.retriever import NO_SOURCES_REFUSAL

# ── Layer 5: Warning phrases (advisory, NOT errors) ──────────────────────────

WARNING_PHRASES = [
    "based on my knowledge",
    "generally speaking",
    "it is well known",
    "as we all know",
    "it is widely accepted",
    "common understanding suggests",
    "from what I know",
    "I recall that",
]

# ── Refusal message when verification fails after corrections ─────────────────

REFUSAL_AFTER_VERIFICATION = (
    "I was unable to produce a response that passed verification "
    "against the provided sources. To avoid presenting ungrounded "
    "information, I must decline to answer. Please try rephrasing "
    "your question or adding more relevant documents."
)


# ── Layer 2: Soft max-token cap ───────────────────────────────────────────────

def compute_soft_max_tokens(context_chars: int, default_max: int) -> int:
    """Return a token budget proportional to context length.

    Short context should produce short answers to reduce hallucination
    surface area.

    Args:
        context_chars: Number of characters in the combined context.
        default_max: The configured ``max_tokens`` ceiling.

    Returns:
        An integer token cap: 1024 if context < 500 chars,
        1536 if context < 2000 chars, otherwise *default_max*.
    """
    if context_chars < 500:
        return 1024
    if context_chars < 2000:
        return 1536
    return default_max


# ── Layer 5: Warning-phrase scanner ───────────────────────────────────────────

def scan_warning_phrases(response: str) -> list[dict]:
    """Scan a response for phrases that hint at training-data leakage.

    These are *advisory* flags — they do not constitute errors on their
    own but are forwarded to the LLM verifier for contextual review.

    Args:
        response: The AI-generated text to scan.

    Returns:
        A list of flag dicts, each with keys ``phrase``, ``severity``,
        and ``message``.
    """
    flags: list[dict] = []
    lower = response.lower()
    for phrase in WARNING_PHRASES:
        if phrase in lower:
            flags.append({
                "phrase": phrase,
                "severity": "advisory",
                "message": (
                    f"Phrase '{phrase}' may indicate the model is drawing "
                    f"on training data rather than the provided context."
                ),
            })
    return flags


# ── Layer 4: Similarity cross-check ──────────────────────────────────────────

def compute_similarity_flags(
    response: str, context: str, cfg: dict
) -> list[dict]:
    """Check that cited claims have reasonable term overlap with context.

    For every sentence in *response* that contains a ``[N]`` citation
    marker, we tokenise the sentence and the context into lowercase
    words, then compute the fraction of sentence words that appear
    anywhere in the context.  If the overlap is below 40 %, the claim
    is flagged as potentially ungrounded.

    Args:
        response: AI-generated response text.
        context: The combined retrieval context.
        cfg: Application config (reserved for future threshold tuning).

    Returns:
        A list of advisory flag dicts.
    """
    flags: list[dict] = []
    # Split into sentences (crude but sufficient for flagging)
    sentences = re.split(r"(?<=[.!?])\s+", response)
    citation_pattern = re.compile(r"\[\d+\]")

    # Build a set of context words once
    context_words = set(re.findall(r"[a-z]{3,}", context.lower()))
    if not context_words:
        return flags

    for sentence in sentences:
        if not citation_pattern.search(sentence):
            continue
        # Strip citation markers before tokenising
        clean = citation_pattern.sub("", sentence)
        words = re.findall(r"[a-z]{3,}", clean.lower())
        if not words:
            continue
        overlap = sum(1 for w in words if w in context_words) / len(words)
        if overlap < 0.4:
            flags.append({
                "claim": sentence.strip(),
                "overlap": round(overlap, 2),
                "severity": "advisory",
                "message": (
                    f"Cited claim has only {overlap:.0%} term overlap with "
                    f"context — may be unsupported."
                ),
            })
    return flags


# ── Layer 3 helper: parse LLM verification JSON ──────────────────────────────

def parse_verification_result(raw: str) -> dict:
    """Extract a structured verification dict from raw LLM output.

    Attempts ``json.loads`` first; falls back to regex extraction of a
    JSON object.  If all parsing fails, returns a synthetic *fail*
    result so the pipeline treats unparseable output conservatively.

    Args:
        raw: The raw string returned by the verifier LLM.

    Returns:
        A dict with at least ``errors``, ``error_count``, and ``pass``.
    """
    # Try direct parse
    try:
        result = json.loads(raw)
        if isinstance(result, dict) and "pass" in result:
            return result
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: scan for the first valid JSON object using raw_decode
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch == '{':
            try:
                result, _ = decoder.raw_decode(raw, i)
                if isinstance(result, dict) and "pass" in result:
                    return result
            except json.JSONDecodeError:
                continue

    # Unparseable — fail conservatively
    return {
        "errors": [{"description": "Verification output was not parseable JSON."}],
        "error_count": 1,
        "pass": False,
    }


# ── Main entry point ─────────────────────────────────────────────────────────

def verify_and_respond(
    query: str, retrieval_result: dict, cfg: dict
) -> dict:
    """Generate a response and run it through the 6-layer verification stack.

    Args:
        query: The user's original question.
        retrieval_result: Dict from ``src.retriever.retrieve`` containing
            ``context``, ``db_results``, ``web_results``, ``has_sources``.
        cfg: Full application configuration dict.

    Returns:
        A dict with keys:
        - ``response`` (str): The final text to show the user.
        - ``refused`` (bool): True if the pipeline refused to answer.
        - ``verification_passed`` (bool | None): True/False/None.
        - ``iterations`` (int): Number of verification loops executed.
    """
    # ── Layer 0: No-source refusal (pre-LLM gate) ────────────────────────
    if not retrieval_result.get("has_sources", False):
        return {
            "response": NO_SOURCES_REFUSAL,
            "refused": True,
            "verification_passed": None,
            "iterations": 0,
        }

    context = retrieval_result.get("context", "")
    bot_name = cfg.get("chatbot", {}).get("name", "ResearchBot")
    domain = cfg.get("chatbot", {}).get("domain", "research")
    llm_cfg = cfg.get("llm", {})
    default_max = llm_cfg.get("max_tokens", 2048)

    # ── Load KB overview for general awareness ────────────────────────────
    from src.kb_meta import load_kb_meta
    kb_overview = load_kb_meta(cfg)

    # ── Layer 2: Soft max-token cap ───────────────────────────────────────
    soft_max = compute_soft_max_tokens(len(context), default_max)

    # ── Layer 1: System prompt guardrails (built into prompt) ─────────────
    system_prompt = build_prompt(context, bot_name, domain, kb_overview=kb_overview)

    # ── Generate initial response ─────────────────────────────────────────
    response = generate(system_prompt, query, cfg, max_tokens=soft_max)

    # ── Guard: detect provider-level content blocks ────────────────────────
    if response.startswith("[") and "blocked" in response.lower():
        return {
            "response": (
                "The LLM provider blocked this request due to content "
                "safety filters. Please try rephrasing your question."
            ),
            "refused": True,
            "verification_passed": None,
            "iterations": 0,
        }

    # ── Short-circuit if verification is disabled ─────────────────────────
    verification_cfg = cfg.get("verification", {})
    if not verification_cfg.get("enabled", True):
        return {
            "response": response,
            "refused": False,
            "verification_passed": None,
            "iterations": 0,
        }

    max_iterations = verification_cfg.get("max_iterations", 3)
    strict_mode = verification_cfg.get("strict_mode", True)

    # Guard: max_iterations=0 with enabled=true → skip verification
    if max_iterations <= 0:
        return {
            "response": response,
            "refused": False,
            "verification_passed": None,
            "iterations": 0,
        }

    # ── Verification loop ─────────────────────────────────────────────────
    for iteration in range(1, max_iterations + 1):
        # Layer 5: Warning-phrase scan
        phrase_flags = scan_warning_phrases(response)
        phrase_flag_strs = [f["message"] for f in phrase_flags]

        # Layer 4: Similarity cross-check
        sim_flags = compute_similarity_flags(response, context, cfg)
        sim_flag_strs = [f["message"] for f in sim_flags]

        # Layer 3: LLM-as-verifier
        verification_prompt = build_verification_prompt(
            response, context, phrase_flag_strs, sim_flag_strs,
        )
        raw_verification = generate(
            "You are a strict verification agent. Return only JSON.",
            verification_prompt,
            cfg,
            max_tokens=1024,
        )
        vr = parse_verification_result(raw_verification)

        if vr.get("pass", False):
            return {
                "response": response,
                "refused": False,
                "verification_passed": True,
                "iterations": iteration,
            }

        # Verification failed — attempt correction
        error_count = vr.get("error_count", len(vr.get("errors", [])))

        # Correct and loop for re-verification
        correction_prompt = (
            f"The user's original question was: {query}\n\n"
            f"Your previous response failed verification with "
            f"{error_count} error(s):\n"
            + json.dumps(vr.get("errors", []), indent=2)
            + "\n\nRewrite your response to fix ALL issues. "
            "Use ONLY the provided context. Keep all citation rules."
        )
        response = generate(
            system_prompt, correction_prompt, cfg, max_tokens=soft_max
        )

    # ── Exhausted iterations ──────────────────────────────────────────────
    if strict_mode:
        return {
            "response": REFUSAL_AFTER_VERIFICATION,
            "refused": True,
            "verification_passed": False,
            "iterations": max_iterations,
        }

    # Non-strict: return with a warning
    warning = (
        "\n\n---\n**Note:** This response could not be fully verified "
        "against the provided sources. Some claims may lack adequate "
        "grounding. Please cross-check important facts."
    )
    return {
        "response": response + warning,
        "refused": False,
        "verification_passed": False,
        "iterations": max_iterations,
    }
