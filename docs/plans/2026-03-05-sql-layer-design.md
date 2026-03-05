# SQL Layer for Tabular Datasets — Design Document

**Date:** 2026-03-05
**Status:** Approved

## Problem

The RAG chatbot uses ChromaDB (embedding similarity) + keyword search for retrieval. Tabular data (CSV, Excel, Stata, SPSS, R data) is chunked into text rows and embedded as vectors. This fails for structured queries like "PTS scores for China along the years" because embedding similarity cannot do filtering, aggregation, or precise lookups on structured data. Summarization queries ("how many countries are in the dataset?") are similarly impossible via vector search.

## Solution

Add a SQL layer alongside the existing vector retrieval. Tabular files ingested into `knowledge_base/` are loaded into both ChromaDB (for natural-language questions) and a SQLite database (for structured queries). The query understanding layer routes queries to the appropriate retrieval path.

## Architecture

```
User query
    |
    v
Query Understanding (extended)
    | Outputs: action, route, search_query, display_query, sql_query
    |
    +-- route="sql" --------> retrieve_from_sql()
    |                           |
    |                           +-- results? --> format as context
    |                           +-- empty? ----> fallback to retrieve_from_vectordb()
    |
    +-- route="vector" -----> retrieve_from_vectordb() (existing)
    |                           |
    |                           +-- results? --> format as context
    |                           +-- empty? ----> fallback to retrieve_from_sql()
    |
    +-- route="both" -------> run both, merge results
    |
    v
Combined context (SQL text + vector chunks)
    |
    v
verify_and_respond() (unchanged 6-layer stack)
    |
    v
Cited response
```

**Key principle:** The SQL layer is a new retrieval path, not a new pipeline. Everything downstream (verification, citation, response formatting) stays the same.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Dual vs. exclusive ingestion | **Dual** — tabular files go to both ChromaDB and SQLite | Conceptual questions ("what does PTS measure?") still need vector search; metadata chunks stay in ChromaDB |
| Query routing | **LLM-based routing with fallback** | QU layer already makes an LLM call; extending it to output `route` is free. Fallback catches misroutes. |
| SQL engine | **SQLite** | Stdlib, zero-config, file-based. Matches the template's "download and run" philosophy. |
| Schema delivery to LLM | **Schema-in-prompt** | Researchers have 1–10 tables. Compact schema (~50 tokens/table) fits easily in QU prompt. Avoids extra LLM call. |
| SQL result handling | **Format as context, feed into verification pipeline** | Preserves anti-hallucination guarantees. SQL results are just another context source. |
| Summarization queries | **Always route to SQL** | Vector search cannot aggregate. QU prompt explicitly instructs: data summarization/counting/averaging/filtering → `sql` or `both`. |

## Ingestion Changes

During `python ingest.py`, tabular files get dual ingestion:

**Existing path (unchanged):** Read -> chunk -> embed -> ChromaDB

**New path (added):** Read -> load into SQLite as a table

### Table naming

`{dataset}_{filename}_{ext}` sanitized to valid SQL identifiers. Multi-sheet Excel files append sheet name.

```
knowledge_base/
  PTS_dataset/
    pts_data.csv        -> SQLite table "pts_dataset__pts_data_csv"
    codebook.pdf        -> ChromaDB only (not tabular)
  economic_data/
    gdp.xlsx            -> SQLite table "economic_data__gdp_xlsx_sheet1"
```

### Schema registry

After loading all tables, ingestion writes `sql_db/sql_schemas.json`:

```json
{
  "pts_dataset__pts_data_csv": {
    "source_file": "PTS_dataset/pts_data.csv",
    "columns": [
      {"name": "Country", "type": "TEXT", "sample": ["China", "India", "Brazil"]},
      {"name": "Year", "type": "INTEGER", "sample": [2000, 2005, 2010]},
      {"name": "PTS_A", "type": "REAL", "sample": [4.0, 3.0, 2.5]}
    ],
    "row_count": 15234
  }
}
```

