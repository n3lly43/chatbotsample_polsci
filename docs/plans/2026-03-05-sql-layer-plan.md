# SQL Layer for Tabular Datasets — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add SQLite-based structured query retrieval alongside existing vector search so tabular data queries (filtering, aggregation, lookups) work correctly.

**Architecture:** Tabular files get dual-ingested into both ChromaDB (text chunks) and SQLite (structured tables). The query understanding layer routes queries to SQL, vector, or both paths with fallback. SQL results are formatted as context and fed through the unchanged 6-layer verification pipeline.

**Tech Stack:** Python 3.11+, SQLite (stdlib), existing ChromaDB/LLM stack

**Design doc:** `docs/plans/2026-03-05-sql-layer-design.md`

---

### Task 1: SQL Ingestion — Helpers (table naming, type inference, samples)

**Files:**
- Create: `src/sql_ingest.py`
- Create: `tests/test_sql_ingest.py`

**Step 1: Write the failing tests**

```python
# tests/test_sql_ingest.py
import pytest


def test_sanitize_table_name_basic():
    from src.sql_ingest import _sanitize_table_name
    assert _sanitize_table_name("PTS_dataset", "pts_data", ".csv") == "pts_dataset__pts_data_csv"


def test_sanitize_table_name_with_sheet():
    from src.sql_ingest import _sanitize_table_name
    result = _sanitize_table_name("econ", "gdp", ".xlsx", "Sheet1")
    assert result == "econ__gdp_xlsx_sheet1"


def test_sanitize_table_name_special_chars():
    from src.sql_ingest import _sanitize_table_name
    result = _sanitize_table_name("my-data", "file (2)", ".csv")
    assert result == "my_data__file_2_csv"
    assert result[0].isalpha()


def test_sanitize_table_name_starts_with_number():
    from src.sql_ingest import _sanitize_table_name
    result = _sanitize_table_name("123data", "file", ".csv")
    assert result[0].isalpha()


def test_infer_column_type_integer():
    from src.sql_ingest import _infer_column_type
    assert _infer_column_type(["1", "2", "3", None, ""]) == "INTEGER"


def test_infer_column_type_real():
    from src.sql_ingest import _infer_column_type
    assert _infer_column_type(["1.5", "2.0", "3.7"]) == "REAL"


def test_infer_column_type_text():
    from src.sql_ingest import _infer_column_type
    assert _infer_column_type(["China", "India", "Brazil"]) == "TEXT"


def test_infer_column_type_mixed_defaults_text():
    from src.sql_ingest import _infer_column_type
    assert _infer_column_type(["1", "two", "3"]) == "TEXT"


def test_infer_column_type_empty():
    from src.sql_ingest import _infer_column_type
    assert _infer_column_type([None, "", "nan"]) == "TEXT"


def test_get_sample_values():
    from src.sql_ingest import _get_sample_values
    samples = _get_sample_values(["China", "India", "China", "Brazil", None, ""], n=3)
    assert samples == ["China", "India", "Brazil"]


def test_get_sample_values_fewer_than_n():
    from src.sql_ingest import _get_sample_values
    samples = _get_sample_values(["a", None, "a"], n=3)
    assert samples == ["a"]
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sql_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.sql_ingest'`

**Step 3: Write minimal implementation**

```python
# src/sql_ingest.py
"""SQL ingestion: load tabular files into SQLite for structured queries."""

import re

# Extensions that trigger SQL ingestion (tabular formats)
SQL_EXTENSIONS = {".csv", ".tab", ".tsv", ".xlsx", ".xls", ".dta", ".sav", ".rds", ".rda"}


def _sanitize_table_name(dataset: str, stem: str, ext: str, sheet: str = None) -> str:
    """Convert dataset/filename/ext into a valid SQL table identifier."""
    name = f"{dataset}__{stem}_{ext.lstrip('.')}"
    if sheet:
        name += f"_{sheet}"
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    if not name or not name[0].isalpha():
        name = "t_" + name
    return name


def _infer_column_type(values: list) -> str:
    """Infer SQLite column type from a list of raw string values."""
    non_empty = [v for v in values if v is not None and str(v).strip() and str(v).lower() != "nan"]
    if not non_empty:
        return "TEXT"
    # Try INTEGER
    try:
        for v in non_empty:
            int(str(v).strip())
        return "INTEGER"
    except (ValueError, TypeError):
        pass
    # Try REAL
    try:
        for v in non_empty:
            float(str(v).strip())
        return "REAL"
    except (ValueError, TypeError):
        pass
    return "TEXT"


def _get_sample_values(values: list, n: int = 3) -> list:
    """Get up to n unique non-empty sample values."""
    seen = set()
    samples = []
    for v in values:
        if v is not None and str(v).strip() and str(v).lower() != "nan":
            v_str = str(v).strip()
            if v_str not in seen:
                seen.add(v_str)
                samples.append(v_str)
                if len(samples) >= n:
                    break
    return samples
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sql_ingest.py -v`
Expected: 11 PASSED

**Step 5: Commit**

```bash
git add src/sql_ingest.py tests/test_sql_ingest.py
git commit -m "feat: add SQL ingestion helpers — table naming, type inference, samples"
```

---

### Task 2: SQL Ingestion — Core ingestion function

**Files:**
- Modify: `src/sql_ingest.py`
- Modify: `tests/test_sql_ingest.py`

**Step 1: Write the failing tests**

Append to `tests/test_sql_ingest.py`:

