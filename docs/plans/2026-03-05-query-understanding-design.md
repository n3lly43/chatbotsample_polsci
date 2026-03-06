# Query Understanding Layer — Design Document

**Date:** 2026-03-05
**Author:** Jie Lian (with Claude)
**Status:** Approved & Implemented

## 1. Problem

Short, vague, or ambiguous user queries produce poor retrieval results. Examples:

| User Query | Problem | What Retrieval Needs |
|---|---|---|
| "China in 2024?" | Too short, embedding doesn't match long document chunks | "China human rights situation developments 2024" |
| "what about 2023?" | Missing context from prior conversation | "China human rights 2023" (from conversation history) |
| "AI stuff" | Vague | Clarification: "Are you asking about AI surveillance, AI in governance, or AI and civil resistance?" |
| "How did they respond?" | Pronouns unresolved | Needs prior context to resolve "they" |

The current pipeline passes the raw user query directly to ChromaDB embedding search. Short/vague queries produce weak embeddings that miss relevant chunks even when the knowledge base has the answer.

## 2. Solution: Query Understanding Layer

Add a pre-retrieval step that uses the LLM to:

1. **Reformulate** — Rewrite the query into a search-optimized form (expanded, keyword-rich, domain-aware)
2. **Clarify** — When the query is genuinely ambiguous, ask the user a targeted question before searching

### Pipeline Change

```
BEFORE:
User query → retrieve(query) → verify_and_respond(query, results) → Display

AFTER:
User query → understand_query(query, history, cfg)
    → [if CLARIFY: ask user, get answer, call understand_query again]
    → [if SEARCH: use reformulated query for retrieval]
    → retrieve(reformulated_query) → verify_and_respond(original_query, results) → Display
```

**Key principle — Dual-query output:** The QU layer produces three queries:
- `search_query`: keyword-optimized for vector retrieval → passed to `retrieve()`
- `display_query`: clear, complete natural-language question (incorporates clarification context) → passed to `verify_and_respond()`
- `original_query`: raw user input, preserved for reference/logging

After clarification, `display_query` is a well-formed question that gives the response LLM better context to generate a relevant answer (e.g., "What are the key findings on AI surveillance in China?" instead of the vague "tell me about that").

## 3. New Module: `src/query_engine.py`

### 3.1 Function Signature

```python
def understand_query(
    user_query: str,
    cfg: dict,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Analyze and reformulate a user query for better retrieval.

    Args:
        user_query: Raw user input.
        cfg: App config (provides domain, LLM settings).
        conversation_history: List of {"role": "user"|"assistant", "content": "..."}
            from the current session. Used to resolve pronouns/references.

    Returns:
        {
            "action": "search" | "clarify",
            "search_query": "keyword-optimized query for vector retrieval",
            "display_query": "clear natural-language question for response LLM",
            "original_query": "user's original text",
            "clarification_question": "..." (only if action == "clarify"),
        }
    """
```

### 3.2 LLM Prompt

```
You are a query reformulation assistant for a {domain} research chatbot.

Your job is to analyze the user's question and decide:
1. SEARCH — if the question is clear enough, rewrite it as an optimized search query
2. CLARIFY — if the question is genuinely ambiguous, ask ONE clarification question

RULES for SEARCH:
- Expand abbreviations and acronyms (e.g., "HR" → "human rights")
- Resolve pronouns using conversation history (e.g., "they" → the entity from prior turn)
- Add relevant domain-specific keywords that would match document content
- Keep the reformulated query concise (15-40 words)
- Preserve the user's original intent — do NOT change what they're asking about
- If the query is already clear and specific, return it with minimal changes

RULES for CLARIFY:
- ONLY ask for clarification when the question is genuinely ambiguous
  (could mean 2+ clearly different things)
- Ask ONE specific, short question
- Provide 2-3 options when possible
- Do NOT ask for clarification on clear questions — even if they are broad
- A broad question is NOT the same as an ambiguous question

CONVERSATION HISTORY:
{history}

USER'S QUESTION: {query}

Respond in JSON:
{
  "action": "search" or "clarify",
  "search_query": "keyword-optimized query for vector search" (only if action is "search"),
  "display_query": "clear natural-language question for the AI to answer" (only if action is "search"),
  "clarification_question": "question to ask" (only if action is "clarify"),
  "reasoning": "one sentence explaining your choice"
}
```

### 3.3 Clarification Threshold

The LLM should have a HIGH bar for asking clarification. Most queries should be reformulated directly, not clarified. Clarification is only for genuinely ambiguous cases. Examples:

| Query | Action | Why |
|---|---|---|
| "China" | SEARCH → "China human rights developments" | Broad but not ambiguous — search and let the user refine |
| "AI" | CLARIFY → "Are you asking about AI surveillance technology, AI in governance, or AI and civil resistance?" | Genuinely ambiguous in a domain that covers all of these |
| "what about 2023?" | SEARCH → "China human rights 2023" (from history) | Pronoun resolved from conversation context |
| "How effective is NVR?" | SEARCH → "effectiveness nonviolent resistance campaigns success rate" | Abbreviation expanded, terms added |

### 3.4 Conversation History

The query engine receives the last N turns of conversation (default: last 3 user-assistant pairs = 6 messages). This lets it resolve:

- Pronouns: "they", "it", "that"
- Follow-ups: "what about 2023?", "and in Asia?"
- Refinements: "more detail on the third point"

The history is passed as text in the prompt, NOT as separate LLM conversation turns (cheaper, simpler).

## 4. Integration Points

### 4.1 CLI (`app_cli.py`)

