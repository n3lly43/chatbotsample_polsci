"""SQL ingestion: load tabular files into SQLite for structured queries."""

import csv
import json
import os
import re
import sqlite3
from pathlib import Path

# Extensions that trigger SQL ingestion (tabular formats)
SQL_EXTENSIONS = {".csv", ".tab", ".tsv", ".xlsx", ".xls", ".dta", ".sav", ".rds", ".rda"}


def _sanitize_part(s: str) -> str:
    """Sanitize a single name part: replace non-alnum with _, collapse, strip."""
    s = re.sub(r"[^a-zA-Z0-9]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _sanitize_table_name(dataset: str, stem: str, ext: str, sheet: str = None) -> str:
    """Convert dataset/filename/ext into a valid SQL table identifier."""
    suffix = f"{_sanitize_part(stem)}_{ext.lstrip('.')}"
    if sheet:
        suffix += f"_{_sanitize_part(sheet)}"
    name = f"{_sanitize_part(dataset)}__{suffix}".lower()
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

    try:
        schema_registry = _ingest_tables(conn, tabular_files, documents_dir)
    finally:
        conn.close()

    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema_registry, f, indent=2, default=str)

    return schema_registry


def _ingest_tables(
    conn: sqlite3.Connection,
    tabular_files: list[tuple],
    documents_dir: str,
) -> dict:
    """Load tabular files into SQLite tables. Returns the schema registry."""
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

    return schema_registry