```python
import csv
import json
import sqlite3


def test_ingest_to_sql_creates_db_and_schema(tmp_path):
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql

    # Create a CSV file
    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "testds"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "data.csv"
    csv_file.write_text("Country,Year,Score\nChina,2005,4.0\nIndia,2005,3.0\n")

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}}
    files = [(Path(csv_file), "testds")]

    schema = ingest_to_sql(files, str(kb_dir), cfg)

    # Check DB was created
    db_path = sql_db_dir / "knowledge_base.db"
    assert db_path.exists()

    # Check schema registry
    schema_path = sql_db_dir / "sql_schemas.json"
    assert schema_path.exists()
    with open(schema_path) as f:
        saved = json.load(f)
    assert len(saved) == 1
    table_name = list(saved.keys())[0]
    assert "testds" in table_name
    assert saved[table_name]["row_count"] == 2
    assert len(saved[table_name]["columns"]) == 3

    # Check data in SQLite
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(f'SELECT * FROM "{table_name}"').fetchall()
    conn.close()
    assert len(rows) == 2
    assert rows[0][0] == "China"


def test_ingest_to_sql_type_inference(tmp_path):
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql

    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "ds"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "typed.csv"
    csv_file.write_text("Name,Year,Score\nChina,2005,4.5\nIndia,2006,3.0\n")

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}}
    files = [(Path(csv_file), "ds")]

    schema = ingest_to_sql(files, str(kb_dir), cfg)
    table_name = list(schema.keys())[0]

    # Name=TEXT, Year=INTEGER, Score=REAL
    col_types = {c["name"]: c["type"] for c in schema[table_name]["columns"]}
    assert col_types["Name"] == "TEXT"
    assert col_types["Year"] == "INTEGER"
    assert col_types["Score"] == "REAL"


def test_ingest_to_sql_no_tabular_files(tmp_path):
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}}
    # Pass empty list (no tabular files)
    schema = ingest_to_sql([], str(tmp_path), cfg)
    assert schema == {}


def test_ingest_to_sql_clears_on_rerun(tmp_path):
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql

    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "ds"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "data.csv"
    csv_file.write_text("A,B\n1,2\n3,4\n")

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}}
    files = [(Path(csv_file), "ds")]

    # First run
    ingest_to_sql(files, str(kb_dir), cfg)
    # Second run — should not duplicate
    schema = ingest_to_sql(files, str(kb_dir), cfg)
    table_name = list(schema.keys())[0]
    assert schema[table_name]["row_count"] == 2
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sql_ingest.py::test_ingest_to_sql_creates_db_and_schema -v`
Expected: FAIL — `ImportError: cannot import name 'ingest_to_sql'`

**Step 3: Write the implementation**

Add to `src/sql_ingest.py`:

```python
import csv
import json
import os
import sqlite3
from pathlib import Path


def _load_rows_from_csv(file_path: str, ext: str) -> list[tuple]:
    """Load CSV/TSV/TAB into (sheet_or_name, headers, rows) tuples."""
    delimiter = "\t" if ext in (".tab", ".tsv") else ","
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        all_rows = list(reader)
    if len(all_rows) < 2:
        return []
    headers = [h.strip().strip('"') for h in all_rows[0]]
    return [(None, headers, all_rows[1:])]


def _load_rows_from_excel(file_path: str, ext: str) -> list[tuple]:
    """Load Excel into (sheet_name, headers, rows) tuples."""
    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        results = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            all_rows = list(ws.iter_rows(values_only=True))
            if len(all_rows) < 2:
                continue
            headers = [str(h) if h is not None else "" for h in all_rows[0]]
            rows = [[str(c) if c is not None else "" for c in row] for row in all_rows[1:]]
            results.append((sheet_name, headers, rows))
        wb.close()
        return results
    else:  # .xls
        import xlrd
        wb = xlrd.open_workbook(file_path)
        results = []
        for sheet_idx in range(wb.nsheets):
            ws = wb.sheet_by_index(sheet_idx)
            if ws.nrows < 2:
                continue
            headers = [str(ws.cell_value(0, c)) for c in range(ws.ncols)]
            rows = [[str(ws.cell_value(r, c)) for c in range(ws.ncols)] for r in range(1, ws.nrows)]
            results.append((ws.name, headers, rows))
        return results


def _load_rows_from_stata(file_path: str) -> list[tuple]:
    """Load Stata .dta into (None, headers, rows) tuples."""
    import pyreadstat
    df, _meta = pyreadstat.read_dta(file_path)
    headers = list(df.columns)
    rows = [[str(v) for v in row] for row in df.values.tolist()]
    return [(None, headers, rows)]


def _load_rows_from_spss(file_path: str) -> list[tuple]:
    """Load SPSS .sav into (None, headers, rows) tuples."""
    import pyreadstat
    df, _meta = pyreadstat.read_sav(file_path)
    headers = list(df.columns)
    rows = [[str(v) for v in row] for row in df.values.tolist()]
    return [(None, headers, rows)]


def _load_rows_from_rdata(file_path: str) -> list[tuple]:
    """Load R data files into (object_name, headers, rows) tuples."""
    import pyreadr
    result = pyreadr.read_r(file_path)
    tables = []
    for name, df in result.items():
        headers = list(df.columns)
        rows = [[str(v) for v in row] for row in df.values.tolist()]
        tables.append((name, headers, rows))
    return tables


def _load_tabular_file(file_path: str, ext: str) -> list[tuple]:
    """Dispatch to the correct loader based on extension.

    Returns list of (sheet_or_name, headers, rows) tuples.
    """
    if ext in (".csv", ".tab", ".tsv"):
        return _load_rows_from_csv(file_path, ext)
    if ext in (".xlsx", ".xls"):
        return _load_rows_from_excel(file_path, ext)
    if ext == ".dta":
        return _load_rows_from_stata(file_path)
    if ext == ".sav":
        return _load_rows_from_spss(file_path)
    if ext in (".rds", ".rda"):
        return _load_rows_from_rdata(file_path)
    return []


def _sanitize_column_name(name: str) -> str:
    """Sanitize a column name into a valid SQL identifier."""
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_")
    if not safe or not safe[0].isalpha():
        safe = "col_" + safe
    return safe


def ingest_to_sql(files: list[tuple], documents_dir: str, cfg: dict) -> dict:
    """Ingest tabular files into SQLite and generate schema registry.

    Args:
        files: List of (file_path, dataset_name) tuples.
        documents_dir: Root documents directory.
        cfg: App config dict.

    Returns:
        Schema registry dict (also saved to sql_schemas.json).
    """
    sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
    if not os.path.isabs(sql_db_dir):
        project_root = Path(__file__).resolve().parent.parent
        sql_db_dir = os.path.join(str(project_root), sql_db_dir)

    os.makedirs(sql_db_dir, exist_ok=True)
    db_path = os.path.join(sql_db_dir, "knowledge_base.db")
    schema_path = os.path.join(sql_db_dir, "sql_schemas.json")

    # Filter to tabular files only
    tabular_files = [(fp, ds) for fp, ds in files if fp.suffix.lower() in SQL_EXTENSIONS]

    if not tabular_files:
        if os.path.exists(schema_path):
            os.remove(schema_path)
        return {}

    # Clear existing DB
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    schema_registry = {}

    for file_path, dataset_name in tabular_files:
        ext = file_path.suffix.lower()
        rel_path = file_path.relative_to(documents_dir)
        source_file = str(rel_path)

        try:
            tables = _load_tabular_file(str(file_path), ext)
        except Exception as e:
            print(f"  SQL ingest error for {file_path.name}: {e}")
            continue

        for sheet_or_name, headers, rows in tables:
            table_name = _sanitize_table_name(dataset_name, file_path.stem, ext, sheet_or_name)

            # Infer column types and collect samples
            safe_headers = [_sanitize_column_name(h) for h in headers]
            col_types = []
            col_samples = []
            for col_idx in range(len(headers)):
                col_values = [row[col_idx] if col_idx < len(row) else None for row in rows]
                col_types.append(_infer_column_type(col_values))
                col_samples.append(_get_sample_values(col_values))

            # Create table
            col_defs = ", ".join(f'"{h}" {t}' for h, t in zip(safe_headers, col_types))
            conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

            # Insert rows
            placeholders = ", ".join(["?"] * len(safe_headers))
            insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'

            for row in rows:
                values = []
                for col_idx, col_type in enumerate(col_types):
                    raw = row[col_idx] if col_idx < len(row) else None
                    if raw is None or str(raw).strip() == "" or str(raw).lower() == "nan":
                        values.append(None)
                    elif col_type == "INTEGER":
                        try:
                            values.append(int(float(str(raw).strip())))
                        except (ValueError, TypeError):
                            values.append(None)
                    elif col_type == "REAL":
                        try:
                            values.append(float(str(raw).strip()))
                        except (ValueError, TypeError):
                            values.append(None)
                    else:
                        values.append(str(raw).strip())
                conn.execute(insert_sql, values)

            conn.commit()

            row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

            schema_registry[table_name] = {
                "source_file": source_file,
                "columns": [
                    {
                        "name": safe_headers[i],
                        "original_name": headers[i],
                        "type": col_types[i],
                        "sample": col_samples[i],
                    }
                    for i in range(len(headers))
                ],
                "row_count": row_count,
            }
            print(f"  SQL: {table_name} ({row_count} rows, {len(headers)} columns)")

    conn.close()

    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema_registry, f, indent=2, default=str)

    return schema_registry
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sql_ingest.py -v`
Expected: 15 PASSED

