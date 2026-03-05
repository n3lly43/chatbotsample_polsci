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
