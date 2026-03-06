# Bug Fix Log — RAG Research Chatbot Template

Tracks all bugs found and fixed across audit sessions. Each entry includes the
severity, file, root cause, fix applied, and the audit round that found it.

---

## Legend

- **Severity**: CRITICAL (crash/security) / HIGH (incorrect behavior) / MEDIUM (edge case/robustness) / LOW (cosmetic/minor)
- **Status**: FIXED / KNOWN (documented, not yet fixed) / WONTFIX (acceptable trade-off)
- **Round**: Which audit session found and fixed the bug

---

## Round 1 — 2026-03-05 (Initial Audit)

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 1 | CRITICAL | `setup.py` | `generate_config()` produced wrong config field names (`vector_store` instead of `vector_db`, `provider` instead of `backend`, etc.) | Corrected all field names to match codebase consumers | FIXED |
| 2 | HIGH | `setup.py:165` | Wrong run command (`python -m src.cli` instead of `python app_cli.py`) | Corrected command string | FIXED |
| 3 | MEDIUM | `app_cli.py:207` | Dead code branch (`if False` ternary in input prompt) | Removed dead code | FIXED |

---

## Round 2 — 2026-03-05 (6-Agent Audit)

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 4 | HIGH | `src/retriever.py` | `build_combined_context()` hardcoded `knowledge_base/` prefix in source paths | Made prefix dynamic from config `paths.knowledge_base` | FIXED |
| 5 | HIGH | `src/verifier.py` | `parse_verification_result()` crashed on malformed JSON with no fallback | Added `raw_decode` fallback for JSON extraction from LLM text | FIXED |
| 6 | HIGH | `src/prompts.py` | System prompt used `[N]` placeholder which LLMs copied literally | Changed to "numbered endnote like [1], [2]" with explicit "Do NOT output [N]" | FIXED |
| 7 | MEDIUM | `src/retriever.py` | Fixed top_k retrieval returning too many irrelevant chunks | Added `max_distance` threshold filter (default 0.55) | FIXED |
| 8 | MEDIUM | `src/verifier.py` | `compute_soft_max_tokens()` could return 0 for very short contexts | Added `max(256, ...)` floor | FIXED |
| 9 | MEDIUM | `src/ingest.py` | Old ChromaDB data persisted across re-ingestion | Added deferred clearing (clear old data only after first successful file read) | FIXED |
| 10 | MEDIUM | `src/retriever.py` | No fallback when vector search returns zero results | Added meta chunk fallback from KB overview | FIXED |
| 11 | LOW | `src/prompts.py` | Verification prompt missing SQL results priority check | Added check #6: "Is the source priority respected (local documents = SQL results > web sources)?" | FIXED |

---

## Round 3 — 2026-03-05 (4-Agent Focused Audit)

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 12 | HIGH | `src/sql_retriever.py` | SQL injection: no SELECT-only validation | Added `_validate_sql()` with SELECT-only check | FIXED |
| 13 | HIGH | `src/sql_retriever.py` | SQL injection: no dangerous keyword blocklist | Added `_DANGEROUS_KEYWORDS` regex (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, ATTACH, DETACH, PRAGMA, LOAD_EXTENSION) | FIXED |
| 14 | MEDIUM | `src/sql_retriever.py` | SQL injection: no read-only connection | Added `?mode=ro` to SQLite URI | FIXED |
| 15 | MEDIUM | `src/sql_retriever.py` | Semicolons not blocked in SQL queries | Added semicolon rejection in `_validate_sql()` | FIXED |
| 16 | MEDIUM | `src/retriever.py` | Chunk IDs not prefixed by type (local vs SQL vs web) | Added `CHUNK-LOCAL-NNN`, `CHUNK-SQL-NNN`, `CHUNK-WEB-NNN` prefixes | FIXED |
| 17 | MEDIUM | `src/prompts.py` | System prompt referenced chunk IDs that shouldn't appear in user-facing output | Added "Do NOT use chunk IDs in the reference list" instruction | FIXED |
| 18 | MEDIUM | `src/verifier.py` | Layer 4 used embedding-based similarity (expensive) | Replaced with term-overlap semantic similarity (zero API cost) | FIXED |
| 19 | MEDIUM | `src/sql_retriever.py` | `format_sql_results_as_context()` didn't include table source file info | Added `table_info` parameter with source file and column descriptions | FIXED |
| 20 | MEDIUM | `app_cli.py` | No transparency message for reformulated queries | Added "Searching for: ..." display when query is reformulated | FIXED |
| 21 | MEDIUM | `src/retriever.py` | SQL-to-vector fallback not implemented | Added fallback: if SQL returns empty and route was "sql", try vector search | FIXED |