### Type inference

During SQL ingestion, column types are inferred per-column:
- Try `int()` on all non-empty values -> INTEGER
- Try `float()` on all non-empty values -> REAL
- Otherwise -> TEXT
- Empty/NaN values -> NULL

### File locations

- SQLite DB: `sql_db/knowledge_base.db` (gitignored)
- Schema registry: `sql_db/sql_schemas.json` (gitignored)
- Tabular extensions triggering dual ingestion: `.csv`, `.tab`, `.tsv`, `.xlsx`, `.xls`, `.dta`, `.sav`, `.rds`, `.rda`

### Clearing

`ingest.py` already clears ChromaDB on re-run. It also drops all SQLite tables and regenerates `sql_schemas.json`.

## Query Understanding Changes

### Schema injection

When `sql_db/sql_schemas.json` exists, a compact summary is appended to the QU prompt:

```
Available SQL tables:
- pts_dataset__pts_data_csv (15234 rows): Country (TEXT), Year (INTEGER), PTS_A (REAL)
- economic_data__gdp_xlsx (5000 rows): Country (TEXT), Year (INTEGER), GDP (REAL)
```

~50 tokens per table. 10 tables = ~500 tokens. Schema text goes through `_escape_braces()` before prompt injection.

**Graceful degradation:** If `sql_schemas.json` does not exist (no tabular files ingested), schema injection is skipped, `route` always defaults to `"vector"`, and the pipeline behaves identically to the current system.

### Extended output format

The QU prompt instructs the LLM to return two new fields:

```json
{
  "action": "search",
  "route": "sql",
  "search_query": "PTS scores China",
  "display_query": "What are the PTS scores for China along the years?",
  "sql_query": "SELECT Country, Year, PTS_A, PTS_S FROM pts_dataset__pts_data_csv WHERE Country = 'China' ORDER BY Year"
}
```

- `route`: `"sql"` | `"vector"` | `"both"` (default: `"vector"` if omitted — backward compatible)
- `sql_query`: Valid SQLite SELECT query (only present when route includes sql)

### Routing rules

| Query type | Route | Example |
|---|---|---|
| Specific data lookup | `sql` | "PTS scores for China along the years" |
| Aggregation / summary | `sql` | "How many countries are in the dataset?" |
| Data comparison | `sql` | "Compare GDP of China and India in 2020" |
| Conceptual / definitional | `vector` | "What does PTS measure?" |
| Mixed (concept + data) | `both` | "Explain PTS methodology and show China's scores" |

The QU prompt explicitly instructs: "If the user asks about data summarization, counting, averaging, filtering, or any question that requires looking at dataset rows, always set route to `sql` or `both`."

## SQL Retriever

New module `src/sql_retriever.py`:

### `execute_sql_query(sql_query, cfg) -> list[dict]`

- Opens `sql_db/knowledge_base.db` in **read-only mode**: `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`
- **SQL injection protection (two layers):**
  1. Validate: strip whitespace, reject if contains `;`, reject if doesn't start with `SELECT` (case-insensitive)
  2. Read-only SQLite connection (belt and suspenders)
- Executes with row limit (default 200) to prevent overwhelming LLM context
- Returns list of row dicts: `[{"Country": "China", "Year": 2005, "PTS_A": 4.0}, ...]`

### `format_sql_results_as_context(rows, sql_query, source_file) -> str`

```
=== SQL Query Results (PRIMARY — from local dataset) ===

Query: SELECT Country, Year, PTS_A FROM pts_dataset__pts_data_csv WHERE Country = 'China' ORDER BY Year
Source: PTS_dataset/pts_data.csv
Rows returned: 24

[CHUNK-SQL-001] Country = China, Year = 2000, PTS_A = 4.0
[CHUNK-SQL-002] Country = China, Year = 2001, PTS_A = 4.0
[CHUNK-SQL-003] Country = China, Year = 2002, PTS_A = 3.5
...
```