**Step 5: Commit**

```bash
git add src/sql_ingest.py tests/test_sql_ingest.py
git commit -m "feat: add SQL ingestion — load tabular files into SQLite with schema registry"
```

---

### Task 3: SQL Retriever — Validation and execution

**Files:**
- Create: `src/sql_retriever.py`
- Create: `tests/test_sql_retriever.py`

**Step 1: Write the failing tests**

```python
# tests/test_sql_retriever.py
import pytest
import json
import sqlite3


def test_validate_sql_rejects_non_select():
    from src.sql_retriever import _validate_sql
    assert _validate_sql("DROP TABLE users") is False
    assert _validate_sql("INSERT INTO t VALUES (1)") is False
    assert _validate_sql("UPDATE t SET x=1") is False
    assert _validate_sql("DELETE FROM t") is False


def test_validate_sql_rejects_semicolons():
    from src.sql_retriever import _validate_sql
    assert _validate_sql("SELECT 1; DROP TABLE users") is False


def test_validate_sql_accepts_select():
    from src.sql_retriever import _validate_sql
    assert _validate_sql("SELECT * FROM t") is True
    assert _validate_sql("  select Country, Year from t WHERE x = 1  ") is True
    assert _validate_sql("SELECT COUNT(*) FROM t GROUP BY x") is True


def test_validate_sql_rejects_empty():
    from src.sql_retriever import _validate_sql
    assert _validate_sql("") is False
    assert _validate_sql("   ") is False


def test_execute_sql_query_returns_rows(tmp_path):
    from src.sql_retriever import execute_sql_query

    # Create a test DB
    db_path = tmp_path / "sql_db" / "knowledge_base.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (Country TEXT, Year INTEGER, Score REAL)")
    conn.execute("INSERT INTO t VALUES ('China', 2005, 4.0)")
    conn.execute("INSERT INTO t VALUES ('India', 2005, 3.0)")
    conn.commit()
    conn.close()

    cfg = {"paths": {"sql_db": str(tmp_path / "sql_db")}, "sql": {"max_rows": 200}}
    rows = execute_sql_query("SELECT * FROM t WHERE Country = 'China'", cfg)
    assert len(rows) == 1
    assert rows[0]["Country"] == "China"
    assert rows[0]["Score"] == 4.0


def test_execute_sql_query_respects_max_rows(tmp_path):
    from src.sql_retriever import execute_sql_query

    db_path = tmp_path / "sql_db" / "knowledge_base.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (x INTEGER)")
    for i in range(100):
        conn.execute("INSERT INTO t VALUES (?)", (i,))
    conn.commit()
    conn.close()

    cfg = {"paths": {"sql_db": str(tmp_path / "sql_db")}, "sql": {"max_rows": 5}}
    rows = execute_sql_query("SELECT * FROM t", cfg)
    assert len(rows) == 5


def test_execute_sql_query_rejects_non_select(tmp_path):
    from src.sql_retriever import execute_sql_query

    db_path = tmp_path / "sql_db" / "knowledge_base.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()

    cfg = {"paths": {"sql_db": str(tmp_path / "sql_db")}}
    rows = execute_sql_query("DROP TABLE t", cfg)
    assert rows == []


def test_execute_sql_query_handles_bad_sql(tmp_path):
    from src.sql_retriever import execute_sql_query

    db_path = tmp_path / "sql_db" / "knowledge_base.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()

    cfg = {"paths": {"sql_db": str(tmp_path / "sql_db")}}
    rows = execute_sql_query("SELECT * FROM nonexistent_table", cfg)
    assert rows == []


def test_execute_sql_query_no_db(tmp_path):
    from src.sql_retriever import execute_sql_query

    cfg = {"paths": {"sql_db": str(tmp_path / "sql_db_missing")}}
    rows = execute_sql_query("SELECT 1", cfg)
    assert rows == []
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sql_retriever.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.sql_retriever'`

**Step 3: Write the implementation**