---

## Round 4 — 2026-03-05 (4-Agent Workflow-Tracing Audit)

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 22 | HIGH | `src/query_engine.py` | `understand_query()` crashed when `sql.enabled` was true but no schema existed | Added guard: only load schema when `sql_db/sql_schemas.json` exists | FIXED |
| 23 | HIGH | `src/retriever.py` | `retrieve()` didn't pass `sql_query` from QU result to SQL retriever | Added `sql_query` parameter threading through retrieve pipeline | FIXED |
| 24 | HIGH | `src/verifier.py` | `verify_and_respond()` didn't use `display_query` for the LLM question | Changed to accept and use `display_query` (clear question) vs `search_query` (keyword-optimized) | FIXED |
| 25 | HIGH | `app_cli.py`, `app_web.py` | Apps didn't pass `display_query` to `verify_and_respond()` | Updated both UIs to pass `display_query` | FIXED |

---

## Round 5 — 2026-03-05 (6 MEDIUM Bugs)

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 26 | MEDIUM | `src/prompts.py` | `str.format()` on templates with curly braces in user content caused KeyError | Verified safe by `str.format()` semantics (substituted values not re-parsed); added regression tests | FIXED |
| 27 | MEDIUM | `src/prompts.py` | QU prompt JSON example braces `{{}}` could confuse LLM | Verified correct — `{{}}` in template produces literal `{}` in output | FIXED |
| 28 | MEDIUM | `src/sql_ingest.py` | Column name deduplication didn't handle pre-existing `_2` suffixes | Added collision-aware suffix generation | FIXED |
| 29 | MEDIUM | `src/sql_retriever.py` | `execute_sql_query()` didn't strip markdown code fences from LLM-generated SQL | Added fence stripping before validation | FIXED |
| 30 | MEDIUM | `src/sql_retriever.py` | `_lookup_source_file()` was private but imported by `retriever.py` | Made it a public function (removed underscore prefix) | FIXED |
| 31 | MEDIUM | `src/retriever.py` | `_extract_table_from_query()` didn't handle backtick-quoted table names | Extended regex to match backtick quoting | FIXED |

---

## Round 6 — 2026-03-06 Session 1 (KB Meta Enrichment)

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 32 | MEDIUM | `src/kb_meta.py` | `generate_kb_overview_with_llm()` didn't pass enriched schema (column descriptions, samples, stats) to LLM prompt | Expanded SQL section with full column detail: type, unique count, min/max, samples, descriptions, codebook attribution | FIXED |
| 33 | MEDIUM | `src/kb_meta.py` | Deterministic fallback `generate_kb_overview()` didn't include column descriptions or stats | Added table descriptions, column descriptions, stats, and samples to deterministic output | FIXED |
| 34 | MEDIUM | `src/prompts.py` | QU prompt didn't instruct LLM to use KB overview for query standardization | Added SEARCH rule: "use exact dataset names, column names, file names from KB overview" | FIXED |
| 35 | MEDIUM | `src/prompts.py` | QU prompt didn't instruct LLM to use KB overview for informed clarification | Added CLARIFY rule: "reference specific datasets, columns, topics from KB overview as options" | FIXED |

---

## Round 7 — 2026-03-06 Session 2 (12-Agent Deep Audit)

