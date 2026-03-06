# Work Log — RAG Research Chatbot Template

## 2026-03-04 — Initial Design & Implementation

### Design Phase

- Brainstormed architecture with user (registry pattern, 6-layer anti-hallucination stack)
- Key decisions made:
  - Target audience: academics (primary) + general users
  - Interfaces: CLI (Rich) + Web UI (Streamlit)
  - LLM providers: OpenAI, Anthropic, Google Gemini with live model fetching
  - Web search: pluggable (Semantic Scholar default, swappable/disable)
  - Anti-hallucination: #1 priority — 6-layer verification stack
  - Config: interactive setup wizard → `config.yaml` + `.env`
  - Embeddings: free local default (ChromaDB), OpenAI upgrade option
  - File formats: 15 extensions (PDF, DOCX, XLSX, XLS, CSV, TAB, TSV, DTA, SAV, RDS, RDA, TXT, MD, JSON, DO)
- Design doc saved: `docs/plans/2026-03-04-rag-research-chatbot-design.md`
- Implementation plan saved: `docs/plans/2026-03-04-rag-research-chatbot-implementation.md`

### Implementation Phase (Subagent-Driven Development)

15 tasks implemented with TDD, dispatched as parallel subagents where independent:

1. **Scaffold** — project structure, requirements.txt, .gitignore (`415e4e8`)
2. **File readers** — PDF + text readers with registry (`c1d9ad3`)
3. **Config loader** — YAML + .env loading (`94515d4`)
4. **DOCX/Excel/CSV readers** — Word, Excel (xlsx+xls), CSV/TSV readers (`7cdd0f2`)
5. **LLM providers** — OpenAI, Anthropic, Gemini with fallback models (`3aabf2e`)
6. **Ingestion pipeline** — recursive chunking, ChromaDB storage (`d8edd70`)
7. **Search backends** — Semantic Scholar with retry logic (`e3d44b5`)
8. **Stat readers** — Stata, SPSS, R data readers (`d8b70fa`)
9. **Prompts** — system prompt + verification prompt templates (`8a653d8`)
10. **Retriever** — dual retrieval with local priority, chunk ID anchoring (`d641d21`)
11. **Verifier** — 6-layer anti-hallucination stack (`1719478`)
12. **CLI app** — Rich-powered terminal chatbot with slash commands (`a5f1274`)
13. **Setup wizard** — interactive 5-step flow with model fetching (`24c097e`)
14. **Web UI** — Streamlit with sidebar controls and chat interface (`e3ae940`)
15. **Docker + docs** — Dockerfile, docker-compose, README, LICENSE (`af76fb1`)

**Test suite**: 49 tests across 12 test files — all passing.

---

## 2026-03-05 — Full Code Audit & Bug Fixes

### Audit

Performed line-by-line review of all source files against the design document.

### Bugs Found & Fixed

**CRITICAL — `setup.py:generate_config()` wrong config field names**

The setup wizard generated a `config.yaml` with field names that didn't match what the rest of the codebase reads. This would cause a **KeyError crash** at runtime when accessing `paths["vector_db"]`.

| Generated (wrong) | Expected (correct) | Impact |
|---|---|---|
| `paths.vector_store` | `paths.vector_db` | KeyError crash |
| `web_search.provider` | `web_search.backend` | Silent fallback |
| `verification.layers: [list]` | `verification.max_iterations` + `strict_mode` | Silent fallback |
| `embeddings.model` only | `embeddings.provider` + `openai_model` | Silent fallback |
| Missing `retrieval.chunk_size` | needed (default 1000) | Silent fallback |
| Missing `retrieval.chunk_overlap` | needed (default 100) | Silent fallback |

**BUG — `setup.py:165` wrong run command**
- Said `python -m src.cli` → fixed to `python app_cli.py`

**BUG — `app_cli.py:207` dead code**
- Removed `if False` ternary from input prompt

**TEST — `tests/test_setup.py` strengthened**
- Added assertions for all config field names to prevent this class of bug from recurring

### Verified Correct (no issues)

- `src/config_loader.py`, `src/readers/` (all 8 modules + registry)
- `src/llm/` (registry + 3 providers), `src/search/` (registry + Semantic Scholar)
- `src/ingest.py`, `src/retriever.py`, `src/prompts.py`, `src/verifier.py`
- `app_cli.py`, `app_web.py`, `ingest.py` (root entry point)
- `Dockerfile`, `docker-compose.yml`, `.gitignore`, `README.md`, `LICENSE`
- All 12 test files (49 tests pass, 1 PyPDF2 deprecation warning)

### Added

- `CLAUDE.md` — project instructions for Claude Code
- `docs/WORKLOG.md` — this working log

---

## 2026-03-05 — Second Full Re-Audit

### Scope

Complete re-read of every source file (38 Python files + Dockerfile, docker-compose.yml, requirements.txt, .gitignore, LICENSE, README) against the design document (`docs/plans/2026-03-04-rag-research-chatbot-design.md`).

### Verified Correct

All 6 anti-hallucination layers verified in correct execution order:
- **Layer 0**: No-source refusal (pre-LLM gate) — `verifier.py:213-219`
- **Layer 1**: System prompt guardrails — `prompts.py:8-60`
- **Layer 2**: Soft max-token cap — `verifier.py:47-65`
- **Layer 3**: LLM self-verification with iterative correction — `verifier.py:250-336`
- **Layer 4**: Term-overlap similarity check — `verifier.py:100-148`
- **Layer 5**: Warning-phrase scanner (8 phrases) — `verifier.py:24-33`

All config field names verified consistent across every `.get()` call in the codebase.
All 4 retrieval scenarios (local+web, local-only, web-only, no-sources) verified.
Chunk ID anchoring (`[CHUNK-LOCAL-NNN]`, `[CHUNK-WEB-NNN]`) verified.
Citation format (endnotes, direct quotes, References section) verified in system prompt.
All 15 file format readers verified present and functional.
Registry pattern verified in `src/llm/`, `src/search/`, `src/readers/`.
Setup wizard generates correct config field names (verified by contract test in `tests/test_setup.py`).

### Bug Found & Fixed

**BUG — `src/search/semantic_scholar.py:38` — `None` authors crash**

If the Semantic Scholar API returns a paper with `"authors": null`, `paper.get("authors", [])` returns `None` (key exists with value `None`; default only applies when key is missing). `len(None)` raises `TypeError`.

- Line 37 already handled this correctly: `(paper.get("authors") or [])[:3]`
- Line 38 did NOT: `len(paper.get("authors", []))` → crashes on `None`
- **Fix**: Changed to `len(paper.get("authors") or [])` — consistent with line 37

### Test Suite

49 tests, all passing after fix.

---

## 2026-03-05 — GitHub Repo & README Rewrite

- Created private GitHub repo: `LIANJie-Jason/chatbotsample_api`
- Rewrote README as a detailed usage guide for social scientists without coding backgrounds
- README includes: step-by-step installation, supported file formats, CLI/web usage, how it works, anti-hallucination explanation, config reference, Docker, 9 advantages, 9 limitations, troubleshooting
- Multiple rounds of README corrections (example output accuracy, clone URL, folder names)
- Added Python 3.11–3.13 environment setup instructions after discovering Python 3.14 incompatibility with ChromaDB/Pydantic

---

## 2026-03-05 — Third Full Audit & Live Testing Fixes

### Third Audit

Complete re-read of all source files, design doc, and README. All 49 tests pass.

**README fix**: Prerequisites said "Python 3.11 or later" → corrected to "Python 3.11–3.13" (Python 3.14+ not supported).

