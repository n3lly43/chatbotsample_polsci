# Bug Log — RAG Research Chatbot Template

**Consolidated tracking file for all bugs, evaluations, and test coverage gaps.**
**Last updated:** Round 18 (2026-03-07)

---

## Summary

| Metric | Value |
|--------|-------|
| Audit rounds completed | 18 (70+ agent dispatches) |
| Total bugs found (all rounds) | ~270+ |
| Total bugs fixed | ~210 |
| Open bugs | 0 CRITICAL, 0 HIGH, 14 MEDIUM, 28 LOW |
| Tests | 175 passing, 17 files |
| Design score | 6.6/10 (Round 17), 7/10 (Round 15) |

---

## Design Evaluation (Round 17)

| Dimension | Score | Key Issue |
|-----------|-------|-----------|
| Architecture Quality | 7/10 | Deferred imports hide coupling, duplicated path resolution (12+ sites) |
| Anti-Hallucination | 8/10 | Layer 0 airtight; verification prompt lacks user query |
| Query Understanding | 7/10 | Dual-query design strong; no input sanitization |
| Retrieval Strategy | 7/10 | Multi-step SQL fallback thorough; no hybrid ranking for "both" route |
| User Experience | 6/10 | No streaming (30-60s blank screen); CLI/Web feature parity gap |
| Production Readiness | 5/10 | No logging, no retry/backoff, no config validation, no timeouts |
| Design Gaps | 6/10 | No cost tracking, no incremental ingestion, no conversation persistence |
| **OVERALL** | **6.6/10** | Strong prototype, needs production hardening |

### Top 10 Design Improvements

1. Cache LLM clients (singleton per provider+key) — saves 500ms-2s per query
2. Add structured logging (replace 40+ `print()` statements)
3. Incremental ingestion (hash-based skip)
4. Fix Layer 4 to check per-source overlap (not all context combined)
5. Structured JSON output for verification calls
6. Extract path resolution utility (12+ duplicate sites)
7. Live `list_models()` via provider APIs
8. API key validation in setup wizard
9. Chat export/persistence
10. Pagination for `_collect_all_data()` in kb_meta.py

---

## Open Bugs — MEDIUM (14)

Deduplicated across all rounds. Ordered by impact.

| ID | File:Line | Description | Found |
|----|-----------|-------------|-------|
| M-01 | `prompts.py:349` | **Verification prompt delimiter injection** — no sanitization for `--- END CONTEXT ---` in document chunks; attacker text could bypass verifier | R18 |
| M-02 | `verifier.py:452` | **Verification loop no-break on LLM failure** — `except: continue` burns all iterations when LLM consistently fails; should break after 2 consecutive failures | R17 |
| M-03 | `gemini.py:29` | **Gemini safety filter returns ""** — sentinel check at verifier.py:387-389 is dead code; user gets generic error, not safety-specific message | R15 |
| M-04 | `sql_retriever.py:81` | **Semicolon in quoted strings rejected** — `";" in stripped` checks raw SQL, not `_strip_quoted()`; blocks valid queries like `WHERE col = 'a;b'` | R15 |
| M-05 | `sql_retriever.py:13` | **WITH (CTE) blocked** — in dangerous keywords list; also blocked by multi-SELECT check on line 92; double-blocked, both overly aggressive | R17 |
| M-06 | `sql_retriever.py:92` | **Subquery block too aggressive** — `SELECT` count > 1 rejects `WHERE EXISTS(...)`, scalar subqueries, `CASE WHEN` with subselects | R17 |
| M-07 | `sql_retriever.py:89` | **sqlite_master check on raw SQL** — uses `stripped` instead of `unquoted`; false-rejects `WHERE col = 'sqlite_master'` as data value | R13 |
| M-08 | `retriever.py:271` | **_try_alternate_columns regex not anchored to WHERE** — can match expressions in SELECT, FROM, or other clauses | R17 |
| M-09 | `retriever.py:315` | **_try_alternate_columns sanitization order** — `replace("'","''")` then regex strip undoes the escaping; "Cote d'Ivoire" becomes "Cote dIvoire" | R17 |
| M-10 | `ingest.py:263` | **Partial-success ingestion data loss** — if first file clears old data but subsequent files fail, previous ingestion lost (partially mitigated by deferred clear) | R15 |
| M-11 | `sql_ingest.py:57` | **Type inference inconsistency** — `_infer_column_type` uses `int(s)` (rejects "3.0") but insertion uses `int(float(s))` (accepts "3.0") | R17 |
| M-12 | `app_web.py:165+190` | **Clarification doubles context in QU prompt** — clarification Q&A appears in both `combined` query string AND conversation history | R17 |
| M-13 | `app_web.py:59,104,109` | **Sidebar mutates shared cfg dict** — direct in-place mutation of session state config; fragile but currently works due to Streamlit rerun model | R18 |
| M-14 | `setup.py:198-200` | **.env overwritten on decline** — user declines config.yaml overwrite but .env is still written; can blank existing API key | R15 |