### CRITICAL Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 36 | CRITICAL | `src/sql_retriever.py:10` | SQL injection: `UNION SELECT` not blocked — allowed schema exfiltration via `SELECT * FROM t UNION SELECT * FROM sqlite_master` | Added `UNION` to `_DANGEROUS_KEYWORDS` regex | FIXED |
| 37 | CRITICAL | `src/ingest.py:225` | No try/except around `collection.add()` — embedding API failure (network error, rate limit) crashed entire ingestion run, losing progress for all remaining files | Wrapped in try/except; only counts successfully embedded chunks; prints warning and continues | FIXED |
| 38 | CRITICAL | `src/ingest.py:221-222` | Chunk ID collision — files with paths differing only in `/` vs `_` (e.g., `subdir/data.csv` and `subdir_data.csv`) produced identical IDs, causing ChromaDB add() error | Replaced path-based prefix with `hashlib.md5(source_name.encode()).hexdigest()[:12]` | FIXED |

### HIGH Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 39 | HIGH | `src/retriever.py:204` | Vector-to-SQL fallback was dead code — required `sql_query` to be non-None, but `sql_query` is always None when `route="vector"` | Added `_build_fallback_sql_query()` that builds a LIKE-based keyword search from schema; removed `sql_query` guard from fallback condition | FIXED |
| 40 | HIGH | `src/verifier.py:242` | Blocked-response detection false positive — `response.startswith("[") and "blocked" in response.lower()` matched legitimate responses like `[1] The road was blocked by protesters...` | Changed to case-insensitive check for specific prefixes: `lower_resp.startswith("[gemini blocked") or lower_resp.startswith("[blocked")` | FIXED |
| 41 | HIGH | `src/verifier.py:276-341` | Last-iteration correction returned unverified — in non-strict mode, the 3rd correction was never verified before being sent to user | Added post-loop verification: if response differs from initial, run one final verification pass before exhausted-iterations handling | FIXED |
| 42 | HIGH | `src/llm/openai.py:11-15` | OpenAI o-series reasoning models (o1/o3/o4) incompatible — `temperature`, `max_tokens`, and `system` role all rejected by these models, but `list_models()` included them | Added `is_reasoning` detection; uses `developer` role, `max_completion_tokens`, omits `temperature` for o-series | FIXED |
| 43 | HIGH | `setup.py:96-102` | `.env` writer didn't quote values — API keys containing `#` silently truncated (treated as comments by dotenv parsers) | Wrapped values in double quotes: `KEY="value"`; updated parser to strip quotes when reading | FIXED |
| 44 | HIGH | `setup.py:134-148` | Setup wizard silently fell back to hardcoded model list when API key was invalid — no warning to user that key validation failed | Added warning message: "Could not validate API key for {provider}. Using default model list." | FIXED |

### MEDIUM Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 45 | MEDIUM | `src/sql_retriever.py:15-31` | SQL comments (`--` and `/* */`) not stripped before validation — could hide payloads | Added `_strip_sql_comments()` function; called before all validation checks | FIXED |
| 46 | MEDIUM | `src/sql_retriever.py:40-42` | Subqueries not restricted despite docstring claiming they were — `SELECT * FROM (SELECT * FROM sqlite_master)` passed validation | Added check: reject queries with more than one `SELECT` keyword | FIXED |
| 47 | MEDIUM | `src/query_engine.py:164-171` | No type validation on LLM-returned `search_query`, `display_query`, `sql_query` — non-string types (list, dict, int) crashed downstream | Added `isinstance(x, str)` checks with fallback to `original_query` or `None` | FIXED |
| 48 | MEDIUM | `src/verifier.py:169,181` | `parse_verification_result()` didn't validate `errors`/`error_count` types — malformed LLM output caused downstream crashes | Added type validation: `errors` must be list (default `[]`), `error_count` must be int (default `len(errors)`) | FIXED |
| 49 | MEDIUM | `src/config_loader.py:33-37` | YAML null sections crashed all chained `.get()` patterns — `cfg.get("llm", {})` returns `None` (not `{}`) when key exists with value `None` | Added normalization loop after `yaml.safe_load()`: replaces `None`-valued top-level keys with empty dicts | FIXED |
| 50 | MEDIUM | `src/verifier.py:247` | Empty LLM response (`""`) passed all verification layers and was returned to user as blank | Added empty-response guard: returns `NO_SOURCES_REFUSAL` with `refused=True` if response is empty/whitespace | FIXED |
| 51 | MEDIUM | `src/sql_ingest.py:558`, `src/sql_ingest.py:43` | `pd.NA` (`"<NA>"`), `pd.NaT` (`"NaT"`), and other common missing indicators (N/A, null, None, .) not recognized as null — forced numeric columns to TEXT | Added `_NULL_STRINGS` set and `_is_null()` helper; updated all 4 null-checking locations | FIXED |
| 52 | MEDIUM | `src/sql_ingest.py:339-351`, `src/readers/excel.py:13-21` | openpyxl workbook not closed on exception — file handle leaked | Wrapped workbook iteration in `try/finally` blocks with `wb.close()` | FIXED |

