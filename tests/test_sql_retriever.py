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


def test_validate_sql_rejects_dangerous_keywords():
    from src.sql_retriever import _validate_sql
    assert _validate_sql("SELECT * FROM t UNION DELETE FROM t") is False
    assert _validate_sql("SELECT * FROM t UNION SELECT * FROM t WHERE 1=1 UNION DROP TABLE t") is False
    assert _validate_sql("SELECT load_extension('x')") is False
    assert _validate_sql("SELECT 1 UNION SELECT sql FROM sqlite_master UNION INSERT INTO t VALUES(1)") is False
    assert _validate_sql("SELECT * FROM t ATTACH DATABASE 'x' AS y") is False
    assert _validate_sql("SELECT 1 UNION PRAGMA table_info('t')") is False


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


def test_format_sql_results_with_table_info():
    from src.sql_retriever import format_sql_results_as_context
    rows = [{"Country": "China", "Year": 2005}]
    table_info = {
        "table_description": "Political Terror Scale data",
        "columns": [
            {"name": "Country", "description": "Country name"},
            {"name": "Year", "description": "Year of observation"},
        ],
    }
    result = format_sql_results_as_context(rows, "SELECT * FROM t", "data.csv", table_info=table_info)
    assert "Political Terror Scale data" in result
    assert "Country: Country name" in result
    assert "Year: Year of observation" in result
    assert "[CHUNK-SQL-001]" in result


def test_format_sql_results_without_table_info():
    """Backward compat: table_info=None still works."""
    from src.sql_retriever import format_sql_results_as_context
    rows = [{"x": 1}]
    result = format_sql_results_as_context(rows, "SELECT x FROM t", "t.csv")
    assert "[CHUNK-SQL-001]" in result
    assert "Column descriptions" not in result


def test_build_schema_summary_empty():
    from src.sql_retriever import build_schema_summary
    assert build_schema_summary({}) == ""


def test_build_schema_summary_basic():
    from src.sql_retriever import build_schema_summary
    schema = {
        "test_table": {
            "source_file": "data.csv",
            "table_description": "Country-year panel data",
            "columns": [
                {
                    "name": "Country", "type": "TEXT",
                    "sample": ["China", "India"],
                    "stats": {"unique_count": 2},
                    "description": "Country name",
                },
                {
                    "name": "Year", "type": "INTEGER",
                    "sample": ["2005", "2010"],
                    "stats": {"unique_count": 2, "min": 2005, "max": 2010},
                    "description": "Year of observation",
                },
            ],
            "row_count": 100,
        }
    }
    result = build_schema_summary(schema)
    assert "test_table" in result
    assert "100 rows" in result
    assert "Country (TEXT" in result
    assert "2 unique" in result
    assert "Year (INTEGER" in result
    assert "range 2005" in result
    # Sample values
    assert '"China"' in result
    assert '"India"' in result
    assert '"2005"' in result
    assert "data.csv" in result
    # Table and column descriptions
    assert "Country-year panel data" in result
    assert "Country name" in result
    assert "Year of observation" in result


def test_build_schema_summary_no_stats():
    """Backward compat: schema entries without stats field still work."""
    from src.sql_retriever import build_schema_summary
    schema = {
        "old_table": {
            "source_file": "old.csv",
            "columns": [
                {"name": "x", "type": "TEXT", "sample": ["a", "b"]},
            ],
            "row_count": 10,
        }
    }
    result = build_schema_summary(schema)
    assert "old_table" in result
    assert '"a"' in result


def test_format_sql_results_null_values():
    """Bug #3: NULL values should render as N/A, not Python 'None'."""
    from src.sql_retriever import format_sql_results_as_context
    rows = [{"Country": "China", "Year": 2005, "Score": None}]
    result = format_sql_results_as_context(rows, "SELECT * FROM t", "data.csv")
    assert "Score = N/A" in result
    assert "Score = None" not in result


def test_build_schema_summary_missing_name():
    """Bug #4: missing 'name' key should not crash."""
    from src.sql_retriever import build_schema_summary
    schema = {
        "t": {
            "source_file": "data.csv",
            "columns": [{"type": "TEXT", "sample": ["a"]}],
            "row_count": 5,
        }
    }
    result = build_schema_summary(schema)
    assert "unknown" in result  # falls back to "unknown"
    assert "data.csv" in result


def test_extract_table_from_query_backticks():
    """Bug #5: backtick-quoted table names should be extracted."""
    from src.retriever import _extract_table_from_query
    assert _extract_table_from_query("SELECT * FROM `my_table`") == "my_table"
    assert _extract_table_from_query('SELECT * FROM "my_table"') == "my_table"
    assert _extract_table_from_query("SELECT * FROM my_table") == "my_table"


def test_format_sql_results_with_missing_col_name_in_table_info():
    """Bug: c['name'] crash when column entry lacks 'name' key in table_info."""
    from src.sql_retriever import format_sql_results_as_context
    rows = [{"x": 1}]
    table_info = {
        "table_description": "Test",
        "columns": [{"type": "INTEGER", "description": "Some column"}],
    }
    # Should not crash — uses .get() fallback
    result = format_sql_results_as_context(rows, "SELECT x FROM t", "t.csv", table_info=table_info)
    assert "[CHUNK-SQL-001]" in result


def test_lookup_source_file():
    from src.sql_retriever import _lookup_source_file
    schema = {
        "ds__data_csv": {"source_file": "ds/data.csv", "columns": [], "row_count": 0},
    }
    assert _lookup_source_file("ds__data_csv", schema) == "ds/data.csv"
    assert _lookup_source_file("unknown", schema) == "unknown"


def test_execute_sql_strips_markdown_fences(tmp_path):
    """M3: LLM-generated SQL wrapped in markdown fences must still execute."""
    from src.sql_retriever import execute_sql_query

    db_path = tmp_path / "sql_db" / "knowledge_base.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    cfg = {"paths": {"sql_db": str(tmp_path / "sql_db")}, "sql": {"max_rows": 200}}
    # Markdown-fenced SQL
    rows = execute_sql_query("```sql\nSELECT * FROM t\n```", cfg)
    assert len(rows) == 1
    assert rows[0]["x"] == 42
    # Plain fences without language tag
    rows2 = execute_sql_query("```\nSELECT * FROM t\n```", cfg)
    assert len(rows2) == 1