### Live Testing — Issues Found & Fixed

User tested the chatbot with real Amnesty International PDFs and CSV data. Several issues discovered:

**FIX — Over-refusal when relevant sources exist** (`src/prompts.py`)

The system prompt had a binary rule: "If the answer is NOT in the context → REFUSE." The LLM refused even when relevant chunks were retrieved (e.g., 5 chunks about China at distances 0.368–0.459) because the question was broad and the data was sparse.

- Added: "If the context contains relevant information, you MUST provide what you can, even if the answer is incomplete."
- Added: "An incomplete answer grounded in sources is ALWAYS better than a refusal."
- Changed refusal to: "ONLY refuse if the context contains NO relevant information at all."
- This matches the design doc's principle: "An incomplete answer is always better than a fabricated one."

**FIX — References showed chunk IDs instead of file paths** (`src/prompts.py`)

The LLM output `[1] CHUNK-LOCAL-001` instead of actual file names. The prompt said "source title or chunk ID" and the LLM took the easy route.

- Added explicit instruction: "Do NOT use chunk IDs (CHUNK-LOCAL-001, CHUNK-WEB-001, etc.) in the reference list."
- Added: "Extract the ACTUAL file name, path, and page number from the From: and Path: lines in the context."
- Added concrete examples of correct local and web reference formatting.

**FIX — LLM output literal `[N]` alongside real citation numbers** (`src/prompts.py`)

The citation rules used `[N]` as a placeholder example. The LLM copied it literally, producing `[N][1]`.

- Replaced `[N]` with plain English: "numbered endnote like [1], [2], etc."
- Added: "Do NOT output the literal text [N] — always use actual numbers."
- Also fixed the last `[N]` in the verification prompt template (9-point checklist item 1).

**FIX — Retrieval missed relevant chunks with fixed top_k** (`src/retriever.py`)

With `top_k=5`, short queries like "China in 2024?" retrieved generic intro pages (pages 1, 3, 11) but missed the China-specific page 410.

- Replaced fixed top_k retrieval with **distance-threshold retrieval**.
- Now queries up to 50 candidates from ChromaDB, then filters to keep only chunks with cosine distance below `max_distance` (default 0.55).
- Broad queries with lots of relevant content get many chunks; narrow queries get fewer.
- New config fields: `retrieval.top_k` (candidate pool cap, default 50), `retrieval.max_distance` (relevance threshold, default 0.55).

**FEAT — Personal welcome message with web search status** (`app_cli.py`)

- Added chatbot self-introduction: "Hi! I'm your research assistant on {domain}..."
- Shows web search status (ON in green / OFF in red) with toggle instructions.

**STYLE — Hidden distance scores from `/sources` output** (`app_cli.py`)

- Removed `(distance: 0.539)` from `/sources` — internal metric not useful for end users.

### Updated Files

| File | Changes |
|---|---|
| `src/prompts.py` | Over-refusal fix, reference format fix, `[N]` removal |
| `src/retriever.py` | Distance-threshold retrieval |
| `app_cli.py` | Welcome message, web search status, hide distance scores |
| `setup.py` | New config defaults (top_k=50, max_distance=0.55) |
| `README.md` | Python version fix, config reference updated |
| `tests/test_prompts.py` | Updated assertions for new prompt wording |

### Test Suite

49 tests, all passing after all fixes.

---

## 2026-03-05 — Query Understanding Layer

### Design

Added a pre-retrieval query understanding layer that uses the LLM to reformulate user queries for better embedding search. Design doc: `docs/plans/2026-03-05-query-understanding-design.md`.

**Problem:** Short/vague queries like "China in 2024?" produce weak embeddings that miss relevant chunks, even when the knowledge base has the answer. Follow-up questions like "what about 2023?" lose context.

**Solution:** Before retrieval, an LLM call analyzes the user's query and either:
1. **Reformulates** it into a search-optimized form (expanded keywords, resolved pronouns, domain-aware terms)
2. **Asks clarification** when the query is genuinely ambiguous (high bar — most queries get reformulated)

### Key Design Decisions

- **Reformulated query → retrieval only.** The original query is preserved for response generation
- **Conversation history** (last 6 messages by default) enables pronoun/reference resolution
- **Transparency:** Shows `Searching for: "reformulated query"` to the user
- **Graceful degradation:** Falls back to raw query if LLM fails. Configurable via `query_understanding.enabled`
- **No anti-hallucination impact:** Operates before retrieval; the 6-layer stack is unchanged
- **Max clarifications:** After `max_clarifications` rounds (default 1), forces a search

### Implementation

| File | Action | Description |
|---|---|---|
| `src/query_engine.py` | CREATE | `understand_query()` + `_parse_qu_result()` with JSON parsing and fallback |
| `src/prompts.py` | MODIFY | Added `QUERY_UNDERSTANDING_PROMPT_TEMPLATE` + `build_query_understanding_prompt()` |
| `app_cli.py` | MODIFY | Query understanding step, clarification flow, conversation history tracking |
| `app_web.py` | MODIFY | Query understanding step, `pending_clarification` state for Streamlit |
| `setup.py` | MODIFY | Added `query_understanding` config defaults |
| `tests/test_query_engine.py` | CREATE | 8 tests covering reformulation, clarification, disabled, error fallback, JSON parsing |
| `tests/test_prompts.py` | MODIFY | 2 tests for new prompt template |
| `tests/test_setup.py` | MODIFY | Assertions for new config section |

### Pipeline Flow (Updated)

```
User query → understand_query(query, history, cfg)
    → [if CLARIFY: ask user, loop back, max 1 round]
    → [if SEARCH: use reformulated query]
    → retrieve(reformulated_query)
    → verify_and_respond(original_query, results)
    → Display
```

### Config

```yaml
query_understanding:
  enabled: true          # false to skip (use raw query)
  max_history: 6         # conversation messages for context
  max_clarifications: 1  # max clarification rounds before forcing search
```

### Test Suite

59 tests across 13 test files — all passing.

---

## 2026-03-05 — Fourth Full Audit & .get() Safety Fixes

### Scope

Complete re-audit of all 40+ source files by 6 parallel subagents, covering: design doc consistency, core pipeline code, app entry points, registry modules, full test suite (59/59 pass), and README/Docker/CLAUDE.md accuracy.

### Bugs Found & Fixed

**BUG — `src/ingest.py:115,148` — Direct dict access crashes on missing config**

Used `cfg["paths"]["vector_db"]` and `cfg["paths"]["knowledge_base"]` instead of `.get()` with defaults. Raises `KeyError` if config is malformed or incomplete.

- Fix: `cfg.get("paths", {}).get("vector_db", "chroma_db")` and `cfg.get("paths", {}).get("knowledge_base", "knowledge_base")`

**BUG — `src/llm/__init__.py:15,21-24` — Direct dict access on `cfg["llm"]`**

Line 15 used `cfg["llm"]["provider"]`; lines 21-24 used `cfg["llm"].get(...)` where the outer `cfg["llm"]` could still crash. All violate CLAUDE.md's `.get()` with defaults requirement.

- Fix: Extract `llm_cfg = cfg.get("llm", {})` once, then use `llm_cfg.get(...)` for all accesses.

**BUG — `src/search/__init__.py:22-24` — Direct key access on result dicts**

Used `r['authors']`, `r['title']`, `r['url']`, `r['abstract']` instead of `.get()`. Would crash if any key missing from a search result.

- Fix: `r.get('authors', 'Unknown')`, `r.get('title', 'Untitled')`, `r.get('url', 'N/A')`, `r.get('abstract', 'N/A')`

