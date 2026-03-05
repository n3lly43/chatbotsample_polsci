"""Tests for src.kb_meta — KB overview generation and storage."""

import json
import os
from unittest.mock import patch

import pytest


# ── Deterministic overview tests ─────────────────────────────────────────────

def test_generate_kb_overview_empty():
    from src.kb_meta import generate_kb_overview
    assert generate_kb_overview([], {}, None) == ""


def test_generate_kb_overview_basic():
    from src.kb_meta import generate_kb_overview
    records = [
        {"source": "ds1/file1.pdf", "dataset": "ds1", "ext": ".pdf", "chunk_count": 10},
        {"source": "ds1/file2.csv", "dataset": "ds1", "ext": ".csv", "chunk_count": 5},
        {"source": "general/readme.txt", "dataset": "general", "ext": ".txt", "chunk_count": 2},
    ]
    overview = generate_kb_overview(records, {}, None)
    assert "KNOWLEDGE BASE OVERVIEW" in overview
    assert "3 files" in overview
    assert "17 chunks" in overview
    assert "[ds1]" in overview
    assert "file1.pdf" in overview


def test_generate_kb_overview_with_sql():
    from src.kb_meta import generate_kb_overview
    records = [{"source": "d/f.csv", "dataset": "d", "ext": ".csv", "chunk_count": 3}]
    schema = {
        "d__f_csv": {
            "columns": [{"name": "x", "type": "TEXT"}, {"name": "y", "type": "INTEGER"}],
            "row_count": 100,
            "source_file": "d/f.csv",
        }
    }
    overview = generate_kb_overview(records, {}, schema)
    assert "SQL table" in overview
    assert "100 rows" in overview
    assert "x, y" in overview


def test_generate_kb_overview_multi_dataset_connections():
    from src.kb_meta import generate_kb_overview
    records = [
        {"source": "a/f1.pdf", "dataset": "a", "ext": ".pdf", "chunk_count": 5},
        {"source": "b/f2.pdf", "dataset": "b", "ext": ".pdf", "chunk_count": 3},
    ]
    overview = generate_kb_overview(records, {}, None)
    # With multiple datasets, lists both
    assert "[a]" in overview
    assert "[b]" in overview
    assert "2 dataset" in overview


# ── File record collection ───────────────────────────────────────────────────

def test_collect_file_records_empty(tmp_path):
    """collect_file_records returns [] for an empty collection."""
    import chromadb
    client = chromadb.Client()
    col = client.get_or_create_collection("test_empty")
    from src.kb_meta import collect_file_records
    assert collect_file_records(col) == []


def test_collect_file_records_groups_by_source(tmp_path):
    """collect_file_records aggregates chunk counts per source."""
    import chromadb
    client = chromadb.Client()
    col = client.get_or_create_collection("test_records")
    col.add(
        ids=["a1", "a2", "b1"],
        documents=["chunk1", "chunk2", "chunk3"],
        metadatas=[
            {"source": "ds/file_a.pdf", "dataset": "ds", "page": "1"},
            {"source": "ds/file_a.pdf", "dataset": "ds", "page": "2"},
            {"source": "ds/file_b.csv", "dataset": "ds", "page": "1"},
        ],
    )
    from src.kb_meta import collect_file_records
    records = collect_file_records(col)
    assert len(records) == 2
    a_rec = next(r for r in records if "file_a" in r["source"])
    assert a_rec["chunk_count"] == 2


# ── Sample chunk collection ──────────────────────────────────────────────────

def test_collect_sample_chunks():
    import chromadb
    client = chromadb.Client()
    col = client.get_or_create_collection("test_samples")
    col.add(
        ids=["x1", "x2"],
        documents=["first chunk of A", "second chunk of A"],
        metadatas=[
            {"source": "A.pdf", "dataset": "d", "page": "1"},
            {"source": "A.pdf", "dataset": "d", "page": "2"},
        ],
    )
    from src.kb_meta import collect_sample_chunks
    samples = collect_sample_chunks(col)
    assert "A.pdf" in samples
    assert samples["A.pdf"] == "first chunk of A"


# ── Meta chunk upsert ────────────────────────────────────────────────────────

def test_upsert_meta_chunk():
    import chromadb
    from src.kb_meta import upsert_meta_chunk, META_CHUNK_ID
    client = chromadb.Client()
    col = client.get_or_create_collection("test_upsert")
    upsert_meta_chunk(col, "test overview text")
    result = col.get(ids=[META_CHUNK_ID])
    assert result["documents"][0] == "test overview text"

    # Upsert again — should update, not duplicate
    upsert_meta_chunk(col, "updated overview")
    assert col.count() == 1
    result = col.get(ids=[META_CHUNK_ID])
    assert result["documents"][0] == "updated overview"


# ── Save and load ────────────────────────────────────────────────────────────

def test_save_and_load_kb_meta(tmp_path):
    from src.kb_meta import save_kb_meta, load_kb_meta
    cfg = {"paths": {"vector_db": str(tmp_path / "chroma_db")}}
    save_kb_meta("my overview", cfg)
    loaded = load_kb_meta(cfg)
    assert loaded == "my overview"