- Uses `[CHUNK-SQL-NNN]` chunk IDs for internal anchoring (consistent with `[CHUNK-LOCAL-NNN]` / `[CHUNK-WEB-NNN]` pattern — never shown to user)
- References the original source file in citations, not the SQL table name

### Integration in `src/retriever.py`

The `retrieve()` function gains `route` and `sql_query` parameters:

```python
def retrieve(query: str, cfg: dict, route: str = "vector", sql_query: str = None) -> dict:
```

- Routes to `retrieve_from_sql()`, `retrieve_from_vectordb()`, or both
- Fallback: if chosen path returns empty, tries the other
- SQL results merged into `build_combined_context()` as a third source type

## Prompt Changes

### System prompt (`SYSTEM_PROMPT_TEMPLATE`)

Update "Do NOT use chunk IDs" instruction:
```
Do NOT use chunk IDs (CHUNK-LOCAL-001, CHUNK-SQL-001, CHUNK-WEB-001, etc.)
```

### Verification prompt

Update check #6:
```
6. Is the source priority respected (CHUNK-LOCAL = CHUNK-SQL > CHUNK-WEB)?
```

SQL results from local files have equal priority with CHUNK-LOCAL (both are local data).

## Config Changes

### New config fields

| Config Path | Read By | Default | Notes |
|---|---|---|---|
| `paths.sql_db` | `src/sql_ingest.py`, `src/sql_retriever.py` | `"sql_db"` | Directory for SQLite DB + schema registry |
| `sql.enabled` | `src/retriever.py`, `src/query_engine.py` | `true` | Can disable if no tabular data |
| `sql.max_rows` | `src/sql_retriever.py` | `200` | Cap on SQL result rows sent to LLM |

### `.gitignore`

Add `sql_db/` alongside existing `chroma_db/`.

## File Changes Summary

### New files
- `src/sql_retriever.py` — SQL execution + result formatting
- `src/sql_ingest.py` — Tabular file -> SQLite loader + schema registry generation
- `sql_db/` — Directory for `knowledge_base.db` + `sql_schemas.json` (gitignored)
- `tests/test_sql_retriever.py` — Tests for SQL execution, validation, formatting
- `tests/test_sql_ingest.py` — Tests for SQLite ingestion, type inference, schema registry

### Modified files
- `src/ingest.py` — Call `sql_ingest` for tabular files during ingestion
- `src/retriever.py` — Add `route`/`sql_query` params, integrate SQL retrieval, merge results
- `src/query_engine.py` — Load schema, inject into QU prompt, parse `route`/`sql_query` from LLM output
- `src/prompts.py` — Extended QU prompt with schema + routing instructions; update system/verification prompts for CHUNK-SQL
- `setup.py` — Add `paths.sql_db`, `sql.enabled`, `sql.max_rows` to generated config
- `app_cli.py` — Pass `route`/`sql_query` from QU result through to retriever
- `app_web.py` — Same as CLI
- `CLAUDE.md` — Document new config fields and SQL architecture
- `README.md` — Document SQL layer feature
- `.gitignore` — Add `sql_db/`

### Unchanged
- `src/verifier.py` — SQL results are just context; 6-layer stack unchanged
- `src/llm/` — No changes
- `src/search/` — No changes
- `src/readers/` — No changes (still produce text for ChromaDB)

## Graceful Degradation

The SQL layer degrades gracefully at every level:

| Failure | Behavior |
|---|---|
| No tabular files ingested | No `sql_schemas.json` -> QU skips schema injection -> always routes to vector -> identical to current system |
| `sql.enabled: false` | QU skips schema injection -> always routes to vector |
| LLM omits `route` field | Defaults to `"vector"` (backward compatible) |
| LLM generates malformed SQL | Execution fails -> returns empty -> fallback to vector search |
| SQL query returns 0 rows | Fallback to vector search |
| Vector search returns 0 results | Fallback to SQL (if schemas exist) |
| `sql_schemas.json` corrupted | Caught, logged, QU skips schema injection |