```python
# src/sql_retriever.py
"""SQL retriever: execute validated queries against the SQLite knowledge base."""

import os
import sqlite3
from pathlib import Path


def _validate_sql(sql: str) -> bool:
    """Validate that a SQL string is a safe SELECT query.

    Rejects non-SELECT statements and queries containing semicolons
    (which could chain dangerous statements).
    """
    stripped = sql.strip()
    if not stripped:
        return False
    if ";" in stripped:
        return False
    if not stripped.upper().startswith("SELECT"):
        return False
    return True


def _get_db_path(cfg: dict) -> str:
    """Resolve the SQLite database path from config."""
    sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
    if not os.path.isabs(sql_db_dir):
        project_root = Path(__file__).resolve().parent.parent
        sql_db_dir = os.path.join(str(project_root), sql_db_dir)
    return os.path.join(sql_db_dir, "knowledge_base.db")


def execute_sql_query(sql_query: str, cfg: dict) -> list[dict]:
    """Execute a validated SELECT query against the knowledge base SQLite DB.

    Args:
        sql_query: A SQL SELECT query (generated by the LLM).
        cfg: App config dict.

    Returns:
        List of row dicts, or empty list on any error.
    """
    if not _validate_sql(sql_query):
        return []

    db_path = _get_db_path(cfg)
    if not os.path.exists(db_path):
        return []

    max_rows = cfg.get("sql", {}).get("max_rows", 200)

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql_query)
        rows = cursor.fetchmany(max_rows)
        result = [dict(row) for row in rows]
        conn.close()
        return result
    except Exception:
        return []
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sql_retriever.py -v`
Expected: 9 PASSED

**Step 5: Commit**

```bash
git add src/sql_retriever.py tests/test_sql_retriever.py
git commit -m "feat: add SQL retriever — validated read-only query execution"
```

---

### Task 4: SQL Retriever — Result formatting and schema summary

**Files:**
- Modify: `src/sql_retriever.py`
- Modify: `tests/test_sql_retriever.py`

**Step 1: Write the failing tests**

Append to `tests/test_sql_retriever.py`:

```python
def test_format_sql_results_empty():
    from src.sql_retriever import format_sql_results_as_context
    assert format_sql_results_as_context([], "SELECT 1", "data.csv") == ""


def test_format_sql_results_basic():
    from src.sql_retriever import format_sql_results_as_context
    rows = [
        {"Country": "China", "Year": 2005, "PTS_A": 4.0},
        {"Country": "China", "Year": 2006, "PTS_A": 3.5},
    ]
    result = format_sql_results_as_context(rows, "SELECT * FROM t", "PTS_dataset/pts_data.csv")
    assert "[CHUNK-SQL-001]" in result
    assert "[CHUNK-SQL-002]" in result
    assert "China" in result
    assert "PTS_dataset/pts_data.csv" in result
    assert "PRIMARY" in result
    assert "SELECT * FROM t" in result
    assert "Rows returned: 2" in result


def test_build_schema_summary_empty():
    from src.sql_retriever import build_schema_summary
    assert build_schema_summary({}) == ""


def test_build_schema_summary_basic():
    from src.sql_retriever import build_schema_summary
    schema = {
        "test_table": {
            "source_file": "data.csv",
            "columns": [
                {"name": "Country", "type": "TEXT", "sample": ["China", "India"]},
                {"name": "Year", "type": "INTEGER", "sample": [2005, 2010]},
            ],
            "row_count": 100,
        }
    }
    result = build_schema_summary(schema)
    assert "test_table" in result
    assert "100 rows" in result
    assert "Country (TEXT)" in result
    assert "Year (INTEGER)" in result


def test_lookup_source_file():
    from src.sql_retriever import _lookup_source_file
    schema = {
        "ds__data_csv": {"source_file": "ds/data.csv", "columns": [], "row_count": 0},
    }
    assert _lookup_source_file("ds__data_csv", schema) == "ds/data.csv"
    assert _lookup_source_file("unknown", schema) == "unknown"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sql_retriever.py::test_format_sql_results_basic -v`
Expected: FAIL — `ImportError: cannot import name 'format_sql_results_as_context'`

**Step 3: Add to `src/sql_retriever.py`**

```python
def format_sql_results_as_context(
    rows: list[dict], sql_query: str, source_file: str,
) -> str:
    """Format SQL result rows as context for the verification pipeline.

    Uses [CHUNK-SQL-NNN] IDs for internal anchoring, consistent with
    CHUNK-LOCAL and CHUNK-WEB patterns.
    """
    if not rows:
        return ""

    parts = [
        "=== SQL Query Results (PRIMARY — from local dataset) ===\n",
        f"Query: {sql_query}",
        f"Source: {source_file}",
        f"Rows returned: {len(rows)}\n",
    ]
    for i, row in enumerate(rows, 1):
        fields = ", ".join(f"{k} = {v}" for k, v in row.items())
        parts.append(f"[CHUNK-SQL-{i:03d}] {fields}")
    return "\n".join(parts)


def _lookup_source_file(table_name: str, schema: dict) -> str:
    """Look up the original source file for a SQL table name."""
    entry = schema.get(table_name)
    if entry:
        return entry.get("source_file", table_name)
    return table_name


def build_schema_summary(schema: dict) -> str:
    """Build a compact schema summary for injection into the QU prompt.

    Format:
        Available SQL tables:
        - table_name (N rows): col1 (TYPE), col2 (TYPE), ...
    """
    if not schema:
        return ""

    lines = ["Available SQL tables:"]
    for table_name, info in schema.items():
        cols = ", ".join(
            f"{c['name']} ({c['type']})" for c in info.get("columns", [])
        )
        row_count = info.get("row_count", 0)
        lines.append(f"- {table_name} ({row_count} rows): {cols}")
    return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sql_retriever.py -v`
Expected: 14 PASSED

**Step 5: Commit**

```bash
git add src/sql_retriever.py tests/test_sql_retriever.py
git commit -m "feat: add SQL result formatting and schema summary builder"
```

---

### Task 5: Prompt updates — QU prompt + system + verification