---

## Open Bugs — LOW (28)

| ID | File:Line | Description | Found |
|----|-----------|-------------|-------|
| L-01 | `llm/*.py` | No retry/backoff on LLM calls (only semantic_scholar has retry) | R13 |
| L-02 | `llm/*.py` | No request timeouts on LLM API calls | R13 |
| L-03 | `llm/*.py` | New LLM client on every `generate()` call (no connection reuse) | R13 |
| L-04 | `config_loader.py` | No config validation — `max_distance: "banana"` fails at ChromaDB | R15 |
| L-05 | `config_loader.py:61` | `get_api_key` doesn't strip whitespace | R15 |
| L-06 | `config_loader.py:42` | Non-dict section values (e.g. `paths: 42`) cause AttributeError | R18 |
| L-07 | `ingest.py` | No embedding model tracking — switching after ingestion corrupts search | R15 |
| L-08 | `ingest.py:226` | Overlap cap allows exactly 80% (should be < 80%) | R17 |
| L-09 | `ingest.py:255` | MD5 12-char prefix collision risk at ~25K files | R15 |
| L-10 | `prompts.py:85-141` | Verification prompt lacks user query — can't check relevance | R17 |
| L-11 | `prompts.py:312` | Dash delimiters (`---`) not sanitized (only `===` is) | R18 |
| L-12 | `verifier.py:473` | Correction prompt interpolates raw `query` without sanitization | R18 |
| L-13 | `sql_retriever.py:27-68` | `_strip_sql_comments` doesn't handle double-quoted identifiers | R13 |
| L-14 | `sql_retriever.py:23` | `_strip_quoted` misses escaped double quotes (`""` SQLite escaping) | R17 |
| L-15 | `sql_retriever.py:258` | Dead escape code in word-level `make_fuzzy_query` | R17 |
| L-16 | `sql_retriever.py:204` | Data values resembling chunk IDs not escaped | R18 |
| L-17 | `sql_retriever.py:54` | Unterminated block comment silently swallows rest of query | R18 |
| L-18 | `sql_retriever.py:239` | `make_fuzzy_query` doesn't match dotted column names (`t.col`) | R18 |
| L-19 | `readers/pdf.py:14` | ImportError swallowed silently (applies to all readers) | R15 |
| L-20 | `kb_meta.py:262` | Full collection loaded into memory (scalability at 100K+ chunks) | R18 |
| L-21 | `kb_meta.py:313` | Sample chunks may not be chunk_index=0 (no sort guarantee) | R17 |
| L-22 | `app_cli.py:380` | `effective_user_msg` no-op ternary (both branches identical) | R17 |
| L-23 | `app_web.py:159-170` | New questions treated as clarification answers (no cancel mechanism) | R15 |
| L-24 | `app_web.py` | No source/chunk viewer in web UI (CLI has `/sources`) | R17 |
| L-25 | `llm/openai.py:36` | Empty `choices` indistinguishable from content filter | R18 |
| L-26 | `setup.py:101` | Backslash unescape order wrong in `generate_env` | R13 |
| L-27 | `setup.py:140` | Invalid provider choice silently defaults to "openai" | R18 |
| L-28 | `readers/csv_tab.py:12` | Encoding inconsistency (`utf-8-sig`) vs `text.py` (`utf-8`) | R18 |

---

## Test Coverage Gaps