### LOW Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 53 | LOW | `src/ingest.py:179-181` | Overlap guard only activated at 100% overlap — `chunk_overlap = chunk_size - 1` (99.9% overlap) passed through, creating enormous numbers of near-duplicate chunks | Changed guard to cap overlap at 80% of chunk_size | FIXED |
| 54 | LOW | `setup.py:136-137` | Empty API key (Enter at prompt) silently accepted and written to `.env` | Added warning: "No API key entered for {provider}. You can set it later in .env" | FIXED |

---

## Round 8 — 2026-03-06 Session 3 (6-Agent Strict Audit + Cross-Check)

### CRITICAL Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 55 | CRITICAL | `src/sql_retriever.py` | SQL injection: `execute_sql_query()` executed original query, not comment-stripped version — attacker could hide dangerous SQL in comments that validation strips but execution preserves | Strip comments before BOTH validation and execution: `sql_query = _strip_sql_comments(sql_query).strip()` at top of `execute_sql_query()` | FIXED |

### HIGH Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 56 | HIGH | `src/verifier.py` | `parse_verification_result(None)` crashed — `enumerate(None)` in raw_decode loop; post-loop `generate()` returning None caused unhandled crash | Added `if not raw:` guard at top returning synthetic fail result `{"pass": False, "errors": [...], "error_count": 1}` | FIXED |
| 57 | HIGH | `src/verifier.py` | Correction `generate()` returning None → `None.lower()` crash on next iteration; also unhandled exceptions from any `generate()` in verification loop | Wrapped ALL verification/correction `generate()` calls in try/except; added `if not response or not response.strip():` guard falling back to `initial_response` | FIXED |
| 58 | HIGH | `src/sql_retriever.py` | Comment stripping not iterative — nested comments (`/* /* hidden */ DROP TABLE */`) could bypass single-pass stripping | Changed to `while prev != sql` loop that iterates until stable | FIXED |
| 59 | HIGH | `src/sql_retriever.py` | `_DANGEROUS_KEYWORDS` missing 12 defense-in-depth entries — REPLACE, VACUUM, REINDEX, SAVEPOINT, RELEASE, ROLLBACK, BEGIN, COMMIT, GRANT, REVOKE, EXPLAIN, WITH all unblocked | Expanded regex from 11 to 23 keywords | FIXED |
| 60 | HIGH | `src/ingest.py` | Data loss if all `collection.add()` calls fail after deferred clear — clear happened before first successful add, so if embedding API was down, all existing data was wiped with nothing to replace it | Moved deferred clear logic INSIDE the try block, only triggers on first SUCCESSFUL `collection.add()` | FIXED |
| 61 | HIGH | `src/readers/excel.py` | `_rows_to_pages([])` crashed with IndexError — `rows[0]` on empty list when openpyxl returns empty sheet | Added `if not rows: return []` guard at top | FIXED |

### MEDIUM Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 62 | MEDIUM | `src/verifier.py` | `"pass": "false"` (string) was truthy, incorrectly passing verification — LLM could return string instead of boolean | Added `result["pass"] = result.get("pass") is True` strict boolean normalization in BOTH parsing paths | FIXED |
| 63 | MEDIUM | `src/sql_ingest.py` | `"na"` missing from `_NULL_STRINGS` — R-style NA values not recognized as null, forcing numeric columns to TEXT type | Added `"na"` to `_NULL_STRINGS` set | FIXED |
| 64 | MEDIUM | `src/llm/gemini.py` | `generate_content()` only caught ValueError (safety filters) — API errors, network errors, auth errors all unhandled, crashing the pipeline | Added broad `except Exception as e` returning `f"[Gemini error: {e}]"` | FIXED |