**BUG — `app_web.py:171` — Clarification ignores `max_clarifications` config**

Web UI always allowed 1 clarification round regardless of `max_clarifications` config value. Setting `max_clarifications: 0` in config would not disable clarification in the web UI.

- Fix: Added `and max_clarifications > 0` condition to the clarification check.

### Test Improvement

- Added missing assertions for `retrieval.top_k` (50) and `retrieval.max_distance` (0.55) in `tests/test_setup.py`

### Documentation

- Committed CLAUDE.md, docs/plans/, and docs/WORKLOG.md to the git repo (previously only existed in working copy)
- Fixed CLAUDE.md: `max_clarifications` now correctly lists both `app_cli.py` and `app_web.py` as consumers
- Refined CLAUDE.md:
  - Separated ingestion pipeline and query pipeline in architecture description
  - Fixed config table column headers (`Config Path | Read By | Notes`)
  - Added `paths.knowledge_base` to config table (was missing)
  - Updated project structure to include `CLAUDE.md` and `docs/`
  - Added `.get()` rule to "Do NOT" section to prevent future direct-access bugs

### Test Suite

59 tests across 13 test files — all passing.

---

## 2026-03-05 — Fifth Full Audit: Line-by-Line Code Stack Review

### Scope

Comprehensive line-by-line audit of every source file by 6 parallel subagents. Each agent audited a different slice of the codebase: config + ingest pipeline, query engine + prompts + verifier, retriever + search backends, LLM providers + readers, app entry points + setup, and the full test suite.

### HIGH Priority Bugs Fixed (3)

**BUG — `src/ingest.py:206` — Chunk ID collision causes silent data loss**

If two files in the same dataset folder share the same stem (e.g., `report.pdf` + `report.docx`), their chunk IDs collide exactly (`general_report_0`, `general_report_1`, ...). ChromaDB would silently overwrite chunks from the first file.

- Fix: Include file suffix in ID: `{dataset}_{stem}{suffix}_{index}` → e.g., `general_report.pdf_0`

**BUG — `src/verifier.py:282-323` — Verification loop short-circuit refuses prematurely**

When iteration 1 found ≤2 errors, a special branch attempted one correction, then **immediately refused** if it failed — never using iterations 2 or 3. This meant `max_iterations=3` was misleading: minor-error responses that could succeed with another attempt were refused outright.

- Fix: Removed the special-case branch. All iterations now use the same correct-and-loop pattern, ensuring the full iteration budget is used.

**BUG — `app_web.py:156,204` — Web UI used wrong query for response generation**

The web UI passed `response_query = combined` (the concatenated clarification string) to `verify_and_respond`, while the CLI correctly passed `original_query`. This violated the design rule: "Reformulated query for retrieval ONLY; original query preserved for response generation."

- Fix: Changed to `verify_and_respond(original_query, ...)`, matching CLI behavior and CLAUDE.md spec.

### MEDIUM Priority Bugs Fixed (6)

| File | Bug | Fix |
|---|---|---|
| `src/ingest.py:67,81` | Direct dict access `page_info["text"]` / `page_info["page"]` | Changed to `.get("text", "")` / `.get("page", "?")` |
| `src/ingest.py:73` | `chunk_index` reset per page instead of accumulating globally | Replaced per-page `enumerate` with `global_chunk_index` counter |
| `src/ingest.py:26` | `chunk_overlap >= chunk_size` → `ValueError` from `range(step=0)` | Added `step = max(1, chunk_size - chunk_overlap)` guard |
| `src/llm/gemini.py:14` | `response.text` raises `ValueError` on safety-blocked content (unlike OpenAI/Anthropic which return `None`) | Wrapped in try/except, returns `""` on blocked |
| `src/config_loader.py:25` | `yaml.safe_load()` returns `None` on empty config → `AttributeError` on `.setdefault()` | Added `or {}` fallback |
| `app_cli.py:167` | `cfg["llm"]["model"]` → `KeyError` if no `llm` section in config | Changed to `cfg.setdefault("llm", {})["model"]` |

### LOW Priority — Design Compliance Fixes (12+)

All remaining direct dict access violations across the codebase converted to `.get()`:

| File | Changes |
|---|---|
| `src/retriever.py:38-44,57,65` | ChromaDB results and chunk dict access → `.get()` with defaults |
| `src/search/__init__.py:20` | `r['year']` → `r.get('year', '')` |
| `src/search/semantic_scholar.py:43` | `external_ids['DOI']` → `.get('DOI', '')` |
| `src/verifier.py:175,221` | Greedy regex `[\s\S]*` → non-greedy `[\s\S]*?`; `retrieval_result.get("context", "")` |
| `src/query_engine.py:87` | Greedy regex `[\s\S]*` → non-greedy `[\s\S]*?` |
| `src/readers/pdf.py:3` | Top-level `PyPDF2` import → lazy (function-level) — prevents all readers from failing if PyPDF2 missing |
| `src/readers/docx.py:2` | Top-level `python-docx` import → lazy (function-level) — same fix |
| `app_cli.py:102,113,117,291,292,344,348` | All direct dict access on result/chunk dicts → `.get()` |
| `app_web.py:172,175,211,226,230` | All direct dict access on result/qu_result dicts → `.get()` |
| `src/ingest.py:179,207,208` | ChromaDB `.get()["ids"]` → `.get().get("ids", [])`, internal chunk access → `.get()` |

### Test Suite

59 tests across 13 test files — all passing after all fixes.

### Advisory (not bugs, noted for future)

- **Path resolution** (`src/ingest.py:117,151`): Uses `os.path.abspath("config.yaml")` which resolves relative to CWD. Works correctly when run from project root (standard usage).
- **Test coverage gaps**: Integration tests for the full retrieval pipeline and verification loop (Layers 1-4) are not covered. The test suite validates utility/helper functions well but lacks end-to-end pipeline tests.

---

## 2026-03-05 — Sixth Full Audit & Bug Fixes

### Scope

Complete line-by-line audit of every source file by 6 parallel subagents. Found and fixed 10 bugs across 8 files.

### HIGH Priority Bugs Fixed (4)

**BUG — `verifier.py:175` + `query_engine.py:87` — Non-greedy regex breaks nested JSON parsing**

The 5th audit incorrectly changed the regex from greedy (`\{[\s\S]*\}`) to non-greedy (`\{[\s\S]*?\}`). For nested JSON like `{"errors": [{"check": 1}], "pass": true}`, the non-greedy match stops at the first `}`, extracting `{"errors": [{"check": 1}` — invalid JSON. This caused the verification fallback to always fail, wasting correction iterations.

- Fix: Reverted to greedy `\{[\s\S]*\}` in both files.

**BUG — `src/ingest.py:122,156` — CWD-relative path resolution**

`os.path.abspath("config.yaml")` resolves relative to the current working directory, not the project root. Running from a different directory creates ChromaDB and looks for knowledge_base in the wrong location.

- Fix: Use `Path(__file__).resolve().parent.parent` (matches `config_loader.py` pattern).

**BUG — `app_cli.py:316` — Clarification combined string passed to verify_and_respond**

After clarification, `original_query` was set from `qu_result.get("original_query")` which returned the combined `"{original} — {clarification}"` string, violating the design rule.

- Fix: Force `original_query = user_input` (true original) after QU.

### MEDIUM Priority Bugs Fixed (4)