```python
# In the main loop, before retrieve():
from src.query_engine import understand_query

# Build conversation history from state
history = state.get("conversation_history", [])

# Query understanding
qu_result = understand_query(user_input, effective_cfg, history)

if qu_result["action"] == "clarify":
    # Show clarification question
    console.print(f"\n[bold yellow]Clarification needed:[/bold yellow] {qu_result['clarification_question']}")
    try:
        clarification = input("You> ").strip()
    except (EOFError, KeyboardInterrupt):
        continue
    if not clarification:
        continue
    # Re-run with clarification appended
    combined = f"{user_input} — {clarification}"
    qu_result = understand_query(combined, effective_cfg, history)

# Use search_query for retrieval, display_query for response generation
search_query = qu_result["search_query"]
display_query = qu_result["display_query"]

retrieval_result = retrieve(search_query, effective_cfg)
result = verify_and_respond(display_query, retrieval_result, effective_cfg)

# Update conversation history
history.append({"role": "user", "content": user_input})
history.append({"role": "assistant", "content": result["response"]})
# Keep last 6 messages (3 turns)
state["conversation_history"] = history[-6:]
```

### 4.2 Web UI (`app_web.py`)

```python
# In render_chat(), before retrieve():
from src.query_engine import understand_query

history = [
    {"role": m["role"], "content": m["content"]}
    for m in st.session_state.messages[-6:]
]

qu_result = understand_query(prompt, cfg, history)

if qu_result["action"] == "clarify":
    # Show clarification as assistant message
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"**Before I search, could you clarify?** {qu_result['clarification_question']}"
    })
    st.rerun()
    return  # Wait for user's next input as clarification

# Use search_query for retrieval, display_query for response
retrieval_result = retrieve(qu_result["search_query"], cfg)
result = verify_and_respond(qu_result["display_query"], retrieval_result, cfg)
```

### 4.3 Status Display

Show the reformulated query to the user so they understand what was searched:

**CLI:**
```
[dim]Searching for: "China human rights situation developments 2024"[/dim]
```

**Web UI:**
```
Status: Searching for "China human rights situation developments 2024"...
```

This is important for transparency — the user should know how their query was interpreted.

## 5. Config

New section in `config.yaml`:

```yaml
query_understanding:
  enabled: true          # set to false to skip reformulation (use raw query)
  max_history: 6         # number of recent messages to include as context
  max_clarifications: 1  # max clarification rounds before forcing a search
```

Default: enabled. Can be disabled for users who want raw pass-through behavior.

### Setup Wizard Addition

No new wizard step needed — `query_understanding` defaults to enabled. Advanced users can disable in `config.yaml`.

The setup wizard's `generate_config()` adds:

```python
"query_understanding": {
    "enabled": True,
    "max_history": 6,
    "max_clarifications": 1,
},
```

## 6. Cost Analysis

| Component | LLM Calls Before | LLM Calls After |
|---|---|---|
| Query understanding | 0 | 1 (small, ~100 tokens out) |
| Response generation | 1 | 1 (unchanged) |
| Verification | 1-3 | 1-3 (unchanged) |
| Clarification | 0 | 0-1 (only when ambiguous) |
| **Total** | **2-4** | **3-5** |

The query understanding call is cheap: short prompt, short response (~100 tokens). The improved retrieval quality is worth the extra call.

## 7. Anti-Hallucination Impact

**No weakening.** The query understanding layer operates BEFORE retrieval and does NOT affect the 6-layer verification stack:

- Layer 0 (no-source gate): Still works — if reformulated query finds nothing, LLM is never called
- Layer 1-5: Unchanged — the response is still verified against retrieved sources
- The `display_query` is a clear natural-language question — it helps the response LLM understand what to answer, but doesn't bypass any verification. The 6-layer stack still checks every claim against the retrieved context.

## 8. Edge Cases

| Case | Handling |
|---|---|
| Query understanding disabled | Skip entirely, use raw query (current behavior) |
| LLM call fails | Fall back to raw query, log warning |
| Clarification on first message (no history) | Works fine — history is empty |
| User skips clarification (empty input) | Skip, use raw query |
| Very long query (paragraph) | Still reformulate — LLM extracts the core question |
| Multi-part question | LLM reformulates the primary question; may suggest focusing |

## 9. Files to Create/Modify

| File | Action | Description |
|---|---|---|
| `src/query_engine.py` | **CREATE** | Query understanding module |
| `src/prompts.py` | **MODIFY** | Add `QUERY_UNDERSTANDING_PROMPT_TEMPLATE` and `build_query_understanding_prompt()` |
| `app_cli.py` | **MODIFY** | Add query understanding step + conversation history + clarification flow |
| `app_web.py` | **MODIFY** | Add query understanding step + clarification flow |
| `setup.py` | **MODIFY** | Add `query_understanding` config defaults |
| `tests/test_query_engine.py` | **CREATE** | Tests for query engine |
| `tests/test_prompts.py` | **MODIFY** | Test for new prompt template |

## 10. Test Plan

1. `test_understand_query_reformulates` — Clear query returns action="search" with `search_query` and `display_query`
2. `test_understand_query_clarifies` — Ambiguous query returns action="clarify" with fallback `display_query`
3. `test_understand_query_preserves_original` — `original_query` always in result
4. `test_understand_query_with_history` — Pronoun resolution using conversation history
5. `test_understand_query_disabled` — When disabled, returns raw query passthrough (`display_query` == raw)
6. `test_understand_query_fallback_on_error` — LLM failure falls back to raw query for all fields
7. `test_build_query_understanding_prompt` — Prompt template includes domain and history
8. `test_parse_qu_result_with_display_query` — JSON with `display_query` field is correctly extracted
