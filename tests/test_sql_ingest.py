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


def test_infer_column_type_preserves_leading_zeros():
    """M1: Zip codes, FIPS codes with leading zeros must stay TEXT."""
    from src.sql_ingest import _infer_column_type
    assert _infer_column_type(["01234", "02345", "03456"]) == "TEXT"
    assert _infer_column_type(["007", "042"]) == "TEXT"
    # Plain integers without leading zeros should still be INTEGER
    assert _infer_column_type(["0", "1", "2"]) == "INTEGER"
    assert _infer_column_type(["100", "200"]) == "INTEGER"


def test_get_sample_values():
    from src.sql_ingest import _get_sample_values
    # Now returns sorted, evenly-spaced values
    samples = _get_sample_values(["China", "India", "China", "Brazil", None, ""], n=3)
    assert samples == ["Brazil", "China", "India"]


def test_get_sample_values_fewer_than_n():
    from src.sql_ingest import _get_sample_values
    samples = _get_sample_values(["a", None, "a"], n=3)
    assert samples == ["a"]


def test_get_sample_values_evenly_spaced():
    from src.sql_ingest import _get_sample_values
    # 10 unique values, pick 5 evenly spaced from sorted list
    vals = [str(i) for i in range(10)]  # "0".."9"
    samples = _get_sample_values(vals, n=5)
    assert len(samples) == 5
    # First and last should be included
    assert samples[0] == "0"
    assert samples[-1] == "9"


def test_get_column_stats_integer():
    from src.sql_ingest import _get_column_stats
    stats = _get_column_stats(["1", "2", "3", None, ""], "INTEGER")
    assert stats["unique_count"] == 3
    assert stats["min"] == 1
    assert stats["max"] == 3


def test_get_column_stats_real():
    from src.sql_ingest import _get_column_stats
    stats = _get_column_stats(["1.5", "2.0", "3.7"], "REAL")
    assert stats["unique_count"] == 3
    assert stats["min"] == 1.5
    assert stats["max"] == 3.7


def test_get_column_stats_text():
    from src.sql_ingest import _get_column_stats
    stats = _get_column_stats(["China", "India", "China"], "TEXT")
    assert stats["unique_count"] == 2
    assert "min" not in stats


def test_find_codebook_files(tmp_path):
    from src.sql_ingest import _find_codebook_files

    ds_dir = tmp_path / "dataset"
    ds_dir.mkdir()
    # Create tabular file and potential codebooks
    csv_file = ds_dir / "data.csv"
    csv_file.write_text("a,b\n1,2\n")
    codebook = ds_dir / "codebook.pdf"
    codebook.write_bytes(b"fake pdf")
    readme = ds_dir / "notes.txt"
    readme.write_text("some notes")
    # Non-codebook extensions should be excluded
    other = ds_dir / "image.png"
    other.write_bytes(b"png")

    results = _find_codebook_files(csv_file)
    names = [f.name for f in results]
    assert "codebook.pdf" in names
    assert "notes.txt" in names
    assert "image.png" not in names
    # codebook keyword file should come first
    assert names[0] == "codebook.pdf"


def test_find_codebook_files_empty_dir(tmp_path):
    from src.sql_ingest import _find_codebook_files

    ds_dir = tmp_path / "empty"
    ds_dir.mkdir()
    csv_file = ds_dir / "data.csv"
    csv_file.write_text("a\n1\n")

    results = _find_codebook_files(csv_file)
    assert results == []


def test_describe_columns_with_llm_returns_dict(monkeypatch):
    from src.sql_ingest import _describe_columns_with_llm

    fake_response = '{"table_description": "Test table", "columns": {"x": "An integer"}}'
    # Patch 'generate' in the llm module so the deferred import picks it up
    monkeypatch.setattr("src.llm.generate", lambda *a, **kw: fake_response)

    columns = [{"name": "x", "type": "INTEGER", "sample": ["1", "2"], "stats": {"unique_count": 2}}]
    result = _describe_columns_with_llm("t", "data.csv", columns, "", {"llm": {"provider": "openai"}})
    assert result.get("table_description") == "Test table"
    assert result.get("columns", {}).get("x") == "An integer"


def test_describe_columns_with_llm_with_codebook(monkeypatch):
    from src.sql_ingest import _describe_columns_with_llm

    # Verify codebook text is passed through to the LLM prompt
    captured = {}

    def fake_generate(system_msg, prompt, cfg, **kw):
        captured["prompt"] = prompt
        return '{"table_description": "Desc", "columns": {"x": "From codebook"}}'

    monkeypatch.setattr("src.llm.generate", fake_generate)

    columns = [{"name": "x", "type": "TEXT", "sample": ["a"], "stats": {}}]
    result = _describe_columns_with_llm("t", "f.csv", columns, "x = country name", {"llm": {}})
    assert "x = country name" in captured["prompt"]
    assert "CODEBOOK" in captured["prompt"]
    assert result["columns"]["x"] == "From codebook"