| Priority | Function | File | Risk |
|----------|----------|------|------|
| HIGH | `validate_citations()` | `verifier.py:152-236` | Core Layer 4.5 — complex regex, zero tests |
| HIGH | Verification correction loop (iteration > 1) | `verifier.py:422-485` | No test exercises correction path |
| HIGH | `app_web.py` (entire file) | `app_web.py` | Streamlit UI has zero test coverage |
| MEDIUM | `make_fuzzy_query()` | `sql_retriever.py:189-279` | SQL retry chain critical path |
| MEDIUM | `compute_similarity_flags()` | `verifier.py:101-149` | Layer 4 semantic checking |
| MEDIUM | `load_kb_meta_brief()` | `kb_meta.py:434-445` | Fallback logic untested |
| MEDIUM | `_try_alternate_columns()` | `retriever.py:252-325` | SQL alt-column search |
| LOW | `_build_fallback_sql_query()` | `retriever.py:190-249` | Only tested indirectly |
| LOW | `generate_env()` key merging | `setup.py:83-102` | Merge with existing .env untested |
| LOW | Unknown command handling | `app_cli.py` | No test for `/foobar` |

### Misleading Tests

| Test | Issue |
|------|-------|
| `test_list_models_fallback` (test_llm.py:21) | Tests static list, not actual fallback — passes with broken code |
| `test_handle_command_unknown` (test_app_cli.py:14) | Tests "not a command" path, not unknown command like `/foobar` |
| `test_verify_and_respond` mock patches (test_verifier.py) | Undifferentiated mocks — fragile, relies on side effects |

---

## Fix History (by round)

| Round | Date | Bugs Fixed | Key Changes |
|-------|------|------------|-------------|
| R1 | 2026-03-05 | 3 | Config field names, run command, dead code |
| R2 | 2026-03-05 | 8 | Hardcoded paths, JSON parse crash, `[N]` placeholder, top_k |
| R3 | 2026-03-05 | 10 | SQL injection protection (SELECT-only, keyword blocklist, read-only conn) |
| R4 | 2026-03-05 | 4 | QU→retriever→verifier pipeline threading |
| R5 | 2026-03-05 | 6 | SQL ingest column dedup, markdown fences, brace escaping |
| R6 | 2026-03-06 | 4 | KB meta overview enrichment, QU prompt KB awareness |
| R7 | 2026-03-06 | 19 | UNION block, embedding crash, chunk ID collision, reasoning models |
| R8 | 2026-03-06 | 15 | Comment stripping execution, nested comments, 12 dangerous keywords |
| R9 | 2026-03-06 | 11 | Anti-hallucination: correction prompt, Layer 4.5, 10-point checklist |
| R10 | 2026-03-06 | 3 | SQL fuzzy matching for country names |
| R11 | 2026-03-06 | 16 | QU max_tokens, Gemini error leaks, fuzzy query sanitization |
| R12 | 2026-03-06 | 33 | Pre-release final audit — 174/174 tests. **Released to GitHub.** |
| R13 | 2026-03-07 | 28 | Post-release: verification bypass, SQL ESCAPE, Gemini safety, readers |
| R14 | 2026-03-07 | 29 | All R13 T1+T2 bugs + regression fix (double-backslash ESCAPE) |
| R15 | 2026-03-07 | 2 | sql_count systematic failure, reader try/except |
| R16 | 2026-03-07 | 4 | Context budget (`max_context_chars`), `top_k` 50→20 |
| R17 | 2026-03-07 | 5 | validate_citations regex, _strip_sql_comments state machine, web budget |
| R18 | 2026-03-07 | 0 | Final audit only — 0 CRITICAL, 0 HIGH found. 4 new MEDIUM, 10 new LOW. |
| **Total** | | **~210** | |

---

## Accepted Trade-offs

These are known limitations that are by-design or too low-risk to fix:

| ID | Description | Rationale |
|----|-------------|-----------|
| K1 | SQL validation false positives for data containing "UNION"/"SELECT" | Conservative security — read-only conn is the real guard |
| K2 | `WITH` (CTE) and subqueries blocked | Same — overly restrictive but safe direction |
| K3 | No SQL execution timeout for Cartesian products | Mitigated by progress handler (10s abort) |
| K4 | `list_models()` returns hardcoded lists, not live API | Avoids API key validation complexity at setup time |
| K5 | No streaming — 30-60s blank screen during verification | Would require significant refactor of verification loop |
| K6 | Path resolution duplicated 12+ times | Works correctly; utility extraction is cleanup, not bugfix |
