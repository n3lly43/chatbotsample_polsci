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