**Files:**
- Modify: `src/prompts.py:124-164` (QU prompt template)
- Modify: `src/prompts.py:43-44` (system prompt — chunk ID line)
- Modify: `src/prompts.py:106` (verification prompt — check #6)
- Modify: `tests/test_prompts.py` (if it exists; otherwise create)

**Context:** Read `src/prompts.py` before editing. The QU prompt template uses `str.format()` with `{{` and `}}` for literal JSON braces.

**Step 1: Write the failing tests**

Create or append to `tests/test_prompts.py`:

```python
# tests/test_prompts.py
import pytest


def test_qu_prompt_includes_schema_when_provided():
    from src.prompts import build_query_understanding_prompt
    schema_summary = "Available SQL tables:\n- t (100 rows): x (TEXT)"
    prompt = build_query_understanding_prompt(
        "test query", "research", [], sql_schema_summary=schema_summary,
    )
    assert "Available SQL tables" in prompt
    assert "route" in prompt
    assert "sql_query" in prompt


def test_qu_prompt_no_schema_no_sql_fields():
    from src.prompts import build_query_understanding_prompt
    prompt = build_query_understanding_prompt("test query", "research", [])
    assert "Available SQL tables" not in prompt


def test_system_prompt_mentions_chunk_sql():
    from src.prompts import build_prompt
    prompt = build_prompt("context", "Bot", "research")
    assert "CHUNK-SQL" in prompt


def test_verification_prompt_sql_priority():
    from src.prompts import build_verification_prompt
    prompt = build_verification_prompt("resp", "ctx", [], [])
    assert "CHUNK-SQL" in prompt
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: FAIL — `build_query_understanding_prompt() got an unexpected keyword argument 'sql_schema_summary'`

**Step 3: Edit `src/prompts.py`**

Three changes needed:

**3a.** Update `SYSTEM_PROMPT_TEMPLATE` (line ~43): Change the chunk ID line from:
```
Do NOT use chunk IDs (CHUNK-LOCAL-001, CHUNK-WEB-001, etc.)
```
to:
```
Do NOT use chunk IDs (CHUNK-LOCAL-001, CHUNK-SQL-001, CHUNK-WEB-001, etc.)
```

**3b.** Update `VERIFICATION_PROMPT_TEMPLATE` (line ~106): Change check #6 from:
```
6. Is the source priority respected (CHUNK-LOCAL > CHUNK-WEB)?
```
to:
```
6. Is the source priority respected (CHUNK-LOCAL = CHUNK-SQL > CHUNK-WEB)?
```

**3c.** Update `QUERY_UNDERSTANDING_PROMPT_TEMPLATE` — add SQL routing instructions and a `{sql_schema}` placeholder. Add this block after the CLARIFY rules, before the CONVERSATION HISTORY section:

```
{sql_routing_block}
```

Where `sql_routing_block` is either empty (no schemas) or:

```
SQL ROUTING:
You have access to structured SQL tables in addition to vector search.
When choosing a route:
- "sql" — for data lookups, filtering, aggregation, counting, comparisons
  (e.g., "PTS scores for China", "how many countries", "average GDP")
- "vector" — for conceptual, definitional, or methodology questions
  (e.g., "what does PTS measure?", "explain the methodology")
- "both" — for mixed questions combining concepts with data
  (e.g., "explain PTS methodology and show China's scores")

IMPORTANT: If the user asks about data summarization, counting, averaging,
filtering, or any question that requires looking at dataset rows, ALWAYS
set route to "sql" or "both".

When route is "sql" or "both", also provide a valid SQLite SELECT query
in the "sql_query" field. Use only table/column names from the schema below.

{schema_text}
```

Also update the JSON output format in the template to include `route` and `sql_query`:

```
Respond in JSON:
{{
  "action": "search" or "clarify",
  "route": "vector" or "sql" or "both",
  "search_query": "keyword-optimized query for vector search",
  "display_query": "clear natural-language question for the AI to answer",
  "sql_query": "SQLite SELECT query (only when route is sql or both)",
  "clarification_question": "question to ask (only if action is clarify)",
  "reasoning": "one sentence explaining your choice"
}}
```

**3d.** Update `build_query_understanding_prompt()` signature to accept `sql_schema_summary`:

```python
def build_query_understanding_prompt(
    query: str, domain: str, history: list[dict],
    sql_schema_summary: str = "",
) -> str:
```

Build the `sql_routing_block`: if `sql_schema_summary` is non-empty, format the full SQL routing instructions with schema. Otherwise use empty string. Pass it through `_escape_braces()`.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_prompts.py -v`
Expected: 4 PASSED

Then run full suite to make sure nothing broke:

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/prompts.py tests/test_prompts.py
git commit -m "feat: update prompts for SQL routing, CHUNK-SQL IDs, and schema injection"
```

---

### Task 6: Query engine — Schema loading and route/sql_query parsing

**Files:**
- Modify: `src/query_engine.py:10-72`
- Modify: `tests/test_query_engine.py` (read first to see existing tests)

**Context:** Read `src/query_engine.py` and `tests/test_query_engine.py` before editing. The QU layer already parses `action`, `search_query`, `display_query`. We need to also parse `route` and `sql_query` from the LLM output, and load the schema summary for prompt injection.

**Step 1: Write the failing tests**

Append to `tests/test_query_engine.py` (or create if it doesn't exist):

```python
def test_parse_qu_result_with_route_and_sql():
    from src.query_engine import _parse_qu_result
    raw = '{"action": "search", "route": "sql", "search_query": "PTS China", "display_query": "PTS scores for China?", "sql_query": "SELECT * FROM t", "reasoning": "data lookup"}'
    result = _parse_qu_result(raw, "original")
    assert result["route"] == "sql"
    assert result["sql_query"] == "SELECT * FROM t"


def test_parse_qu_result_defaults_route_to_vector():
    from src.query_engine import _parse_qu_result
    raw = '{"action": "search", "search_query": "test", "display_query": "test?"}'
    result = _parse_qu_result(raw, "original")
    assert result["route"] == "vector"
    assert result.get("sql_query") is None


def test_load_sql_schema_missing_file():
    from src.query_engine import _load_sql_schema_summary
    result = _load_sql_schema_summary("/nonexistent/path/sql_db")
    assert result == ""


def test_load_sql_schema_valid_file(tmp_path):
    import json
    from src.query_engine import _load_sql_schema_summary
    schema_dir = tmp_path / "sql_db"
    schema_dir.mkdir()
    schema = {
        "test_table": {
            "source_file": "data.csv",
            "columns": [{"name": "x", "type": "TEXT", "sample": ["a"]}],
            "row_count": 10,
        }
    }
    (schema_dir / "sql_schemas.json").write_text(json.dumps(schema))
    result = _load_sql_schema_summary(str(schema_dir))
    assert "test_table" in result
    assert "10 rows" in result
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_query_engine.py::test_parse_qu_result_with_route_and_sql -v`
Expected: FAIL

**Step 3: Edit `src/query_engine.py`**

**3a.** Add `_load_sql_schema_summary()` function:

```python
import json as _json_mod

def _load_sql_schema_summary(sql_db_dir: str) -> str:
    """Load SQL schema summary from sql_schemas.json if it exists."""
    import os
    schema_path = os.path.join(sql_db_dir, "sql_schemas.json")
    if not os.path.exists(schema_path):
        return ""
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = _json_mod.load(f)
        from src.sql_retriever import build_schema_summary
        return build_schema_summary(schema)
    except Exception:
        return ""
```

**3b.** Update `understand_query()` to load schema and pass to prompt builder:

```python
# After getting domain and max_history, add:
sql_enabled = cfg.get("sql", {}).get("enabled", True)
schema_summary = ""
if sql_enabled:
    sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
    if not os.path.isabs(sql_db_dir):
        from pathlib import Path as _Path
        project_root = _Path(__file__).resolve().parent.parent
        sql_db_dir = os.path.join(str(project_root), sql_db_dir)
    schema_summary = _load_sql_schema_summary(sql_db_dir)

prompt = build_query_understanding_prompt(
    user_query, domain, history, sql_schema_summary=schema_summary,
)
```

Add `import os` at the top if not already there.

**3c.** Update `_parse_qu_result()` to extract `route` and `sql_query`:

In the `action == "search"` branch, after extracting `search_query` and `display_query`, add:

```python
route = parsed.get("route", "vector")
if route not in ("sql", "vector", "both"):
    route = "vector"
sql_query = parsed.get("sql_query") if route in ("sql", "both") else None
```

And include both in the return dict:

```python
return {
    "action": "search",
    "search_query": search_query,
    "display_query": display_query,
    "original_query": original_query,
    "route": route,
    "sql_query": sql_query,
}
```

Also update all other return paths (fallbacks, clarify) to include `"route": "vector"` and `"sql_query": None`.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_query_engine.py -v`
Expected: All PASS

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/query_engine.py tests/test_query_engine.py
git commit -m "feat: add SQL schema loading and route/sql_query parsing to query engine"
```

---

### Task 7: Retriever integration — Routing, fallback, SQL context merging

**Files:**
- Modify: `src/retriever.py:202-227` (the `retrieve()` function)
- Modify: `src/retriever.py:171-199` (`build_combined_context()`)
- Modify: `tests/test_retriever.py`

**Context:** Read `src/retriever.py` before editing. The `retrieve()` function currently takes `(query, cfg)` and returns `{context, db_results, web_results, has_sources}`. We need to add `route` and `sql_query` parameters, implement routing with fallback, and update `build_combined_context()` to accept SQL results.

**Step 1: Write the failing tests**

Append to `tests/test_retriever.py`:

```python
def test_build_combined_context_with_sql():
    from src.retriever import build_combined_context
    sql = "=== SQL Query Results (PRIMARY) ===\n[CHUNK-SQL-001] x = 1"
    db = [{"text": "data", "metadata": {"source": "f.pdf", "dataset": "d", "page": "1"}, "distance": 0.1}]
    result = build_combined_context(db, [], sql_context=sql)
    assert "SQL Query Results" in result
    assert "CHUNK-LOCAL" in result


def test_build_combined_context_sql_only():
    from src.retriever import build_combined_context
    sql = "=== SQL Query Results (PRIMARY) ===\n[CHUNK-SQL-001] x = 1"
    result = build_combined_context([], [], sql_context=sql)
    assert "SQL Query Results" in result


def test_build_combined_context_sql_no_sources():
    from src.retriever import build_combined_context
    result = build_combined_context([], [], sql_context="")
    assert "No relevant" in result or "don't have" in result
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_retriever.py::test_build_combined_context_with_sql -v`
Expected: FAIL — `build_combined_context() got an unexpected keyword argument 'sql_context'`

**Step 3: Edit `src/retriever.py`**

**3a.** Update `build_combined_context()` to accept `sql_context`:

```python
def build_combined_context(
    db_results: list[dict], web_results: list[dict], sql_context: str = "",
) -> str:
    """Build combined context string from local, SQL, and web results."""
    db_context = format_db_results_as_context(db_results)
    web_context = format_web_results_as_context(web_results)

    has_local = bool(db_results) or bool(sql_context)
    has_web = bool(web_results)

    if not has_local and not has_web:
        return NO_SOURCES_REFUSAL

    parts = []

    if has_local and not has_web:
        parts.append("ONLY use the local sources below. Do not add any outside knowledge.\n")

    if has_local and has_web:
        parts.append(
            "IMPORTANT: Local document sources are the PRIMARY authority. "
            "Web sources are SUPPLEMENTARY only. If any web source contradicts "
            "a local document, trust the local document.\n"
        )

    if not has_local and has_web:
        parts.append(
            "NOTE: No local documents are indexed. All sources below come from "
            "academic web search. You MUST include the URL link for every source cited. "
            "State clearly that you have no curated local sources.\n"
        )

    if sql_context:
        parts.append(sql_context)
    if db_context:
        parts.append(db_context)
    if web_context:
        parts.append(web_context)

    return "\n\n".join(parts)
```

**3b.** Update `retrieve()` to accept `route` and `sql_query`, implement routing:

```python
def retrieve(
    query: str, cfg: dict, route: str = "vector", sql_query: str = None,
) -> dict:
    """Run retrieval with SQL/vector routing and fallback.

    Returns dict with: context, db_results, web_results, sql_results, has_sources.
    """
    sql_enabled = cfg.get("sql", {}).get("enabled", True)
    sql_context = ""
    sql_rows = []

    # ── SQL retrieval ────────────────────────────────────────────────
    if sql_enabled and route in ("sql", "both") and sql_query:
        from src.sql_retriever import execute_sql_query, format_sql_results_as_context, _lookup_source_file
        sql_rows = execute_sql_query(sql_query, cfg)
        if sql_rows:
            # Look up source file from schema
            import json as _json
            import os
            sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
            if not os.path.isabs(sql_db_dir):
                from pathlib import Path
                project_root = Path(__file__).resolve().parent.parent
                sql_db_dir = os.path.join(str(project_root), sql_db_dir)
            schema_path = os.path.join(sql_db_dir, "sql_schemas.json")
            schema = {}
            if os.path.exists(schema_path):
                try:
                    with open(schema_path) as f:
                        schema = _json.load(f)
                except Exception:
                    pass
            # Extract table name from query for source lookup
            table_name = _extract_table_from_query(sql_query)
            source_file = _lookup_source_file(table_name, schema)
            sql_context = format_sql_results_as_context(sql_rows, sql_query, source_file)

    # ── Vector retrieval ─────────────────────────────────────────────
    db_results = []
    if route in ("vector", "both") or (route == "sql" and not sql_rows):
        db_results = retrieve_from_vectordb(query, cfg)

    # ── Fallback: vector found nothing, try SQL ──────────────────────
    if sql_enabled and not db_results and not sql_rows and route == "vector" and sql_query:
        from src.sql_retriever import execute_sql_query, format_sql_results_as_context, _lookup_source_file
        sql_rows = execute_sql_query(sql_query, cfg)
        if sql_rows:
            import json as _json, os
            sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
            if not os.path.isabs(sql_db_dir):
                from pathlib import Path
                project_root = Path(__file__).resolve().parent.parent
                sql_db_dir = os.path.join(str(project_root), sql_db_dir)
            schema_path = os.path.join(sql_db_dir, "sql_schemas.json")
            schema = {}
            if os.path.exists(schema_path):
                try:
                    with open(schema_path) as f:
                        schema = _json.load(f)
                except Exception:
                    pass
            table_name = _extract_table_from_query(sql_query)
            source_file = _lookup_source_file(table_name, schema)
            sql_context = format_sql_results_as_context(sql_rows, sql_query, source_file)

    # ── Web search ───────────────────────────────────────────────────
    web_enabled = cfg.get("web_search", {}).get("enabled", False)
    web_results = []
    if web_enabled:
        backend = cfg.get("web_search", {}).get("backend", "semantic_scholar")
        max_results = cfg.get("web_search", {}).get("max_results", 5)
        if not db_results and not sql_rows:
            max_results *= 2
        web_results = search(query, backend=backend, limit=max_results)

    combined_context = build_combined_context(db_results, web_results, sql_context=sql_context)
    has_sources = bool(db_results) or bool(web_results) or bool(sql_rows)

    return {
        "context": combined_context,
        "db_results": db_results,
        "web_results": web_results,
        "sql_results": sql_rows,
        "has_sources": has_sources,
    }
```

**3c.** Add helper to extract table name from SQL query:

```python
def _extract_table_from_query(sql_query: str) -> str:
    """Extract the first table name from a SQL query (best-effort)."""
    match = re.search(r'\bFROM\s+"?(\w+)"?', sql_query, re.IGNORECASE)
    return match.group(1) if match else ""
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_retriever.py -v`
Expected: All PASS

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/retriever.py tests/test_retriever.py
git commit -m "feat: add SQL routing, fallback, and context merging to retriever"
```

---

### Task 8: Ingestion integration — Call SQL ingest during pipeline

**Files:**
- Modify: `src/ingest.py:145-219` (the `ingest_documents()` function)

**Context:** Read `src/ingest.py`. After the existing ChromaDB ingestion loop, add a call to `ingest_to_sql()` for the same file list.

**Step 1: Write the failing test**

Append to `tests/test_sql_ingest.py`:

```python
def test_ingest_documents_calls_sql_ingest(tmp_path):
    """Integration test: ingest_documents should also populate SQLite."""
    import os
    from pathlib import Path

    # Set up knowledge base with a CSV
    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "testds"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "scores.csv"
    csv_file.write_text("Country,Year,Score\nChina,2005,4.0\nIndia,2005,3.0\n")

    # Minimal config
    cfg = {
        "paths": {
            "knowledge_base": str(kb_dir),
            "vector_db": str(tmp_path / "chroma_db"),
            "sql_db": str(tmp_path / "sql_db"),
        },
        "retrieval": {"chunk_size": 1000, "chunk_overlap": 100},
        "embeddings": {"provider": "local"},
        "sql": {"enabled": True},
    }

    from src.ingest import ingest_documents
    count = ingest_documents(cfg, documents_dir=str(kb_dir))

    # Verify ChromaDB got chunks
    assert count > 0

    # Verify SQLite DB was created
    db_path = tmp_path / "sql_db" / "knowledge_base.db"
    assert db_path.exists()

    # Verify schema registry
    schema_path = tmp_path / "sql_db" / "sql_schemas.json"
    assert schema_path.exists()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sql_ingest.py::test_ingest_documents_calls_sql_ingest -v`
Expected: FAIL — SQLite DB not created (sql_ingest not called yet)

**Step 3: Edit `src/ingest.py`**

At the end of `ingest_documents()`, after the ChromaDB ingestion loop and before the final print, add:

```python
    # ── SQL ingestion for tabular files ──────────────────────────────
    sql_enabled = cfg.get("sql", {}).get("enabled", True)
    if sql_enabled:
        from src.sql_ingest import ingest_to_sql, SQL_EXTENSIONS
        tabular_count = sum(1 for f, _ in files if f.suffix.lower() in SQL_EXTENSIONS)
        if tabular_count > 0:
            print(f"\nIngesting {tabular_count} tabular file(s) into SQLite...")
            try:
                schema = ingest_to_sql(files, documents_dir, cfg)
                print(f"SQL ingestion complete: {len(schema)} table(s).")
            except Exception as e:
                print(f"SQL ingestion error (non-fatal): {e}")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sql_ingest.py -v`
Expected: All PASS

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ingest.py tests/test_sql_ingest.py
git commit -m "feat: integrate SQL ingestion into the main ingest pipeline"
```

---

### Task 9: App integration — Pass route/sql_query through CLI and Web UI

**Files:**
- Modify: `app_cli.py:315-325` (retrieve call)
- Modify: `app_web.py:194-195` (retrieve call)

**Context:** Read both files. Both call `retrieve(search_query, cfg)`. They need to also pass `route` and `sql_query` from the QU result.

**Step 1: No new tests needed** — this is a wiring change. The existing test suite plus manual testing covers it.

**Step 2: Edit `app_cli.py`**

In the RAG pipeline section, after the QU result is finalized (~line 315), extract route and sql_query:

```python
            search_query = qu_result.get("search_query", user_input)
            display_query = qu_result.get("display_query", user_input)
            route = qu_result.get("route", "vector")
            sql_query = qu_result.get("sql_query")
```

Then update the retrieve call (~line 325):

```python
                retrieval_result = retrieve(search_query, effective_cfg, route=route, sql_query=sql_query)
```

Also show SQL route indicator to user (after the "Searching for:" line):

```python
            if route in ("sql", "both"):
                console.print(f"[dim]Using SQL query for structured data[/dim]")
```

**Step 3: Edit `app_web.py`**

Similarly, after QU result is finalized (~line 183):

```python
            search_query = qu_result.get("search_query", combined)
            display_query = qu_result.get("display_query", original_query)
            route = qu_result.get("route", "vector")
            sql_query = qu_result.get("sql_query")
```

Update the retrieve call (~line 195):

```python
                    retrieval_result = retrieve(search_query, cfg, route=route, sql_query=sql_query)
```

Update the source summary to include SQL results:

```python
                n_sql = len(retrieval_result.get("sql_results", []))
```

And display it.

**Step 4: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app_cli.py app_web.py
git commit -m "feat: wire SQL routing through CLI and web UI"
```

---

### Task 10: Config, gitignore, and documentation

**Files:**
- Modify: `setup.py` (`generate_config()`)
- Modify: `.gitignore`
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Edit `setup.py`**

In `generate_config()`, add to the config dict:

```python
    "paths": {
        ...
        "sql_db": "sql_db",
    },
    "sql": {
        "enabled": True,
        "max_rows": 200,
    },
```

**Step 2: Edit `.gitignore`**

Add `sql_db/` line after `chroma_db/`.

**Step 3: Edit `CLAUDE.md`**

- Add `paths.sql_db`, `sql.enabled`, `sql.max_rows` to the config table
- Add SQL layer to architecture description
- Update project structure to include `src/sql_ingest.py`, `src/sql_retriever.py`, `sql_db/`
- Update test count
- Add `retrieval.hybrid_search` to config table if missing

**Step 4: Edit `README.md`**

- Add SQL layer feature description
- Add `sql` section to config reference
- Add `sql_db/` to gitignored directories

**Step 5: Update test for setup.py**

In `tests/test_setup.py`, add assertions:

```python
    assert cfg["paths"]["sql_db"] == "sql_db"
    assert cfg["sql"]["enabled"] is True
    assert cfg["sql"]["max_rows"] == 200
```

**Step 6: Run tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add setup.py .gitignore CLAUDE.md README.md tests/test_setup.py
git commit -m "feat: add SQL layer config, gitignore, and documentation"
```

---

### Task 11: Final integration test and cleanup

**Files:**
- Create: `tests/test_sql_integration.py`

**Step 1: Write an end-to-end integration test**

```python
# tests/test_sql_integration.py
"""End-to-end integration test for the SQL layer."""
import json
import sqlite3
import pytest


def test_sql_roundtrip(tmp_path):
    """Test: ingest CSV -> SQL -> retrieve -> format context."""
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql
    from src.sql_retriever import execute_sql_query, format_sql_results_as_context, build_schema_summary

    # Create test data
    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "pts"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "scores.csv"
    csv_file.write_text(
        "Country,Year,PTS_A\n"
        "China,2000,4.0\n"
        "China,2001,4.0\n"
        "China,2002,3.5\n"
        "India,2000,3.0\n"
        "India,2001,3.0\n"
    )

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}, "sql": {"max_rows": 200}}
    files = [(Path(csv_file), "pts")]

    # Ingest
    schema = ingest_to_sql(files, str(kb_dir), cfg)
    assert len(schema) == 1
    table_name = list(schema.keys())[0]

    # Build schema summary
    summary = build_schema_summary(schema)
    assert "Country" in summary
    assert "PTS_A" in summary

    # Execute a query
    sql = f'SELECT Country, Year, PTS_A FROM "{table_name}" WHERE Country = \'China\' ORDER BY Year'
    rows = execute_sql_query(sql, cfg)
    assert len(rows) == 3
    assert all(r["Country"] == "China" for r in rows)

    # Format as context
    context = format_sql_results_as_context(rows, sql, schema[table_name]["source_file"])
    assert "[CHUNK-SQL-001]" in context
    assert "China" in context
    assert "pts/scores.csv" in context


