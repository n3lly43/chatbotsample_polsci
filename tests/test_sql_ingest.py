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
