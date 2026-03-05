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

## Pending / Next Steps

- [x] ~~Create GitHub repo~~ → `LIANJie-Jason/chatbotsample_api` (private)
- [x] ~~End-to-end test with real documents and a real API key~~
- [x] ~~Query understanding layer for better retrieval~~
- [ ] Replace PyPDF2 with pypdf (PyPDF2 is deprecated)
- [ ] Consider adding provider switching in setup wizard (currently only one provider per config)
- [ ] Tune `max_distance` threshold based on more user testing