def test_describe_columns_with_llm_handles_failure(monkeypatch):
    from src.sql_ingest import _describe_columns_with_llm

    def raise_error(*a, **kw):
        raise RuntimeError("no API key")

    monkeypatch.setattr("src.llm.generate", raise_error)

    columns = [{"name": "x", "type": "INTEGER", "sample": ["1"], "stats": {}}]
    result = _describe_columns_with_llm("t", "data.csv", columns, "", {"llm": {}})
    assert result == {}


def test_get_sample_values_n_equals_one():
    """Latent bug: n=1 caused ZeroDivisionError."""
    from src.sql_ingest import _get_sample_values
    samples = _get_sample_values(["a", "b", "c"], n=1)
    assert samples == ["a"]


def test_infer_column_type_inf():
    """Bug #6: inf/Infinity should not be classified as REAL."""
    from src.sql_ingest import _infer_column_type
    assert _infer_column_type(["inf", "1.0", "2.0"]) == "TEXT"
    assert _infer_column_type(["-inf", "3.14"]) == "TEXT"
    assert _infer_column_type(["Infinity", "0.5"]) == "TEXT"


def test_sanitize_column_name_deduplication():
    """Bug #1: columns that sanitize to the same name must be deduplicated."""
    from src.sql_ingest import _sanitize_column_name
    # Both map to the same sanitized name
    assert _sanitize_column_name("Score-A") == _sanitize_column_name("Score_A")


def test_ingest_to_sql_deduplicates_columns(tmp_path):
    """Bug #1: duplicate column names after sanitization get _2 suffix."""
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql
    import json as _json
    import sqlite3 as _sqlite3

    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "ds"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "dup.csv"
    csv_file.write_text("Score-A,Score_A,Value\n1,2,3\n4,5,6\n")

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}}
    files = [(Path(csv_file), "ds")]

    schema = ingest_to_sql(files, str(kb_dir), cfg)
    table_name = list(schema.keys())[0]

    col_names = [c["name"] for c in schema[table_name]["columns"]]
    # All column names must be unique
    assert len(col_names) == len(set(col_names))
    # First stays as-is, second gets _2 suffix
    assert col_names[0] == "Score_A"
    assert col_names[1] == "Score_A_2"

    # Verify data is queryable without loss
    db_path = sql_db_dir / "knowledge_base.db"
    conn = _sqlite3.connect(str(db_path))
    conn.row_factory = _sqlite3.Row
    rows = conn.execute(f'SELECT * FROM "{table_name}"').fetchall()
    row0 = dict(rows[0])
    conn.close()
    assert row0["Score_A"] == 1
    assert row0["Score_A_2"] == 2
    assert row0["Value"] == 3


def test_ingest_to_sql_dedup_collision_with_existing_suffix(tmp_path):
    """Bug: dedup suffix _2 can collide with an existing column named _2."""
    from pathlib import Path
    from src.sql_ingest import ingest_to_sql
    import sqlite3 as _sqlite3

    kb_dir = tmp_path / "knowledge_base"
    ds_dir = kb_dir / "ds"
    ds_dir.mkdir(parents=True)
    csv_file = ds_dir / "triple.csv"
    csv_file.write_text("Score-A,Score_A,Score_A_2,Value\n1,2,3,4\n5,6,7,8\n")

    sql_db_dir = tmp_path / "sql_db"
    cfg = {"paths": {"sql_db": str(sql_db_dir)}}
    files = [(Path(csv_file), "ds")]

    schema = ingest_to_sql(files, str(kb_dir), cfg)
    table_name = list(schema.keys())[0]
    col_names = [c["name"] for c in schema[table_name]["columns"]]

    # All column names must be unique — no duplicates
    assert len(col_names) == len(set(col_names)), f"Duplicate columns: {col_names}"
    # The third column is already Score_A_2, so the dedup suffix must skip to _3
    assert "Score_A" in col_names
    assert "Score_A_2" in col_names

    # Verify all data is queryable
    db_path = sql_db_dir / "knowledge_base.db"
    conn = _sqlite3.connect(str(db_path))
    conn.row_factory = _sqlite3.Row
    rows = conn.execute(f'SELECT * FROM "{table_name}"').fetchall()
    row0 = dict(rows[0])
    conn.close()
    assert row0["Value"] == 4
    assert len(row0) == 4  # all 4 columns present


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

    # Check stats are stored in schema
    year_col = [c for c in saved[table_name]["columns"] if c["name"] == "Year"][0]
    assert "stats" in year_col
    assert year_col["stats"]["unique_count"] == 1  # only 2005
    assert year_col["stats"]["min"] == 2005
    assert year_col["stats"]["max"] == 2005

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