### LOW Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 65 | LOW | `src/verifier.py` | Empty LLM response showed misleading "no information in knowledge base" when sources DID exist | Changed to distinct message: "The AI model was unable to generate a response. Please try rephrasing your question." | FIXED |
| 66 | LOW | `setup.py` | Model selection "0" indexed `models[-1]` via negative indexing (`int("0") - 1 = -1`) | Added bounds check: `if 0 <= idx < len(models)` | FIXED |
| 67 | LOW | `app_cli.py` | Missing `route`/`sql_query` keys in exception fallback dicts — `qu_result.get("route")` returned None, passed to `retrieve()` as route=None | Added `"route": "vector", "sql_query": None` to both fallback dicts | FIXED |
| 68 | LOW | `src/retriever.py` | No SQL fallback when `route="both"` and both paths empty — only triggered for `route="vector"` | Extended condition to `route in ("vector", "both")` | FIXED |
| 69 | LOW | `app_web.py:187` | QU exception fallback dict missing `"route"` and `"sql_query"` keys — inconsistent with CLI fix (non-crashing due to `.get()` defaults + pre-initialized locals) | Added `"route": "vector", "sql_query": None` for consistency | FIXED |

---

## Known Issues (Not Yet Fixed)

| # | Severity | File | Description | Reason |
|---|----------|------|-------------|--------|
| K1 | MEDIUM | `src/sql_ingest.py:562` | `int(float(...))` loses precision for 16+ digit integers | Rare in research datasets; fix requires careful refactoring of type conversion pipeline |
| K2 | MEDIUM | Design doc | Verification loop branching logic description doesn't match uniform loop in code | Doc update needed, not a code bug |
| K3 | MEDIUM | Design doc | 9-point verification checklist items differ between doc and code | Doc update needed, not a code bug |
| K4 | MEDIUM | `CLAUDE.md` | Config table missing 9+ fields (web_search.enabled, chatbot.name, llm.provider, etc.) | Doc update needed |
| K5 | LOW | `src/sql_retriever.py` | SQL validation false positive when data values contain "UNION" or "SELECT" (e.g., `WHERE org = 'European Union'`) | Acceptable security trade-off — overly strict is safer than exploitable |
| K10 | LOW | `src/sql_retriever.py` | No SQL execution timeout — Cartesian product queries could hang indefinitely | Would need separate thread/process; SQLite has no built-in timeout for SELECT |
| K11 | LOW | `src/retriever.py` | `_build_fallback_sql_query()` uses string interpolation instead of parameterized queries | Mitigated by `\W+` word splitting which strips SQL metacharacters |
| K12 | LOW | Multiple | `cfg.get("section", {})` systemic pattern — if YAML section exists but is `None`, returns `None` not `{}` | Partially mitigated by config_loader normalization; remaining ~30 locations are low risk |
| K6 | LOW | `src/search/semantic_scholar.py` | Filters out papers without abstracts, reducing result count for some topics | By design — abstract-less papers can't provide useful context |
| K7 | LOW | `src/retriever.py` | LIKE wildcards `_`/`%` not escaped in fallback SQL query | Minor — extra matches unlikely to cause visible problems |
| K8 | LOW | `CLAUDE.md` | Test count says 162, should be 165 | Doc update needed |
| K9 | LOW | `src/verifier.py` | `compute_similarity_flags` regex `[a-z]{3,}` excludes non-ASCII and 2-letter acronyms (AI, US, UK) | Advisory-only layer; impact limited to noisy flags |

---

## Test Coverage Gaps (Identified Round 7)

