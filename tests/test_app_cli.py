import pytest

def test_cli_commands_exist():
    from app_cli import handle_command
    assert callable(handle_command)

def test_handle_command_help():
    from app_cli import handle_command
    result = handle_command("/help", cfg={}, state={})
    assert result is not None
    assert "quit" in result.lower() or "help" in result.lower()

def test_handle_command_unknown():
    from app_cli import handle_command
    result = handle_command("What is nonviolent resistance?", cfg={}, state={})
    assert result is None


def test_format_sources_sql_only():
    """SQL-only results should not say 'No sources were used'."""
    from app_cli import _format_sources
    retrieval = {
        "db_results": [],
        "web_results": [],
        "sql_results": [{"Country": "China", "Year": 2005, "Score": 4.0}],
    }
    result = _format_sources(retrieval)
    assert "No sources" not in result
    assert "SQL Results" in result
    assert "1 row" in result


def test_format_sources_all_types():
    """All three source types should appear in /sources output."""
    from app_cli import _format_sources
    retrieval = {
        "db_results": [{"text": "t", "metadata": {"source": "f.pdf", "page": "1", "dataset": "d"}, "distance": 0.1}],
        "web_results": [{"title": "P", "authors": "A", "year": 2020, "url": "http://x"}],
        "sql_results": [{"x": 1}],
    }
    result = _format_sources(retrieval)
    assert "Local Sources" in result
    assert "SQL Results" in result
    assert "Web Sources" in result