def test_sql_aggregation(tmp_path):
    """Test: aggregation queries work."""
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql
    from src.sql_retriever import execute_sql_query

    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "ds"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "data.csv"
    csv_file.write_text("Country,Year,Score\nA,2000,1\nB,2000,2\nC,2000,3\n")

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}, "sql": {"max_rows": 200}}
    files = [(Path(csv_file), "ds")]
    schema = ingest_to_sql(files, str(kb_dir), cfg)
    table_name = list(schema.keys())[0]

    # Count
    rows = execute_sql_query(f'SELECT COUNT(*) as cnt FROM "{table_name}"', cfg)
    assert rows[0]["cnt"] == 3

    # Average
    rows = execute_sql_query(f'SELECT AVG(Score) as avg_score FROM "{table_name}"', cfg)
    assert rows[0]["avg_score"] == 2.0
```

**Step 2: Run integration tests**

Run: `python -m pytest tests/test_sql_integration.py -v`
Expected: 2 PASSED

**Step 3: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS. Note the new test count.

**Step 4: Commit**

```bash
git add tests/test_sql_integration.py
git commit -m "test: add end-to-end SQL layer integration tests"
```

**Step 5: Update test count in CLAUDE.md** if needed.

---

## Summary

| Task | What it does | New/Modified files |
|---|---|---|
| 1 | SQL ingest helpers (naming, types, samples) | `src/sql_ingest.py`, `tests/test_sql_ingest.py` |
| 2 | Core SQL ingestion function | `src/sql_ingest.py`, `tests/test_sql_ingest.py` |
| 3 | SQL retriever (validation + execution) | `src/sql_retriever.py`, `tests/test_sql_retriever.py` |
| 4 | SQL result formatting + schema summary | `src/sql_retriever.py`, `tests/test_sql_retriever.py` |
| 5 | Prompt updates (QU, system, verification) | `src/prompts.py`, `tests/test_prompts.py` |
| 6 | Query engine (schema loading, route parsing) | `src/query_engine.py`, `tests/test_query_engine.py` |
| 7 | Retriever (routing, fallback, context merge) | `src/retriever.py`, `tests/test_retriever.py` |
| 8 | Ingestion integration | `src/ingest.py`, `tests/test_sql_ingest.py` |
| 9 | App integration (CLI + Web UI) | `app_cli.py`, `app_web.py` |
| 10 | Config, gitignore, docs | `setup.py`, `.gitignore`, `CLAUDE.md`, `README.md`, `tests/test_setup.py` |
| 11 | Integration tests + cleanup | `tests/test_sql_integration.py` |

**Estimated new tests:** ~30 tests across 4 new test files
**Total test count after:** ~97 tests