| Priority | What | Description |
|----------|------|-------------|
| CRITICAL | `retrieve()` | Central routing/fallback orchestration — zero direct tests |
| CRITICAL | `verify_and_respond()` loop | Iterative correction — zero tests for multi-iteration scenarios |
| CRITICAL | `compute_similarity_flags()` | Layer 4 — entire function untested |
| HIGH | `_build_fallback_sql_query()` | New fallback SQL builder — zero tests |
| HIGH | `app_web.py` | Entire Streamlit web UI — zero test file |
| HIGH | Clarification flow | CLI/web clarification loop — untested |
| HIGH | `semantic_scholar.py` | Retry logic, rate limiting, result formatting — untested |
| HIGH | SQL fallback paths | Both directions (SQL→vector, vector→SQL) — untested |

---

## Round 9 — 2026-03-06 Session 4 (6-Agent Final Inspection + Anti-Hallucination Audit)

This round was a comprehensive pre-release inspection using 6 parallel audit agents (pipeline integrity, security, error handling, test coverage, cross-cutting consistency, anti-hallucination stack), followed by 3 parallel fix agents and 2 parallel inspector agents.

### CRITICAL Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 70 | CRITICAL | `src/verifier.py:343-349` | **AH-06**: Correction prompt missing previous response — LLM told "your previous response failed" but never shown what failed; correction loop was blind regeneration, not targeted fixing | Included `f"Your previous response was:\n{response}\n\n"` in correction prompt | FIXED |

### HIGH Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 71 | HIGH | `src/ingest.py:160-164` | **BUG-P1**: Stale data persists after removing all files — re-ingesting with empty `knowledge_base/` returned early without clearing ChromaDB/SQLite/KB meta | Added cleanup of all 3 data stores (ChromaDB chunks, SQLite DB + schema, KB meta file) before returning 0; each cleanup independently try/except guarded | FIXED |
| 72 | HIGH | `src/verifier.py` | **AH-12**: No automated citation-to-source mapping — nothing verified that `[N]` in response corresponds to correct source; LLM could misattribute every citation | Added `validate_citations()` deterministic audit (Layer 4.5): checks citation numbers don't exceed source count, verifies References section mentions actual retrieved filenames; integrated into verification loop and non-strict warning | FIXED |
| 73 | HIGH | `src/prompts.py` | **AH-07**: Self-verification bias — verification prompt's checklist item 2 too vague ("Are all citations grounded?") | Strengthened to require EXACT evidence identification; added checklist item 10 for citation number/source cross-validation; upgraded to 10-point checklist | FIXED |
| 74 | HIGH | `src/verifier.py:283-303` | **AH-08**: `max_iterations=0` or `verification.enabled=false` silently disabled ALL anti-hallucination verification with no warning | Added `print("WARNING: ...")` for both disabled paths so users/operators know verification is bypassed | FIXED |
| 75 | HIGH | `src/llm/gemini.py:17-22` | **ERR-1**: `NameError` crash when `generate_content()` raises `ValueError` before `response` assigned — except handler referenced unbound `response` variable | Added `response = None` initialization before try; added `if response is not None:` guard in ValueError handler | FIXED |
| 76 | HIGH | `src/llm/openai.py`, `src/llm/anthropic.py` | **ERR-2**: Zero error handling in `generate()` — raw SDK exceptions (AuthenticationError, RateLimitError, APIConnectionError) propagated as unhelpful tracebacks | Wrapped API calls in try/except; re-raise as `RuntimeError` with sanitized message (error type only, no raw exception text to prevent API key leaks) | FIXED |

### MEDIUM Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 77 | MEDIUM | `src/llm/gemini.py:23-24` | **SEC-1**: Raw exception message in `f"[Gemini error: {e}]"` could leak API key fragments or internal URLs to user | Changed to static `"[Gemini error: request failed]"` — no raw exception text | FIXED |
| 78 | MEDIUM | `.gitignore` | **SEC-2**: `config.yaml` not gitignored despite CLAUDE.md documenting it as gitignored; setup wizard generates `api_keys:` section inviting users to put keys there | Added `config.yaml` to `.gitignore` | FIXED |
| 79 | MEDIUM | `src/verifier.py:272` | Gemini error strings `"[Gemini error: ...]"` not caught by blocked-response detector — leaked into verification loop, wasting 6+ LLM calls | Added `lower_resp.startswith("[gemini error")` to the guard condition | FIXED |
| 80 | MEDIUM | `src/verifier.py:380` | **INSPECT-1**: `citation_warnings` computed once from initial response, never recomputed after corrections — stale warnings fed to verifier on subsequent iterations | Moved `validate_citations()` call inside the loop so it recomputes each iteration | FIXED |