| File | Bug | Fix |
|---|---|---|
| `verifier.py:283` | Correction prompt omitted original user query — LLM saw only "fix errors" without knowing what was asked | Added original query to correction prompt |
| `openai.py:16` | `response.choices[0]` — IndexError on empty choices (content policy block) | Guard: `if not response.choices: return ""` |
| `anthropic.py:14` | `response.content[0]` — IndexError on empty content | Guard: `if not response.content: return ""` |
| `app_web.py:192,203` | `retrieve()` and `verify_and_respond()` not wrapped in try/except (unlike CLI) | Added try/except with `st.error()` |

### LOW Priority Fixes (2)

| File | Bug | Fix |
|---|---|---|
| `app_web.py:169` | Exception fallback set `original_query` to `combined` instead of true original | Changed to `original_query` |
| `tests/test_readers_docx_excel_csv.py:4,16` | Missing `pytest.importorskip()` for optional deps | Added `pytest.importorskip("docx")` and `pytest.importorskip("openpyxl")` |

### Test Suite

59 tests across 13 test files — all passing.

---

## 2026-03-05 — Display Query Feature (Improved Response Quality)

### Problem

After the query understanding layer reformulates a query or the user provides a clarification, the response LLM still received the raw, vague original query. For example:

- User asks: "tell me about that paper"
- User clarifies: "the Chenoweth one on civil resistance"
- **Before:** Response LLM receives "tell me about that paper" — vague, unhelpful
- **After:** Response LLM receives "What are the key findings of Chenoweth's research on civil resistance?" — clear, specific

### Solution: Dual-Query Output

The query understanding layer now produces **three queries**:

| Field | Purpose | Used by |
|---|---|---|
| `search_query` | Keyword-optimized for vector retrieval | `retrieve()` |
| `display_query` | Clear natural-language question for response LLM | `verify_and_respond()` |
| `original_query` | Raw user input, for reference/logging | conversation history |

### Pipeline Flow (Updated)

```
User query → understand_query(query, history, cfg)
    → [if CLARIFY: ask user, loop back, max 1 round]
    → [if SEARCH: produces search_query + display_query]
    → retrieve(search_query)
    → verify_and_respond(display_query, results)
    → Display
```

### Implementation

| File | Change |
|---|---|
| `src/prompts.py` | QU prompt requests `display_query` in JSON output |
| `src/query_engine.py` | `_parse_qu_result` extracts `display_query`; all return paths include it |
| `app_cli.py` | Uses `display_query` for `verify_and_respond()` |
| `app_web.py` | Uses `display_query` for `verify_and_respond()` |
| `tests/test_query_engine.py` | New test `test_parse_qu_result_with_display_query` + updated assertions |

### Anti-Hallucination Impact

**None.** The `display_query` is just a better-worded question. The 6-layer verification stack still checks every claim against the retrieved context. All citations must still be grounded in sources.

### Design Docs Updated

- `docs/plans/2026-03-05-query-understanding-design.md` — updated function signature, prompt template, integration examples, pipeline flow, test plan
- `docs/plans/2026-03-04-rag-research-chatbot-design.md` — updated data flow diagram
- `CLAUDE.md` — updated QU layer description with dual-query output

### Test Suite

60 tests across 13 test files — all passing (1 new test added).

---

## 2026-03-05 — Seventh Full Audit, Format Injection Fix, Push to GitHub

### Scope

Complete line-by-line audit of all 38 source files across 6 parallel read batches. Every file checked for bugs, inconsistencies, and design-doc compliance.

### Bugs Fixed

**CRITICAL — `src/prompts.py` — Format injection crash on curly braces in user content**

Python's `str.format()` raises `KeyError` when user-supplied content (context, response, query, history) contains `{placeholder}` patterns — common in academic documents with code snippets, variable names, or LaTeX.

- Fix: Added `_escape_braces()` helper that converts `{` → `{{` and `}` → `}}` before passing to `.format()`. Applied to all user-supplied content in all 3 prompt builder functions.
- Only `context`, `response`, `history`, `query` need escaping — `bot_name` and `domain` come from config and `.format()` doesn't re-process braces in substituted values.

**BUG — `app_web.py:155-156,170` — `display_query` fallback lost clarification context**

When the QU layer was disabled or failed during a clarification flow, `display_query` defaulted to `original_query` (the bare pre-clarification question) instead of `combined` (which includes the clarification answer). The response LLM lost the clarification context.

- Fix: Changed defaults and exception fallback to use `combined` for `display_query`.

### Regression Tests Added

- `test_build_prompt_with_curly_braces_in_context` — context with `{placeholder}` patterns
- `test_build_verification_prompt_with_curly_braces` — response/context/flags with braces

### Cross-Checks Verified

- All 16 config field paths consistent (wizard → consumers → tests)
- Dual-query flow consistent (CLI + web)
- Anti-hallucination 6-layer stack intact
- All registry completeness (readers: 15 ext, providers: 3, backends: 2)
- Zero `cfg[` direct access in `src/`
- All empty/error guards in place

### Test Suite

62 tests across 13 test files — all passing. Pushed as commit `9815e49` to `origin/master`.

---

## 2026-03-05 — Hybrid Search & Natural Tabular Formatting

### Problem

The chatbot could summarize the PTS codebook (PDF) but failed to retrieve PTS data rows for specific countries. Asking "PTS scores for China along the years" returned 29 local chunks but the LLM refused — because embedding similarity search is poor at matching natural language queries to structured tabular data rows. Data rows like `Country: China; Year: 2005; PTS_A: 4` have low cosine similarity to "PTS scores for China."

### Fix 1: Hybrid Search (Keyword + Embedding)

Added keyword-based retrieval alongside the existing embedding search. The retriever now:

1. Runs embedding search (existing — distance-threshold filtering)
2. Extracts significant keywords from the query (proper nouns, numbers, acronyms)
3. Finds chunks containing those keywords via case-insensitive text matching
4. Merges results (embedding first, keyword supplements, deduplicated)

For "PTS scores for China along the years", keywords extracted: `["China", "PTS", "scores", "years"]`. The keyword search finds data rows containing "China" even when their embeddings don't match the query.

**New functions in `src/retriever.py`:**
- `_extract_keywords()` — stop word removal, proper noun / number prioritization, returns top 5
- `_keyword_search()` — fetches all chunks from ChromaDB, scores by keyword match count

**Config:** `retrieval.hybrid_search: true` (default). Disable with `false`.

### Fix 2: Natural Tabular Data Formatting

Changed all 4 tabular readers to produce more natural-language-like output, improving both embedding quality and LLM comprehension.

**Before:**
```
Sheet: Data | Columns: Country, Year, PTS_A
Country: China; Year: 2005; PTS_A: 4
```

**After:**
```
Data records from sheet "Data" with columns: Country, Year, PTS_A.

Record: Country = China, Year = 2005, PTS_A = 4.
```

**Files modified:**
| File | Change |
|---|---|
| `src/readers/csv_tab.py` | `col: val; ...` → `Record: col = val, ...` + natural header |
| `src/readers/excel.py` | Same format change in `_rows_to_pages()` |
| `src/readers/stata.py` | Same + improved metadata description text |
| `src/readers/rdata.py` | Same format change |

### Implementation Summary

| File | Action |
|---|---|
| `src/retriever.py` | Added `_STOP_WORDS`, `_extract_keywords()`, `_keyword_search()`, hybrid merge in `retrieve_from_vectordb()` |
| `src/readers/csv_tab.py` | Updated row/header format |
| `src/readers/excel.py` | Updated row/header format |
| `src/readers/stata.py` | Updated row/header format + metadata text |
| `src/readers/rdata.py` | Updated row/header format |
| `setup.py` | Added `hybrid_search: True` to retrieval config |
| `tests/test_retriever.py` | 5 new tests (keyword extraction + keyword search) |
| `tests/test_setup.py` | Assert `hybrid_search` in generated config |
| `CLAUDE.md` | Updated retrieval strategy, config table, test count |
| `README.md` | Added `hybrid_search` to config reference |

