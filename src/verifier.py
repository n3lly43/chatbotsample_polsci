"""
7-Layer Anti-Hallucination Verification Pipeline.

Layers:
    0 — No-source refusal (pre-LLM gate)
    1 — System prompt guardrails (handled by src.prompts)
    2 — Soft max-token cap (proportional to context length)
    3 — LLM-as-verifier (structured JSON audit)
    4 — Semantic similarity cross-check (term-overlap heuristic)
    4.5 — Deterministic citation audit (validate_citations)
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


def validate_citations(response: str, retrieval_result: dict) -> list[str]:
    """Deterministic citation audit (Layer 4.5).

    Checks that:
    - Citation numbers [N] in the response body don't exceed source count.
    - References section lists source names that match actual retrieved sources.

    Returns a list of warning strings (empty if all checks pass).
    """
    warnings = []

    # Count citable units — each retrieved chunk is a separate citable
    # reference that the LLM may cite as [1], [2], etc.  Counting unique
    # *files* instead would trigger false "fabricated reference" warnings
    # when a single file contributes multiple chunks (e.g., a PDF cited
    # as [1]–[10] for 10 different sections).
    db_results = retrieval_result.get("db_results", [])
    db_count = len(db_results)
    web_count = len(retrieval_result.get("web_results", []))
    sql_count = 1 if retrieval_result.get("sql_results") else 0
    total_sources = db_count + web_count + sql_count

    if total_sources == 0:
        return warnings

    # Extract citation numbers from response BODY only (not References section)
    refs_split = re.split(r'(?im)^#+\s*(?:references|sources)\s*$|^\*\*(?:references|sources)\*\*\s*$', response)
    body_text = refs_split[0] if refs_split else response
    citation_nums = set(int(m) for m in re.findall(r"\[(\d+)\]", body_text))
    if not citation_nums:
        return warnings

    max_citation = max(citation_nums)
    if max_citation > total_sources:
        warnings.append(
            f"Citation [{max_citation}] exceeds available source count "
            f"({total_sources}). Possible fabricated reference."
        )

    # Check that source file names from retrieval appear in the References section
    refs_match = re.search(
        r"(?im)(?:^#+\s*(?:references|sources)\s*$|^\*\*(?:references|sources)\*\*\s*$).*",
        response, re.DOTALL,
    )
    if refs_match:
        refs_text = refs_match.group(0).lower()
        matched_sources = 0
        for chunk in db_results:
            source = chunk.get("metadata", {}).get("source", "")
            if source:
                # Check for filename (last component of path)
                filename = source.rsplit("/", 1)[-1].lower()
                if filename in refs_text:
                    matched_sources += 1
        # Also check SQL source — SQL results are plain row dicts (no
        # metadata wrapper).  All rows come from a single table/source file
        # whose name is embedded in the context as "Source: <filename>".
        # Extract it from the combined context instead of iterating rows.
        sql_results = retrieval_result.get("sql_results", [])
        if sql_results:
            context_text = retrieval_result.get("context", "")
            sql_source_match = re.search(
                r"Source:\s*(.+)", context_text,
            )
            if sql_source_match:
                sql_filename = sql_source_match.group(1).strip().rsplit("/", 1)[-1].lower()
                if sql_filename in refs_text:
                    matched_sources += 1
        # Also check web source URLs — web results are flat dicts with
        # a top-level "url" key (no metadata wrapper).
        web_results = retrieval_result.get("web_results", [])
        for web_chunk in web_results:
            web_url = web_chunk.get("url", "")
            if web_url and web_url.lower() in refs_text:
                matched_sources += 1
        # Only warn when db_results are present and are the primary source
        # and no filenames matched from any source type
        has_any_source = db_results or sql_results or web_results
        if has_any_source and matched_sources == 0 and db_results:
            warnings.append(
                "References section does not mention any filenames from "
                "the retrieved local sources. Citations may be fabricated."
            )

    return warnings


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
    if not raw:
        return {
            "errors": [{"description": "Verification LLM returned no output."}],
            "error_count": 1,
            "pass": False,
        }

    # Try direct parse
    try:
        result = json.loads(raw)
        if isinstance(result, dict) and "pass" in result:
            if not isinstance(result.get("errors"), list):
                result["errors"] = []
            if not isinstance(result.get("error_count"), int):
                result["error_count"] = len(result["errors"])
            result["pass"] = result.get("pass") is True
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
                    if not isinstance(result.get("errors"), list):
                        result["errors"] = []
                    if not isinstance(result.get("error_count"), int):
                        result["error_count"] = len(result["errors"])
                    result["pass"] = result.get("pass") is True
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
    query: str, retrieval_result: dict, cfg: dict,
    original_query: str = "",
) -> dict:
    """Generate a response and run it through the 7-layer verification stack.

    Args:
        query: The display query (reformulated by QU layer).
        retrieval_result: Dict from ``src.retriever.retrieve`` containing
            ``context``, ``db_results``, ``web_results``, ``has_sources``.
        cfg: Full application configuration dict.
        original_query: The user's raw input before QU reformulation.
            Included in the user message so the LLM can cross-check intent.

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

    # ── Load KB overview for general awareness (brief version) ──────────
    from src.kb_meta import load_kb_meta_brief
    kb_overview = load_kb_meta_brief(cfg)

    # ── Layer 2: Soft max-token cap ───────────────────────────────────────
    soft_max = compute_soft_max_tokens(len(context), default_max)

    # ── Layer 1: System prompt guardrails (built into prompt) ─────────────
    system_prompt = build_prompt(context, bot_name, domain, kb_overview=kb_overview)

    # ── Build user message with original query for intent cross-check ────
    if original_query and original_query != query:
        user_message = (
            f"{query}\n\n"
            f"(Original message from the user: \"{original_query}\". "
            f"If the reformulated question above misunderstood the user's "
            f"intent, prioritize answering what the user originally asked.)"
        )
    else:
        user_message = query

    # ── Generate initial response ─────────────────────────────────────────
    try:
        response = generate(system_prompt, user_message, cfg, max_tokens=soft_max)
    except Exception as e:
        return {
            "response": f"An error occurred while generating the response: {e}",
            "refused": True,
            "verification_passed": None,
            "iterations": 0,
        }

    # ── Guard: empty response from LLM ────────────────────────────────────
    if not response or not response.strip():
        return {
            "response": (
                "The AI model was unable to generate a response. "
                "Please try rephrasing your question."
            ),
            "refused": True,
            "verification_passed": False,
            "iterations": 0,
        }

    # ── Guard: detect provider-level content blocks ────────────────────────
    lower_resp = response.lower()
    if (lower_resp.startswith("[gemini blocked")
            or lower_resp.startswith("[gemini error")
            or lower_resp.startswith("[blocked")):
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
        print("WARNING: Verification is disabled (verification.enabled=false). "
              "Responses may contain ungrounded claims.")
        return {
            "response": response,
            "refused": False,
            "verification_passed": None,
            "iterations": 0,
        }

    max_iterations = verification_cfg.get("max_iterations", 3)
    strict_mode = verification_cfg.get("strict_mode", True)

    # Guard: max_iterations=0 with enabled=true → clamp to 1.
    # Verification cannot be bypassed via iteration count alone;
    # users must explicitly set verification.enabled: false.
    if max_iterations <= 0:
        print("WARNING: Verification iterations set to 0 but verification "
              "is enabled. Clamping to 1 iteration. To disable verification, "
              "set verification.enabled: false.")
        max_iterations = 1

    # ── Verification loop ─────────────────────────────────────────────────
    initial_response = response
    any_verification_ran = False  # Track whether ANY verification call succeeded
    for iteration in range(1, max_iterations + 1):
        # Layer 5: Warning-phrase scan
        phrase_flags = scan_warning_phrases(response)
        phrase_flag_strs = [f["message"] for f in phrase_flags]

        # Layer 4: Similarity cross-check
        sim_flags = compute_similarity_flags(response, context, cfg)
        sim_flag_strs = [f["message"] for f in sim_flags]

        # Layer 4.5: Citation audit (recomputed each iteration after corrections)
        citation_warnings = validate_citations(response, retrieval_result)
        citation_flag_strs = citation_warnings if citation_warnings else []

        # Layer 3: LLM-as-verifier
        all_sim_flags = sim_flag_strs + citation_flag_strs
        verification_prompt = build_verification_prompt(
            response, context, phrase_flag_strs, all_sim_flags,
        )
        try:
            raw_verification = generate(
                "You are a strict verification agent. Return only JSON.",
                verification_prompt,
                cfg,
                max_tokens=1024,
            )
        except Exception:
            # Verification LLM failed — skip correction, continue to next iteration
            continue
        any_verification_ran = True
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
        # Truncate previous response to reduce prompt competition with context
        truncated_response = response[:1500] + "..." if len(response) > 1500 else response
        correction_prompt = (
            f"The user's original question was: {query}\n\n"
            f"Your previous response (truncated for brevity):\n{truncated_response}\n\n"
            f"This response failed verification with "
            f"{error_count} error(s):\n"
            + json.dumps(vr.get("errors", []), indent=2)
            + "\n\nRewrite your COMPLETE response from scratch to fix ALL the issues "
            "listed above. Use ONLY the provided context. Keep all citation rules."
        )
        try:
            response = generate(
                system_prompt, correction_prompt, cfg, max_tokens=soft_max
            )
        except Exception:
            break
        # Guard: empty or None correction response
        if not response or not response.strip():
            response = initial_response
            break

    # ── Verify the final correction (last iteration corrected but never verified) ──
    if response != initial_response:
        phrase_flags = scan_warning_phrases(response)
        similarity_flags = compute_similarity_flags(response, context, cfg)
        citation_flags_final = validate_citations(response, retrieval_result)
        all_sim_final = [f["message"] for f in similarity_flags] + citation_flags_final
        vp = build_verification_prompt(
            response, context,
            [f["message"] for f in phrase_flags],
            all_sim_final,
        )
        try:
            vr = parse_verification_result(generate(
                "You are a strict verification agent. Return only JSON.",
                vp, cfg, max_tokens=1024,
            ))
            any_verification_ran = True
        except Exception:
            vr = {"pass": False, "errors": [], "error_count": 0}
        if vr.get("pass", False):
            return {
                "response": response,
                "refused": False,
                "verification_passed": True,
                "iterations": max_iterations,
            }

    # ── Handle total verification system failure ──────────────────────────
    # If ALL verification LLM calls failed (not "didn't pass" — actually
    # failed to run), this is a system failure, not a content-quality issue.
    if not any_verification_ran:
        print("ERROR: All verification LLM calls failed. "
              "Verification could not run at all.")
        if strict_mode:
            return {
                "response": (
                    "Verification was unable to run due to repeated LLM "
                    "errors. To avoid presenting unverified information, "
                    "I must decline to answer. Please check your LLM "
                    "configuration and try again."
                ),
                "refused": True,
                "verification_passed": False,
                "iterations": max_iterations,
            }
        # Non-strict: return with a prominent system-failure warning
        warning = (
            "\n\n---\n**WARNING: Verification system failure.** "
            "The verification pipeline was unable to run due to "
            "repeated LLM errors. This response has NOT been verified "
            "at all — treat all claims as unverified."
        )
        return {
            "response": response + warning,
            "refused": False,
            "verification_passed": False,
            "iterations": max_iterations,
        }

    # ── Exhausted iterations (verification ran but never passed) ──────────
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
    final_citation_warnings = validate_citations(response, retrieval_result)
    if final_citation_warnings:
        warning += "\n**Citation issues:** " + "; ".join(final_citation_warnings)
    return {
        "response": response + warning,
        "refused": False,
        "verification_passed": False,
        "iterations": max_iterations,
    }