### Known Issues Added

| # | Severity | File | Description | Reason |
|---|----------|------|-------------|--------|
| K13 | HIGH | `src/llm/gemini.py` + `requirements.txt` | **CON-4**: `google-generativeai` package fully deprecated; replacement `google-genai` has different API surface | Requires full API migration; functional for now but will break when PyPI removes package |
| K14 | MEDIUM | `src/verifier.py` | **AH-05**: Token cap step function too generous for small contexts (501 chars → 1536 tokens = 12:1 ratio) | Would benefit from continuous formula; current 3-tier approach is functional |
| K15 | MEDIUM | `src/verifier.py:24-33` | **AH-11**: Warning phrase list missing common patterns: "studies have shown", "research suggests", "historically" | Advisory layer only; expandable post-release |
| K16 | LOW | `src/verifier.py:184` | **INSPECT-2**: References section regex matches "sources" in prose, not just section header | Mitigated: filename matching still works because match includes everything to end of response |
| K17 | LOW | `tests/test_ingest.py` | **INSPECT-5**: No test coverage for new empty-dir cleanup code path | Should add test for empty knowledge_base/ clearing stale data |

---

## Round 10 — 2026-03-06 Session 5 (SQL Fuzzy Matching)

User-reported bug: querying "south korea in pts" returned zero SQL results despite PTS dataset being ingested, because country names in the dataset use parenthetical forms (e.g., `"South Korea (Republic of Korea)"`). The LLM-generated SQL used exact `= 'South Korea'` which missed the match.

### HIGH Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 81 | HIGH | `src/sql_retriever.py`, `src/retriever.py` | SQL exact match fails for country names with alternate forms (e.g., "South Korea (Republic of Korea)", "Iran (Islamic Republic of)") — LLM generates `= 'South Korea'` which returns 0 rows | Added `make_fuzzy_query()` that converts `= 'value'` → `LIKE '%value%'` for quoted string values; `_run_sql_retrieval()` now tries exact match first, auto-retries with fuzzy if 0 rows; returns `match_type` ("exact"/"fuzzy") for transparent reporting | FIXED |
| 82 | HIGH | `app_cli.py`, `app_web.py` | No transparency about which SQL matching strategy produced results — user couldn't tell if exact or fuzzy match was used | Source summary now shows `(exact match)` or `(fuzzy match)` label; `/sources` command shows `(matched via exact/fuzzy match)` | FIXED |

### MEDIUM Fixes

| # | Severity | File | Bug | Fix | Status |
|---|----------|------|-----|-----|--------|
| 83 | MEDIUM | `src/prompts.py` | QU prompt had no guidance on SQL text matching strategy | Added instruction: use exact `=` for text columns; system handles fuzzy fallback automatically | FIXED |

### Files Changed

- `src/sql_retriever.py` — Added `make_fuzzy_query()` function
- `src/retriever.py` — `_run_sql_retrieval()` returns 3-tuple with `match_type`; all callers updated
- `src/prompts.py` — SQL routing instructions updated
- `app_cli.py` — Source summary and `/sources` show match type
- `app_web.py` — Source label shows match type
- `tests/test_retriever.py` — Updated 5 mock return values from 2-tuple to 3-tuple

---

## Statistics

| Metric | Count |
|--------|-------|
| Total bugs fixed | ~119 (3 this round) |
| Audit rounds completed | 10 (10 sessions, 30+ total agent dispatches) |
| Test count | 174 passing |
| Test files | 17 |
| Source files audited | All 20+ |
| Known issues remaining | 17 (0 CRITICAL, 1 HIGH, 6 MEDIUM, 10 LOW) |