### Note

Tabular format changes only affect new ingestions. Existing ChromaDB data retains the old format until `python ingest.py` is re-run.

### Test Suite

67 tests across 13 test files — all passing.

---

## 2026-03-05 — SQL Layer: Design, Implementation, Review & Merge

### Problem

Even with hybrid search (keyword + embedding), vector retrieval cannot perform filtering, aggregation, or precise lookups on structured tabular data. Questions like "PTS scores for China along the years" or "how many countries are in the dataset?" require SQL-style operations that vector search fundamentally cannot do.

### Solution: SQL Layer

Added a SQLite-based structured query layer alongside the existing vector retrieval. Tabular files ingested into `knowledge_base/` are loaded into **both** ChromaDB (for conceptual questions) and a SQLite database (for structured queries). The query understanding layer routes queries to the appropriate path.

### Design Document

`docs/plans/2026-03-05-sql-layer-design.md` — Covers architecture, dual ingestion, query routing, SQL retriever spec, prompt changes, config changes, and graceful degradation.

### Implementation (TDD, 11 tasks on `sql-layer` branch)

Plan: `docs/plans/2026-03-05-sql-layer-plan.md`

| Task | Files | Description |
|---|---|---|
| 1 | `src/sql_ingest.py` | Table naming: `_sanitize_part`, `_sanitize_table_name` |
| 2 | `src/sql_ingest.py` | Type inference: `_infer_column_type`, `_get_sample_values` |
| 3 | `src/sql_ingest.py` | File loaders: CSV/TSV, Excel, Stata, SPSS, R data → `(sheet, headers, rows)` |
| 4 | `src/sql_ingest.py` | `ingest_to_sql()`: create DB, tables, schema registry |
| 5 | `src/sql_retriever.py` | `_validate_sql`, `execute_sql_query` (SELECT-only + read-only connection) |
| 6 | `src/sql_retriever.py` | `format_sql_results_as_context`, `_lookup_source_file`, `build_schema_summary` |
| 7 | `src/prompts.py` | SQL routing instructions, CHUNK-SQL IDs, schema-in-prompt, verification priority |
| 8 | `src/query_engine.py` | Schema loading, `route`/`sql_query` parsing, route validation |
| 9 | `src/retriever.py` | SQL routing, fallback logic, context merging, `_run_sql_retrieval` |
| 10 | `src/ingest.py` | Call `ingest_to_sql` for tabular files during ingestion |
| 11 | `app_cli.py`, `app_web.py`, `setup.py`, `.gitignore` | Wire routing through frontends, config defaults, gitignore |

### Key Design Decisions

- **Dual ingestion**: tabular files → both ChromaDB (text chunks via `src/readers/`) AND SQLite (structured tables via `src/sql_ingest.py`) — two separate loaders reading the same source files independently
- **LLM-based routing**: QU layer outputs `route` ("vector" | "sql" | "both") + `sql_query`
- **Schema-in-prompt**: compact table schema (~50 tokens/table) injected into QU prompt
- **SQL injection protection**: two layers — SELECT-only validation (no semicolons) + read-only SQLite connection (`?mode=ro`)
- **SQL results as context**: formatted with `[CHUNK-SQL-NNN]` IDs, fed into the same verification pipeline
- **Source priority**: `CHUNK-LOCAL = CHUNK-SQL > CHUNK-WEB` (SQL treated as local authority)
- **Fallback**: if chosen route returns nothing, tries the other
- **Graceful degradation**: no tabular files → no schema → QU skips SQL → behaves identically to vector-only system

### Dual Ingestion Detail: How Dataset Files Are Treated

Tabular files go through **two independent loaders** during ingestion:

**Path 1 — ChromaDB** (via `src/readers/`):
- CSV/Excel/Stata/SPSS/R readers convert each row into text: `"Country: China; Year: 2005; PTS_A: 4.0"`
- Rows are batched into blocks (≤6000 chars), each prefixed with column header line
- Blocks are chunked and embedded into ChromaDB for vector search
- Enables conceptual questions: "What does PTS measure?"

**Path 2 — SQLite** (via `src/sql_ingest.py`):
- Same source files loaded independently, preserving column types (INTEGER/REAL/TEXT)
- Each file becomes a SQL table: `{dataset}__{filename}_{ext}` (e.g., `pts_dataset__pts_data_csv`)
- Schema registry saved to `sql_db/sql_schemas.json` (column names, types, samples, row counts)
- Enables structured queries: `SELECT Country, Year, PTS_A FROM ... WHERE Country = 'China' ORDER BY Year`

### Bugs Found & Fixed During Review

**BUG — `app_cli.py` + `app_web.py` — NameError when QU disabled**

`route` and `sql_query` were defined inside the `if qu_enabled:` block but used unconditionally at the `retrieve()` call. When QU disabled → `NameError`.

- Fix: Added `route = "vector"` and `sql_query = None` defaults before the QU block in both files.

**BUG — `src/sql_retriever.py` — Connection leak in `execute_sql_query`**

`conn.close()` was not in a `finally` block. If `conn.execute(sql_query)` raised an exception, the connection would leak.

- Fix: Wrapped inner block with `try: ... finally: conn.close()`.

### Code Review Summary (Two full line-by-line inspections)

22 design requirements verified — all match implementation:

| Requirement | Status |
|---|---|
| Dual ingestion (ChromaDB + SQLite) | ✓ |
| LLM-based routing with fallback | ✓ |
| SQLite engine (stdlib) | ✓ |
| Schema-in-prompt delivery | ✓ |
| SQL results as context → verification pipeline | ✓ |
| Summarization → SQL routing | ✓ |
| Table naming convention | ✓ |
| Schema registry (sql_schemas.json) | ✓ |
| Type inference: INTEGER → REAL → TEXT | ✓ |
| File locations (sql_db/) | ✓ |
| Clearing on re-run | ✓ |
| SQL injection protection (2 layers) | ✓ |
| Row limit (default 200) | ✓ |
| CHUNK-SQL-NNN IDs | ✓ |
| Source priority (LOCAL = SQL > WEB) | ✓ |
| Config fields (paths.sql_db, sql.enabled, sql.max_rows) | ✓ |
| Graceful degradation (all 7 failure modes) | ✓ |
| Extended QU output (route + sql_query) | ✓ |
| Multi-sheet Excel support | ✓ |
| .gitignore updated | ✓ |
| setup.py generates SQL config | ✓ |
| App frontends wire route/sql_query through | ✓ |

**Minor observations (not bugs):**
1. `ingest_to_sql` write connection not in try/finally — minimal risk (ingestion-only, re-run clears DB)
2. `retriever.py:176` vector→SQL fallback unreachable from normal flow (dead code, present for API completeness)
3. `/sources` CLI command doesn't show SQL result details (shows count in summary only)

### Merge & Push

- Merged `sql-layer` branch (12 commits) into `master` at `/private/tmp/chatbotsample_api`
- Updated README.md with SQL layer documentation (new section, updated architecture diagram, config reference, etc.)
- Updated `docker-compose.yml` with `sql_db/` volume mount
- Pushed 16 commits to `origin/master`

### Note: Keyword Hybrid Search WIP Lost

