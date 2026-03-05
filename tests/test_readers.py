import pytest
from pathlib import Path


def test_reader_registry_has_all_extensions():
    from src.readers import READERS
    expected = {
        ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".tab", ".tsv",
        ".dta", ".sav", ".rds", ".rda", ".txt", ".md", ".json", ".do",
    }
    assert expected == set(READERS.keys())


def test_text_reader_txt(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("This is a test document.\nSecond line.")
    from src.readers.text import read_text
    pages = read_text(str(f))
    assert len(pages) >= 1
    assert "test document" in pages[0]["text"]
    assert pages[0]["page"] == 1


def test_text_reader_json(tmp_path):
    f = tmp_path / "data.json"
    f.write_text('{"key": "value", "items": [1, 2, 3]}')
    from src.readers.text import read_text
    pages = read_text(str(f))
    assert len(pages) >= 1
    assert "key" in pages[0]["text"]


def test_text_reader_empty(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("")
    from src.readers.text import read_text
    pages = read_text(str(f))
    assert pages == []


def test_reader_registry_dispatch(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("Hello world")
    from src.readers import read_file
    pages = read_file(str(f))
    assert len(pages) >= 1
    assert "Hello world" in pages[0]["text"]
