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


def test_sql_table_name_collision(tmp_path):
    """Regression: files that sanitize to the same table name must not overwrite each other."""
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql
    from src.sql_retriever import execute_sql_query

    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "ds"
    ds_dir.mkdir(parents=True)

    # Two files whose names differ only in punctuation -> same sanitized table name
    csv1 = ds_dir / "my-file.csv"
    csv1.write_text("x\n1\n2\n")
    csv2 = ds_dir / "my_file.csv"
    csv2.write_text("x\n3\n4\n5\n")

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}, "sql": {"max_rows": 200}}
    files = [(Path(csv1), "ds"), (Path(csv2), "ds")]
    schema = ingest_to_sql(files, str(kb_dir), cfg)

    # Both tables must exist (collision resolved with suffix)
    assert len(schema) == 2
    table_names = list(schema.keys())

    # Query both tables — both should have their original data
    rows1 = execute_sql_query(f'SELECT * FROM "{table_names[0]}"', cfg)
    rows2 = execute_sql_query(f'SELECT * FROM "{table_names[1]}"', cfg)
    counts = sorted([len(rows1), len(rows2)])
    assert counts == [2, 3]  # 2 rows from csv1, 3 rows from csv2


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