During the merge, uncommitted keyword hybrid search changes (stop words, `_extract_keywords`, `_keyword_search` in retriever.py + reader format changes) that were in the main worktree were stashed. The stash pop had a conflict in retriever.py. During conflict resolution cleanup, these WIP changes were lost. They may need to be recreated if needed.

### Test Suite

105 tests across 19 test files — all passing.

New test files: `tests/test_sql_ingest.py` (16 tests), `tests/test_sql_retriever.py` (14 tests), `tests/test_sql_integration.py` (2 tests). Updated: `tests/test_prompts.py` (+4), `tests/test_query_engine.py` (+4), `tests/test_retriever.py` (+3), `tests/test_setup.py` (+3 assertions).

---

## 2026-03-05 — KB Meta Overview: Self-Awareness for the Chatbot

### Problem

When users ask meta-questions about the knowledge base — "What kind of data do you have?", "What datasets are available?", "What is in the knowledge base?" — the system returns zero results and refuses to answer.

**Root cause:** Vector search matches user queries against specific document chunks by embedding similarity with a `max_distance` threshold (0.55). Abstract meta-questions like "what data is available" are semantically distant from any specific chunk content. All candidate chunks exceed the distance threshold and are filtered out. Layer 0 (no-source refusal) then blocks the LLM from being called.

**Secondary problem:** The LLM has no awareness of the knowledge base's overall structure. It cannot contextualize answers within the broader KB.

### Solution: KB Meta Overview

Generate an LLM-powered high-level summary of the entire knowledge base during ingestion. This overview is used three ways:

1. **ChromaDB chunk** — Stored as a special chunk so meta-questions find it via vector search
2. **QU prompt injection** — Gives the query understanding LLM full KB awareness for better routing
3. **System prompt injection** — Gives the response LLM the "general picture" for contextualized answers

### Design Document

`docs/plans/2026-03-05-kb-meta-overview-design.md` — Covers architecture, query-time data flow, design decisions, graceful degradation, and integration points.

### Implementation

| File | Action | Description |
|---|---|---|
| `src/kb_meta.py` | CREATE | Overview generation (LLM + deterministic fallback), ChromaDB collection/storage, file I/O, meta chunk upsert |
| `tests/test_kb_meta.py` | CREATE | 20 tests covering all paths (deterministic, LLM, collection, storage, prompt integration, brace safety) |
| `src/ingest.py` | MODIFY | Trigger `build_and_store_overview()` after all ingestion (non-fatal try/except) |
| `src/prompts.py` | MODIFY | `{kb_overview_section}` in system prompt, `{kb_overview_block}` in QU prompt, updated builder functions |
| `src/query_engine.py` | MODIFY | Load `kb_meta.txt` via `load_kb_meta()`, pass to `build_query_understanding_prompt()` |
| `src/verifier.py` | MODIFY | Load `kb_meta.txt` via `load_kb_meta()`, pass to `build_prompt()` |

### Key Design Decisions

- **LLM-powered with deterministic fallback**: LLM analyzes sample chunks to describe topics and connections; falls back to structured file listing if LLM fails
- **Triple storage**: File (`chroma_db/kb_meta.txt`) + ChromaDB special chunk (id: `kb_meta_overview_001`) + prompt injection
- **Meta chunk skipped by `collect_file_records()`**: Uses `META_SOURCE = "Knowledge Base Overview"` to avoid self-reference
- **`_escape_braces()` for format injection safety**: All user-supplied text escaped before `str.format()`
- **Graceful degradation**: Missing file → `""`, LLM failure → deterministic fallback, empty KB → no-op, corrupted file → `""`

### Code Review

Two full line-by-line reviews performed:
- **Design evaluation**: All 21 design claims verified against implementation — all match
- **Code review**: 6 files reviewed (kb_meta.py, prompts.py, query_engine.py, verifier.py, ingest.py, test_kb_meta.py) — no bugs

One design-code gap found and fixed:
- **Missing connection note**: The deterministic fallback was missing the "basic connection note" for multi-dataset KBs specified in the design. Added at `kb_meta.py:115-122`.

### README Updated

