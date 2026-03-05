import pytest

def test_search_registry_has_backends():
    from src.search import BACKENDS
    assert "semantic_scholar" in BACKENDS
    assert "none" in BACKENDS

def test_search_none_returns_empty():
    from src.search import search
    results = search("test query", backend="none")
    assert results == []

def test_format_web_results_empty():
    from src.search import format_web_results_as_context
    assert format_web_results_as_context([]) == ""

def test_format_web_results_with_data():
    from src.search import format_web_results_as_context
    results = [{
        "title": "Test Paper", "authors": "Smith, J.", "year": 2023,
        "abstract": "An abstract.", "url": "https://doi.org/10.1234/test",
        "citation_count": 10, "source_type": "web_search",
    }]
    context = format_web_results_as_context(results)
    assert "Test Paper" in context
    assert "Smith" in context
    assert "https://doi.org/10.1234/test" in context
    assert "[CHUNK-WEB-" in context