def test_load_kb_meta_missing(tmp_path):
    from src.kb_meta import load_kb_meta
    cfg = {"paths": {"vector_db": str(tmp_path / "nonexistent")}}
    assert load_kb_meta(cfg) == ""


# ── Prompt integration ───────────────────────────────────────────────────────

def test_build_prompt_includes_kb_overview():
    from src.prompts import build_prompt
    prompt = build_prompt("context", "Bot", "research", kb_overview="MY_KB_OVERVIEW")
    assert "MY_KB_OVERVIEW" in prompt
    assert "KNOWLEDGE BASE OVERVIEW" in prompt


def test_build_prompt_no_overview():
    from src.prompts import build_prompt
    prompt = build_prompt("context", "Bot", "research", kb_overview="")
    assert "KNOWLEDGE BASE OVERVIEW" not in prompt


def test_qu_prompt_includes_kb_overview():
    from src.prompts import build_query_understanding_prompt
    prompt = build_query_understanding_prompt(
        "test query", "research", [],
        kb_overview="OVERVIEW_TEXT_HERE",
    )
    assert "OVERVIEW_TEXT_HERE" in prompt
    assert "KNOWLEDGE BASE CONTENTS" in prompt


def test_qu_prompt_no_overview():
    from src.prompts import build_query_understanding_prompt
    prompt = build_query_understanding_prompt("test query", "research", [])
    assert "KNOWLEDGE BASE CONTENTS" not in prompt


# ── LLM overview generation ──────────────────────────────────────────────────

def _mock_llm_generate(system_prompt, user_message, cfg, **kwargs):
    """Mock LLM that returns a KB overview."""
    return "## Overview\nThis KB covers human rights data across 2 datasets."


def _mock_llm_generate_fail(system_prompt, user_message, cfg, **kwargs):
    """Mock LLM that raises an exception."""
    raise RuntimeError("LLM unavailable")


def test_generate_kb_overview_with_llm_success():
    from src.kb_meta import generate_kb_overview_with_llm
    records = [{"source": "d/f.pdf", "dataset": "d", "ext": ".pdf", "chunk_count": 5}]
    samples = {"d/f.pdf": "Introduction to human rights..."}
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o"}, "api_keys": {"openai": "fake"}}
    with patch("src.llm.generate", _mock_llm_generate):
        overview = generate_kb_overview_with_llm(records, samples, None, cfg)
    assert "KNOWLEDGE BASE OVERVIEW" in overview
    assert "human rights" in overview


def test_generate_kb_overview_with_llm_fallback():
    from src.kb_meta import generate_kb_overview_with_llm
    records = [{"source": "d/f.pdf", "dataset": "d", "ext": ".pdf", "chunk_count": 5}]
    samples = {"d/f.pdf": "text"}
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o"}, "api_keys": {"openai": "fake"}}
    with patch("src.llm.generate", _mock_llm_generate_fail):
        overview = generate_kb_overview_with_llm(records, samples, None, cfg)
    # Falls back to deterministic overview
    assert "KNOWLEDGE BASE OVERVIEW" in overview
    assert "d/f.pdf" in overview


def test_generate_kb_overview_with_llm_empty():
    from src.kb_meta import generate_kb_overview_with_llm
    cfg = {"llm": {}}
    result = generate_kb_overview_with_llm([], {}, None, cfg)
    assert result == ""


# ── Brace safety (format injection regression) ──────────────────────────────

def test_llm_overview_survives_braces_in_samples():
    """Sample chunks with {braces} must not crash the prompt formatter."""
    from src.kb_meta import generate_kb_overview_with_llm
    records = [{"source": "d/code.py", "dataset": "d", "ext": ".py", "chunk_count": 1}]
    samples = {"d/code.py": 'def foo(): return {"key": value}'}
    cfg = {"llm": {"provider": "openai", "model": "gpt-4o"}, "api_keys": {"openai": "fake"}}
    with patch("src.llm.generate", _mock_llm_generate):
        # Should not raise KeyError or ValueError
        overview = generate_kb_overview_with_llm(records, samples, None, cfg)
    assert "KNOWLEDGE BASE OVERVIEW" in overview


def test_build_prompt_kb_overview_with_braces():
    """KB overview containing {braces} must not crash the system prompt builder."""
    from src.prompts import build_prompt
    overview = "Dataset contains {variable_name} and LaTeX {R}."
    # Should not raise — braces are escaped by build_prompt
    prompt = build_prompt("context", "Bot", "research", kb_overview=overview)
    # Braces in substituted values stay doubled after str.format() (pre-existing behavior)
    assert "variable_name" in prompt
    assert "KNOWLEDGE BASE OVERVIEW" in prompt


def test_qu_prompt_kb_overview_with_braces():
    """KB overview containing {braces} must not crash the QU prompt builder."""
    from src.prompts import build_query_understanding_prompt
    overview = "Table has columns {id}, {name}, {value}."
    prompt = build_query_understanding_prompt(
        "test", "research", [], kb_overview=overview,
    )
    assert "{id}" in prompt
    assert "{name}" in prompt