- New "KB Self-Awareness: The Meta Overview" section
- Updated "What This Does" (KB awareness is now item #1: "Knows what it knows")
- Updated "How It Works" pipeline diagram (QU has KB awareness, system prompt includes overview)
- Added "Self-aware" to key design principles
- Added "Knows what it knows" to Advantages section
- Updated ingestion output example to show overview generation

### Test Suite

125/125 tests passing. Pushed as commits `8f35c1b` and `864852c` to `origin/master`.

---

## 2026-03-05 — Meta Fallback Test & Eighth Full Audit

### Meta Chunk Fallback Test

Added `test_retrieve_from_vectordb_fallback_to_meta` to `tests/test_retriever.py` — verifies that when no chunks pass the distance filter, the KB meta overview chunk (`kb_meta_overview_001`) is returned as a fallback so meta-questions about the knowledge base can still be answered.

### Bugs Found & Fixed (3)

**BUG — `src/sql_ingest.py:199` — Connection leak on exception**

`sqlite3.connect(db_path)` was not wrapped in `try/finally`. If any exception occurred during table creation or row insertion, the connection would leak.

- Fix: Extracted the table-loading loop into `_ingest_tables()` helper and wrapped the connection in `try/finally`.

**BUG — `src/prompts.py:286-288` — Brace-escaping gap for `bot_name` and `domain`**

`build_prompt()` escaped `context` and `kb_overview_section` through `_escape_braces()` but passed `bot_name` and `domain` directly to `.format()`. If a user set a domain containing `{` or `}` in `config.yaml`, prompt building would crash with `KeyError`.

- Fix: Added `_escape_braces()` to both `bot_name` and `domain` in `build_prompt()` and `build_query_understanding_prompt()`.

**DOC — `CLAUDE.md` — Stale test count**

Said "128 tests" but actual count was 129 after the meta fallback test.

- Fix: Updated both occurrences (lines 133 and 174) to "129 tests".

### Eighth Full Audit (Fresh Line-by-Line)

Complete re-read of every source file (17 Python source modules + 17 test files + `setup.py` + `app_cli.py` + `app_web.py`), design doc, CLAUDE.md, and `.gitignore`. Every line checked against the design document (`docs/plans/2026-03-05-sql-layer-design.md`).

**Design compliance**: All 22 design requirements verified — all match implementation.

| Category | Items Checked | Status |
|---|---|---|
| Dual ingestion | ChromaDB + SQLite paths | ✅ |
| Table naming & schema registry | Convention, JSON format, type inference | ✅ |
| SQL injection protection | SELECT-only validation + read-only connection | ✅ |
| Query routing | LLM-based with fallback, route validation | ✅ |
| Schema-in-prompt delivery | ~50 tokens/table, escaped | ✅ |
| Prompt changes | CHUNK-SQL in system + verification prompts | ✅ |
| Config fields | `paths.sql_db`, `sql.enabled`, `sql.max_rows` | ✅ |
| App integration | CLI + web wire route/sql_query through | ✅ |
| Graceful degradation | All 7 failure modes | ✅ |
| Brace escaping | All 4 prompt builders, all parameters | ✅ |
| Connection management | try/finally in sql_ingest + sql_retriever | ✅ |
| Fallback logic | Bidirectional (SQL↔vector) | ✅ |

**Minor observations (not bugs, no action needed):**
1. `_extract_table_from_query` regex doesn't handle single-quoted table names — graceful degradation (returns `""`, source file shows empty)
2. `_sanitize_column_name` could theoretically produce collisions — SQLite would error, caught by try/except, file skipped
3. CLAUDE.md config table doesn't list `kb_meta.py` as a consumer of `paths.sql_db` — minor doc gap

### Test Suite

129 tests across 17 test files — all passing.

---

## 2026-03-05 — Ninth Audit: Final Pre-Push Quality Gate

### Scope

Final comprehensive re-evaluation of the entire codebase before pushing to GitHub. All source files re-read, every code workflow traced, test suite run.

### Bugs Fixed & Pushed (commit `3a0fe98`)

Two fixes from the eighth audit, committed and pushed together:

**FIX — `src/sql_ingest.py` — Connection leak on exception**

Extracted inner loop into `_ingest_tables()` helper, wrapped `sqlite3.connect()` in `try/finally`.

**FIX — `src/prompts.py` — Brace-escaping gap for `bot_name` and `domain`**

Added `_escape_braces()` to `bot_name` and `domain` in both `build_prompt()` and `build_query_understanding_prompt()`.

### Workflow Traces Verified

All code workflows traced end-to-end:

1. **Ingestion pipeline**: files → chunk → embed → ChromaDB + tabular → SQLite + KB meta overview
2. **Query pipeline**: QU (with SQL routing + KB awareness) → retrieve (vector/SQL/both with fallback) → verify_and_respond (6-layer stack)
3. **Fallback chains**: SQL→vector, vector→SQL, meta chunk fallback
4. **No-retrieval behavior**: 3 scenarios traced — (1) KB exists but no match → meta-chunk fallback → LLM answers with KB overview, (2) empty KB → Layer 0 blocks → canned refusal, (3) SQL fails → bidirectional fallback
5. **Clarification flow**: CLI (while loop, max rounds) + web (session state, pending_clarification)
6. **Graceful degradation**: all 7 failure modes verified

### Design Compliance

All 22 design requirements verified — all match implementation. No discrepancies found.

### Test Suite

129/129 tests passing (3.09s). No failures, no warnings.

---

## 2026-03-05 — Schema Enrichment, Column Statistics, Code Reviews

### Features Added

**Schema enrichment pipeline** (`3d1d5b4`)
- Codebook detection: searches tabular file directories for `.pdf`, `.docx`, `.txt`, `.md` files with keywords ("codebook", "readme", "dictionary", etc.)
- LLM-powered column descriptions: generates `table_description` and per-column `description` using codebook text or inference from column names/types/samples
- Graceful degradation: LLM failure is non-fatal; missing codebook falls back to inference-only
- Key functions: `_find_codebook_files()`, `_read_codebook_text()`, `_describe_columns_with_llm()`, `_enrich_schema_with_descriptions()`

**Column statistics** (`353f65a`)
- `_get_column_stats()`: computes `unique_count` (all types), `min`/`max` (INTEGER/REAL only)
- `_get_sample_values()`: evenly-spaced representative values from sorted unique set (numeric-aware sorting)
- `build_schema_summary()`: rich format with types, ranges, unique counts, samples, and descriptions
- `format_sql_results_as_context()`: includes dataset description and column descriptions via `table_info` parameter

### Bug Fix Round 1 (`86e20a0`)

4 bugs found during first comprehensive code review:
1. Numeric sorting in `_get_sample_values` — used `float()` key for numeric-sortable values
2. CSV BOM encoding — `utf-8-sig` for Excel-exported CSVs
3. `relative_to` try/except in `_ingest_tables` — handle files not under documents_dir
4. Schema summary colon placement in `build_schema_summary`

### Design Doc Updated

Updated `docs/plans/2026-03-05-sql-layer-design.md` to reflect all implemented features:
- Status changed from "Approved" to "Implemented"
- Added schema enrichment section, updated examples, expanded graceful degradation table
- Note: design doc is gitignored but also updated at `/Users/lianjie/Desktop/tool making/chatbot template/docs/plans/`

---

## 2026-03-06 — Comprehensive Multi-Agent Debug Review

### Process

Dispatched 5 parallel debug agents to cross-check the entire SQL layer stack line-by-line:
1. **Agent 1**: `sql_ingest.py` — type inference, column naming, sample values, loaders
2. **Agent 2**: `sql_retriever.py` + `retriever.py` — SQL execution, routing, fallback paths
3. **Agent 3**: `query_engine.py` + `prompts.py` — schema injection, brace escaping, QU parsing
4. **Agent 4**: `app_cli.py` + `app_web.py` — pipeline integration, route/sql_query flow
5. **Agent 5**: Test suite — run tests, identify coverage gaps, find false-confidence tests

### Bug Fix Round 2 — 7 Bugs Fixed

| # | Severity | File | Bug | Confirmed By |
|---|----------|------|-----|-------------|
| 1 | **Critical** | `sql_ingest.py:497` | Column name collision — `"Score-A"` and `"Score_A"` both sanitize to `"Score_A"`, causing duplicate SQL columns and silent data loss via `dict(row)` overwrite | Agent 1, 5 |
| 2 | **Important** | `sql_ingest.py:351-383` | `None` → `"None"` string in Stata/SPSS/R loaders — `str(None)` produces `"None"` stored as data instead of SQL NULL | Agent 1 |
| 3 | **Important** | `sql_retriever.py:105` | NULL values rendered as Python `"None"` in LLM context — `f"{k} = {v}"` with `None` produces confusing `"Score = None"` | Agent 2 |
| 4 | **Important** | `sql_retriever.py:165` | Direct `c['name']` access in `build_schema_summary` — crashes on malformed schema, silently destroying ALL routing awareness | Agent 2 |
| 5 | **Important** | `retriever.py:142` | `_extract_table_from_query` regex misses backtick-quoted table names that LLMs sometimes generate | Agent 2, 5 |
| 6 | **Important** | `sql_ingest.py:55` | `"inf"`/`"-inf"`/`"Infinity"` misclassified as REAL — `float("inf")` succeeds, but SQLite cannot store infinity reliably | Agent 5 |
| 7 | **Latent** | `sql_ingest.py:88` | `_get_sample_values(n=1)` → `ZeroDivisionError` from `(n-1)` division | Agent 1 |

### Fixes Applied

- **Bug 1**: Added deduplication after `_sanitize_column_name()` — second collision gets `_2` suffix
- **Bug 2**: Added `_safe_str()` helper preserving Python `None` instead of converting to string
- **Bug 3**: Changed to `v if v is not None else 'N/A'` in context formatting
- **Bug 4**: Changed to `c.get("name", "unknown")` (defensive access)
- **Bug 5**: Updated regex to `["\x60]?(\w+)["\x60]?` (handles backticks)
- **Bug 6**: Added finite-range check rejecting `float("inf")` in type inference
- **Bug 7**: Added `if n <= 1: return [sorted_vals[0]]` guard

### Verified Clean (No Bugs Found)

- All routing paths in `retrieve()` — Agent 2, 4
- Brace escaping in `prompts.py` — Agent 3 (proved `str.format()` does not re-scan substituted values)
- QU parsing in `query_engine.py` — Agent 3
- App integration (CLI + Web) — Agent 4
- SQL injection protection — Agent 2, 5 (validation + read-only connection adequate)
- Verification pipeline — Agent 3

### Tests

- 7 new regression tests added for all fixed bugs
- **148/148 tests passing** (2.96s)

---

## 2026-03-06 — Second Multi-Agent Debug Audit (6 Agents, Full Codebase)

### Process

Dispatched 6 parallel audit agents, each covering a different area of the codebase. All agents read the CLAUDE.md design spec first, then audited every line of their assigned files. Agents cross-checked findings — 3 issues were independently confirmed by 2+ agents.

| Agent | Scope | Files Audited |
|-------|-------|---------------|
| 1. Ingestion Pipeline | `ingest.py`, `src/ingest.py`, `sql_ingest.py`, `kb_meta.py`, `config_loader.py` | 5 files |
| 2. Query Pipeline | `query_engine.py`, `retriever.py`, `sql_retriever.py` | 3 files |
| 3. Verification & Prompts | `verifier.py`, `prompts.py` | 2 files |
| 4. LLM/Search/Readers | All providers, backends, 15 readers | 15 files |
| 5. App Layer | `app_cli.py`, `app_web.py`, `setup.py`, `docker-compose.yml` | 4 files |
| 6. Config Consistency | Cross-check all 16 config fields across all consumers | All files |

### Config Consistency Result (Agent 6)

**Zero config name or default mismatches** across the entire codebase. All field names, defaults, and setup.py generation fully consistent with CLAUDE.md. Minor doc gaps: CLAUDE.md table missing `kb_meta.py` as consumer of `paths.vector_db` and `paths.sql_db`.

### Bugs Found & Fixed — Commit 1 (`a8fd301`)

3 small fixes from previous session's uncommitted changes:

| File | Fix |
|---|---|
| `query_engine.py` | Route normalization — strip whitespace and lowercase before validation |
| `sql_ingest.py` | Column dedup uses set-based collision check (handles suffix collisions like `Score_A`, `Score_A`, `Score_A_2`) |
| `sql_retriever.py` | Defensive `.get("name", "unknown")` for column name access in formatting |

### Bugs Found & Fixed — Commit 2 (`106354e`)

8 bugs fixed across 8 files based on 6-agent audit findings:

| # | Severity | File(s) | Bug | Fix | Confirmed By |
|---|----------|---------|-----|-----|-------------|
| 1 | **HIGH** | `llm/__init__.py` + 3 providers | Empty `model=""` always overrode provider defaults — API errors when no model configured | Changed to `model or None`; providers now use `model = model or "default"` | Agent 4 |
| 2 | **HIGH** | `query_engine.py` + `prompts.py` | Vector-to-SQL fallback was dead code — QU set `sql_query=None` when `route="vector"`, making fallback condition impossible | Always preserve `sql_query` from LLM; prompt asks for fallback sql_query | Agents 1, 2 |
| 3 | **HIGH** | `sql_retriever.py` | SQL validation only checked starts-with-SELECT + no-semicolons — dangerous keywords in UNION clauses passed | Added `_DANGEROUS_KEYWORDS` blocklist (INSERT, DELETE, DROP, ALTER, CREATE, ATTACH, DETACH, PRAGMA, LOAD_EXTENSION) | Agents 1, 2 |
| 4 | **MEDIUM** | `prompts.py` | Verification prompt leaked internal chunk ID naming (`CHUNK-LOCAL`, `CHUNK-SQL`) into correction loop — risk of chunk IDs in user-facing responses | Changed to user-facing language: "local documents = SQL results > web sources" | Agent 3 |
| 5 | **MEDIUM** | `config_loader.py` | Missing config.yaml gave raw `FileNotFoundError` traceback — confusing for first-time users | Added explicit check with friendly message directing to `python setup.py` | Agent 1 |
| 6 | **MEDIUM** | `config_loader.py` | `open(config_path, "r")` without `encoding` — cross-platform portability issue | Added `encoding="utf-8"` | Agent 1 |
| 7 | **MEDIUM** | `openai.py` | Model filter `startswith("o")` too broad — matched non-chat models like tokenizers | Narrowed to `startswith(("o1", "o3", "o4"))` | Agent 4 |
| 8 | **NEW TEST** | `tests/test_sql_retriever.py` | No coverage for dangerous keyword rejection | Added `test_validate_sql_rejects_dangerous_keywords` (6 assertions) | — |

### Cross-Confirmed Findings (2+ agents agreed)

| Issue | Agents |
|---|---|
| Vector-to-SQL fallback dead code | 1 (Ingestion) + 2 (Query) |
| SQL validation weakness | 1 (Ingestion) + 2 (Query) |
| Web app clarification limited to 1 round | 2 (Query) + 5 (App) |

### Remaining Items (not fixed — low impact)

| Severity | Description | Rationale |
|---|---|---|
| MEDIUM | Gemini `genai.configure()` global state, not thread-safe | Library limitation; single-user template |
| MEDIUM | Web app clarification limited to 1 round (ignores `max_clarifications > 1`) | Default is 1; Streamlit execution model makes iterative loops complex |
| MEDIUM | Correction prompt references "provided context" without re-injecting it | Context available via system prompt; fragile but functional |
| MEDIUM | Stata/RData `block_start` row numbering off when empty rows skipped | Cosmetic — page labels only, no data loss |
| LOW | Docker Compose `version: "3.8"` deprecated | Still functional; ignored by Compose v2 |
| LOW | `build_combined_context` returns refusal text as `context` when no sources | Layer 0 blocks LLM call regardless; semantically misleading but not harmful |

### Verification Confirmed

- **All 6 verification layers present and correct** (Agent 3)
- **Citation format rules complete** — numbered endnotes, no `[N]` placeholder, quotation marks, References section (Agent 3)
- **Over-refusal prevention present** (Agent 3)
- **All prompt builders escape braces correctly** (Agent 3)
- **setup.py generates correct config** (Agent 6)

### Test Suite

**153/153 tests passing** (2.35s) — 152 existing + 1 new SQL validation test.

### Note: Desktop Copy Out of Sync

The working copy at `/Users/lianjie/Desktop/tool making/chatbot template` is behind the real repo at `/tmp/chatbotsample_api/`. The Desktop copy is missing ~15 commits of bug fixes and features (KB meta fallback, brace escaping for bot_name/domain, schema enrichment, etc.). The Desktop copy was the one audited by the agents, but all fixes were applied to the real repo.

---

## Current State (2026-03-06)

- **Branch**: `master` at commit `106354e`
- **Tests**: 153/153 passing
- **GitHub**: `https://github.com/LIANJie-Jason/chatbotsample_api` — up to date
- **Total audits completed**: 10 (6 in previous sessions, 1 multi-agent SQL debug, 1 pre-push gate, 2 today)
- **Total bugs fixed to date**: ~50+ across all sessions

---

## Pending / Next Steps

- [x] ~~Create GitHub repo~~ → `LIANJie-Jason/chatbotsample_api` (private)
- [x] ~~End-to-end test with real documents and a real API key~~
- [x] ~~Query understanding layer for better retrieval~~
- [x] ~~Hybrid search for structured/tabular data retrieval~~
- [x] ~~Natural tabular data formatting for better embeddings~~
- [x] ~~SQL layer for structured dataset queries~~
- [x] ~~KB meta overview for self-awareness and meta-question answering~~
- [x] ~~Schema enrichment (codebook detection + LLM descriptions)~~
- [x] ~~Comprehensive multi-agent debug review (round 1)~~
- [x] ~~Commit and push bug fix round 2 (7 bugs)~~
- [x] ~~6-agent full-codebase debug audit (round 2) — 8 more bugs fixed~~
- [ ] Sync Desktop copy with real repo (or deprecate Desktop copy)
- [ ] Replace PyPDF2 with pypdf (PyPDF2 is deprecated)
- [ ] Consider adding provider switching in setup wizard (currently only one provider per config)
- [ ] Tune `max_distance` threshold based on more user testing
- [ ] Add integration tests for retrieval pipeline and verification loop
- [ ] Recreate keyword hybrid search (lost during SQL merge — see note above)
- [ ] Clean up sql-layer branch and worktree
