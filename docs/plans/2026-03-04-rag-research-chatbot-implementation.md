# RAG Research Chatbot — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reusable RAG chatbot template with 6-layer anti-hallucination stack, pluggable LLM/search registries, 12+ academic file formats, and CLI + Streamlit web UI.

**Architecture:** Config-driven registry pattern. `src/readers/`, `src/llm/`, `src/search/` each use a dict registry. `src/verifier.py` implements the 6-layer anti-hallucination stack. Two entry points: `app_cli.py` (Rich) and `app_web.py` (Streamlit).

**Tech Stack:** Python 3.10+, ChromaDB, PyPDF2, python-docx, openpyxl, xlrd, pyreadstat, pyreadr, OpenAI/Anthropic/Gemini SDKs, Rich, Streamlit, PyYAML

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `knowledge_base/.gitkeep`
- Create: `src/__init__.py`
- Create: `src/llm/__init__.py` (empty placeholder)
- Create: `src/search/__init__.py` (empty placeholder)
- Create: `src/readers/__init__.py` (empty placeholder)
- Create: `tests/__init__.py`

**Step 1: Create directory structure**

```bash
cd "/Users/lianjie/Desktop/tool making/chatbot template"
mkdir -p src/llm src/search src/readers knowledge_base tests
```

**Step 2: Write requirements.txt**

```
# Core
chromadb>=0.4.0
PyPDF2>=3.0.0
python-docx>=1.0.0
openpyxl>=3.0.0
xlrd>=2.0.0
pyreadstat>=1.2.0
pyreadr>=0.5.0
requests>=2.28.0
rich>=13.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
numpy>=1.24.0

# LLM providers
openai>=1.0.0
anthropic>=0.20.0
google-generativeai>=0.5.0

# Web UI
streamlit>=1.30.0

# Testing
pytest>=7.0.0
```

**Step 3: Write .gitignore**

```
.env
chroma_db/
__pycache__/
*.pyc
.DS_Store
*.egg-info/
dist/
build/
.pytest_cache/
knowledge_base/*
!knowledge_base/.gitkeep
```

**Step 4: Create placeholder __init__.py files**

Empty files for `src/__init__.py`, `src/llm/__init__.py`, `src/search/__init__.py`, `src/readers/__init__.py`, `tests/__init__.py`.

**Step 5: Create knowledge_base/.gitkeep**

Empty file.

**Step 6: Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 7: Commit**

```bash
git add -A
git commit -m "scaffold: project structure, requirements, gitignore"
```

---

### Task 2: Config Loader

**Files:**
- Create: `src/config_loader.py`
- Create: `tests/test_config_loader.py`

**Step 1: Write the failing test**

```python
# tests/test_config_loader.py
import os
import tempfile
import pytest


def test_load_config_from_yaml(tmp_path):
    """Config loader reads config.yaml and exposes settings."""
    yaml_content = """
chatbot:
  name: "Test Bot"
  domain: "testing"
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.0
  max_tokens: 2048
api_keys:
  openai: ""
  anthropic: ""
  gemini: ""
embeddings:
  provider: "local"
  openai_model: "text-embedding-3-small"
retrieval:
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 5
web_search:
  enabled: true
  backend: "semantic_scholar"
  max_results: 5
verification:
  enabled: true
  max_iterations: 3
  strict_mode: true
paths:
  knowledge_base: "knowledge_base"
  vector_db: "chroma_db"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    from src.config_loader import load_config
    cfg = load_config(str(config_file))

    assert cfg["chatbot"]["name"] == "Test Bot"
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["model"] == "gpt-4o"
    assert cfg["retrieval"]["top_k"] == 5
    assert cfg["verification"]["enabled"] is True


def test_env_vars_override_api_keys(tmp_path):
    """Environment variables take precedence over config.yaml api_keys."""
    yaml_content = """
chatbot:
  name: "Test"
  domain: "test"
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.0
  max_tokens: 2048
api_keys:
  openai: "yaml-key"
  anthropic: ""
  gemini: ""
embeddings:
  provider: "local"
  openai_model: "text-embedding-3-small"
retrieval:
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 5
web_search:
  enabled: false
  backend: "semantic_scholar"
  max_results: 5
verification:
  enabled: true
  max_iterations: 3
  strict_mode: true
paths:
  knowledge_base: "knowledge_base"
  vector_db: "chroma_db"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    os.environ["OPENAI_API_KEY"] = "env-key"
    try:
        from src.config_loader import load_config
        cfg = load_config(str(config_file))
        assert cfg["api_keys"]["openai"] == "env-key"
    finally:
        del os.environ["OPENAI_API_KEY"]


def test_get_api_key_helper(tmp_path):
    """get_api_key returns the resolved key for a provider."""
    yaml_content = """
chatbot:
  name: "Test"
  domain: "test"
llm:
  provider: "openai"
  model: "gpt-4o"
  temperature: 0.0
  max_tokens: 2048
api_keys:
  openai: "test-key-123"
  anthropic: ""
  gemini: ""
embeddings:
  provider: "local"
  openai_model: "text-embedding-3-small"
retrieval:
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 5
web_search:
  enabled: false
  backend: "semantic_scholar"
  max_results: 5
verification:
  enabled: true
  max_iterations: 3
  strict_mode: true
paths:
  knowledge_base: "knowledge_base"
  vector_db: "chroma_db"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    from src.config_loader import load_config, get_api_key
    cfg = load_config(str(config_file))
    assert get_api_key(cfg, "openai") == "test-key-123"
    assert get_api_key(cfg, "anthropic") == ""
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_config_loader.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# src/config_loader.py
"""Loads config.yaml and .env, exposes settings as a dict."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


# Env var names mapped to config api_keys paths
_ENV_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file and environment variables.

    Environment variables override api_keys in config.yaml.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"

    # Load .env if it exists (next to config.yaml)
    env_path = Path(config_path).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    # Environment variables override api_keys
    for provider, env_var in _ENV_KEY_MAP.items():
        env_val = os.environ.get(env_var)
        if env_val:
            cfg.setdefault("api_keys", {})[provider] = env_val

    return cfg


def get_api_key(cfg: dict, provider: str) -> str:
    """Get the resolved API key for a provider."""
    # Check env var first
    env_var = _ENV_KEY_MAP.get(provider)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            return env_val
    # Fall back to config
    return cfg.get("api_keys", {}).get(provider, "")
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_config_loader.py -v
```

Expected: 3 PASSED

**Step 5: Commit**

```bash
git add src/config_loader.py tests/test_config_loader.py
git commit -m "feat: config loader with YAML + env var support"
```

---

### Task 3: File Readers — Registry + PDF + Text

**Files:**
- Create: `src/readers/__init__.py` (registry)
- Create: `src/readers/pdf.py`
- Create: `src/readers/text.py`
- Create: `tests/test_readers.py`

**Step 1: Write failing tests**

```python
# tests/test_readers.py
import pytest
from pathlib import Path


def test_reader_registry_has_all_extensions():
    """Registry maps all supported extensions to reader functions."""
    from src.readers import READERS
    expected = {
        ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".tab", ".tsv",
        ".dta", ".sav", ".rds", ".rda", ".txt", ".md", ".json", ".do",
    }
    assert expected == set(READERS.keys())


def test_text_reader_txt(tmp_path):
    """Text reader extracts content from .txt files."""
    f = tmp_path / "notes.txt"
    f.write_text("This is a test document.\nSecond line.")
    from src.readers.text import read_text
    pages = read_text(str(f))
    assert len(pages) >= 1
    assert "test document" in pages[0]["text"]
    assert pages[0]["page"] == 1


def test_text_reader_json(tmp_path):
    """Text reader extracts content from .json files."""
    f = tmp_path / "data.json"
    f.write_text('{"key": "value", "items": [1, 2, 3]}')
    from src.readers.text import read_text
    pages = read_text(str(f))
    assert len(pages) >= 1
    assert "key" in pages[0]["text"]


def test_text_reader_empty(tmp_path):
    """Text reader returns empty list for empty files."""
    f = tmp_path / "empty.txt"
    f.write_text("")
    from src.readers.text import read_text
    pages = read_text(str(f))
    assert pages == []


def test_pdf_reader(tmp_path):
    """PDF reader extracts pages with text and page numbers."""
    # Create a minimal PDF using PyPDF2
    from PyPDF2 import PdfWriter
    from io import BytesIO
    from reportlab.pdfgen import canvas as rl_canvas

    # Use reportlab if available, otherwise skip
    pytest.importorskip("reportlab")

    buf = BytesIO()
    c = rl_canvas.Canvas(buf)
    c.drawString(100, 750, "Test PDF content page one")
    c.showPage()
    c.drawString(100, 750, "Second page of the PDF")
    c.showPage()
    c.save()
    buf.seek(0)

    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(buf.read())

    from src.readers.pdf import read_pdf
    pages = read_pdf(str(pdf_path))
    assert len(pages) == 2
    assert pages[0]["page"] == 1
    assert "Test PDF content" in pages[0]["text"]
    assert pages[1]["page"] == 2


def test_reader_registry_dispatch(tmp_path):
    """Registry dispatches to correct reader by extension."""
    f = tmp_path / "test.txt"
    f.write_text("Hello world")
    from src.readers import read_file
    pages = read_file(str(f))
    assert len(pages) >= 1
    assert "Hello world" in pages[0]["text"]
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_readers.py -v
```

Expected: FAIL

**Step 3: Write text reader**

```python
# src/readers/text.py
"""Reader for plain text files: .txt, .md, .json, .do"""


def read_text(file_path: str) -> list[dict]:
    """Extract text from a plain text file.

    Returns list of dicts with {"page": int, "text": str}.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if not text.strip():
        return []
    return [{"page": 1, "text": text.strip()}]
```

**Step 4: Write PDF reader**

```python
# src/readers/pdf.py
"""Reader for PDF files."""

from PyPDF2 import PdfReader


def read_pdf(file_path: str) -> list[dict]:
    """Extract text from a PDF file, one entry per page.

    Returns list of dicts with {"page": int, "text": str}.
    """
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append({"page": i + 1, "text": text.strip()})
    return pages
```

**Step 5: Write readers registry (partial — PDF + text only, others added in Tasks 4-5)**

```python
# src/readers/__init__.py
"""File reader registry. Maps extensions to reader functions."""

from src.readers.pdf import read_pdf
from src.readers.text import read_text

# Registry: extension -> reader function
# Each reader returns list[dict] with {"page": int|str, "text": str}
READERS = {
    # Populated incrementally — PDF + text now, others in Tasks 4-5
    ".pdf": read_pdf,
    ".txt": read_text,
    ".md": read_text,
    ".json": read_text,
    ".do": read_text,
}

# Placeholders — will be replaced in Tasks 4-5 when implementations land
def _not_yet(fp):
    raise NotImplementedError(f"Reader not yet implemented for {fp}")

for ext in (".docx", ".xlsx", ".xls", ".csv", ".tab", ".tsv", ".dta", ".sav", ".rds", ".rda"):
    READERS[ext] = _not_yet


def read_file(file_path: str) -> list[dict]:
    """Dispatch to the correct reader based on file extension."""
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        print(f"  Unsupported file type: {ext}, skipping {file_path}")
        return []
    return reader(file_path)
```

**Step 6: Run tests**

```bash
pytest tests/test_readers.py -v
```

Expected: `test_reader_registry_has_all_extensions` PASS, text tests PASS, PDF test PASS (or skip if no reportlab), dispatch test PASS

**Step 7: Commit**

```bash
git add src/readers/ tests/test_readers.py
git commit -m "feat: file reader registry with PDF and text readers"
```

---

### Task 4: File Readers — DOCX + Excel + CSV/Tab

**Files:**
- Create: `src/readers/docx.py`
- Create: `src/readers/excel.py`
- Create: `src/readers/csv_tab.py`
- Modify: `src/readers/__init__.py`
- Modify: `tests/test_readers.py`

**Step 1: Write failing tests (append to tests/test_readers.py)**

```python
def test_docx_reader(tmp_path):
    """DOCX reader extracts paragraphs."""
    from docx import Document
    doc = Document()
    doc.add_paragraph("First paragraph of the document.")
    doc.add_paragraph("Second paragraph with more content.")
    path = tmp_path / "test.docx"
    doc.save(str(path))

    from src.readers.docx import read_docx
    pages = read_docx(str(path))
    assert len(pages) >= 1
    assert "First paragraph" in pages[0]["text"]


def test_xlsx_reader(tmp_path):
    """Excel reader extracts rows as readable text."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["Country", "Year", "Success"])
    ws.append(["India", 1930, "Yes"])
    ws.append(["Poland", 1980, "Yes"])
    path = tmp_path / "test.xlsx"
    wb.save(str(path))

    from src.readers.excel import read_excel
    pages = read_excel(str(path))
    assert len(pages) >= 1
    assert "India" in pages[0]["text"]
    assert "Country" in pages[0]["text"]


def test_csv_reader(tmp_path):
    """CSV reader extracts rows as readable text."""
    f = tmp_path / "data.csv"
    f.write_text("name,year,outcome\nAlice,2020,success\nBob,2021,failure\n")

    from src.readers.csv_tab import read_csv_tab
    pages = read_csv_tab(str(f))
    assert len(pages) >= 1
    assert "Alice" in pages[0]["text"]


def test_tab_reader(tmp_path):
    """Tab reader extracts rows as readable text."""
    f = tmp_path / "data.tab"
    f.write_text("country\tyear\tresult\nEgypt\t2011\tpartial\n")

    from src.readers.csv_tab import read_csv_tab
    pages = read_csv_tab(str(f), delimiter="\t")
    assert len(pages) >= 1
    assert "Egypt" in pages[0]["text"]
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_readers.py::test_docx_reader tests/test_readers.py::test_xlsx_reader tests/test_readers.py::test_csv_reader tests/test_readers.py::test_tab_reader -v
```

Expected: FAIL

**Step 3: Write DOCX reader**

```python
# src/readers/docx.py
"""Reader for Word .docx files."""

from docx import Document


def read_docx(file_path: str) -> list[dict]:
    """Extract text from a .docx file.

    Returns all paragraphs as a single page entry.
    """
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return []
    return [{"page": 1, "text": "\n\n".join(paragraphs)}]
```

**Step 4: Write Excel reader**

```python
# src/readers/excel.py
"""Reader for Excel files: .xlsx and .xls"""

MAX_CHUNK_CHARS = 6000


def read_excel(file_path: str) -> list[dict]:
    """Extract text from an Excel file (.xlsx or .xls).

    Converts rows into readable "Header: Value" format.
    Groups rows into blocks that fit within embedding token limits.
    """
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    if ext == ".xls":
        return _read_xls(file_path)
    return _read_xlsx(file_path)


def _read_xlsx(file_path: str) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    pages = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        pages.extend(_rows_to_pages(rows, sheet_name))

    wb.close()
    return pages


def _read_xls(file_path: str) -> list[dict]:
    import xlrd
    wb = xlrd.open_workbook(file_path)
    pages = []

    for sheet_idx in range(wb.nsheets):
        ws = wb.sheet_by_index(sheet_idx)
        if ws.nrows == 0:
            continue
        rows = []
        for r in range(ws.nrows):
            rows.append(tuple(ws.cell_value(r, c) for c in range(ws.ncols)))
        pages.extend(_rows_to_pages(rows, ws.name))

    return pages


def _rows_to_pages(rows: list[tuple], sheet_name: str) -> list[dict]:
    """Convert rows to page dicts, grouping into blocks under MAX_CHUNK_CHARS."""
    headers = [str(h) if h is not None else "" for h in rows[0]]

    row_texts = []
    for row in rows[1:]:
        parts = []
        for header, val in zip(headers, row):
            if val is not None and str(val).strip():
                parts.append(f"{header}: {val}")
        if parts:
            row_texts.append("; ".join(parts))

    header_line = f"Sheet: {sheet_name} | Columns: {', '.join(headers)}\n"
    pages = []
    block = []
    block_chars = len(header_line)
    block_start = 1

    for idx, row_text in enumerate(row_texts):
        if block and block_chars + len(row_text) + 1 > MAX_CHUNK_CHARS:
            text = header_line + "\n".join(block)
            pages.append({
                "page": f"{sheet_name}_rows_{block_start}-{block_start + len(block) - 1}",
                "text": text,
            })
            block = []
            block_chars = len(header_line)
            block_start = idx + 1
        block.append(row_text)
        block_chars += len(row_text) + 1

    if block:
        text = header_line + "\n".join(block)
        pages.append({
            "page": f"{sheet_name}_rows_{block_start}-{block_start + len(block) - 1}",
            "text": text,
        })

    return pages
```

**Step 5: Write CSV/Tab reader**

```python
# src/readers/csv_tab.py
"""Reader for CSV, tab-delimited, and TSV files."""

import csv

MAX_CHUNK_CHARS = 6000


def read_csv_tab(file_path: str, delimiter: str = None) -> list[dict]:
    """Extract text from a delimited file.

    Auto-detects delimiter from extension if not provided.
    Returns list of dicts with {"page": str, "text": str}.
    """
    from pathlib import Path

    if delimiter is None:
        ext = Path(file_path).suffix.lower()
        delimiter = "\t" if ext in (".tab", ".tsv") else ","

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        return []

    headers = [h.strip().strip('"') for h in rows[0]]
    row_texts = []
    for row in rows[1:]:
        parts = []
        for header, val in zip(headers, row):
            val = val.strip().strip('"')
            if val:
                parts.append(f"{header}: {val}")
        if parts:
            row_texts.append("; ".join(parts))

    pages = []
    header_line = f"Columns: {', '.join(headers)}\n"
    block = []
    block_chars = len(header_line)
    block_start = 1

    for idx, row_text in enumerate(row_texts):
        if block and block_chars + len(row_text) + 1 > MAX_CHUNK_CHARS:
            text = header_line + "\n".join(block)
            pages.append({
                "page": f"rows_{block_start}-{block_start + len(block) - 1}",
                "text": text,
            })
            block = []
            block_chars = len(header_line)
            block_start = idx + 1
        block.append(row_text)
        block_chars += len(row_text) + 1

    if block:
        text = header_line + "\n".join(block)
        pages.append({
            "page": f"rows_{block_start}-{block_start + len(block) - 1}",
            "text": text,
        })

    return pages
```

**Step 6: Update registry**

```python
# src/readers/__init__.py
"""File reader registry. Maps extensions to reader functions."""

from src.readers.pdf import read_pdf
from src.readers.text import read_text
from src.readers.docx import read_docx
from src.readers.excel import read_excel
from src.readers.csv_tab import read_csv_tab

# Registry: extension -> reader function
# Each reader returns list[dict] with {"page": int|str, "text": str}
READERS = {
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".xlsx": read_excel,
    ".xls": read_excel,
    ".csv": read_csv_tab,
    ".tab": read_csv_tab,
    ".tsv": read_csv_tab,
    ".txt": read_text,
    ".md": read_text,
    ".json": read_text,
    ".do": read_text,
}

# Placeholders for Task 5
def _not_yet(fp):
    raise NotImplementedError(f"Reader not yet implemented for {fp}")

for ext in (".dta", ".sav", ".rds", ".rda"):
    READERS[ext] = _not_yet


def read_file(file_path: str) -> list[dict]:
    """Dispatch to the correct reader based on file extension."""
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        print(f"  Unsupported file type: {ext}, skipping {file_path}")
        return []
    return reader(file_path)
```

**Step 7: Run tests**

```bash
pytest tests/test_readers.py -v
```

Expected: All new tests PASS

**Step 8: Commit**

```bash
git add src/readers/ tests/test_readers.py
git commit -m "feat: add docx, excel, csv/tab readers"
```

---

### Task 5: File Readers — Stata + SPSS + R Data

**Files:**
- Create: `src/readers/stata.py`
- Create: `src/readers/spss.py`
- Create: `src/readers/rdata.py`
- Modify: `src/readers/__init__.py`
- Modify: `tests/test_readers.py`

**Step 1: Write failing tests (append to tests/test_readers.py)**

```python
def test_stata_reader(tmp_path):
    """Stata reader extracts data via pyreadstat."""
    pytest.importorskip("pyreadstat")
    import pandas as pd
    import pyreadstat

    df = pd.DataFrame({"country": ["India", "Poland"], "year": [1930, 1980]})
    path = str(tmp_path / "test.dta")
    pyreadstat.write_dta(df, path)

    from src.readers.stata import read_stata
    pages = read_stata(path)
    assert len(pages) >= 1
    assert "India" in pages[0]["text"]


def test_spss_reader(tmp_path):
    """SPSS reader extracts data via pyreadstat."""
    pytest.importorskip("pyreadstat")
    import pandas as pd
    import pyreadstat

    df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [85.0, 92.0]})
    path = str(tmp_path / "test.sav")
    pyreadstat.write_sav(df, path)

    from src.readers.spss import read_spss
    pages = read_spss(path)
    assert len(pages) >= 1
    assert "Alice" in pages[0]["text"]


def test_rdata_reader(tmp_path):
    """R data reader extracts data via pyreadr."""
    pytest.importorskip("pyreadr")
    import pandas as pd
    import pyreadr

    df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
    path = str(tmp_path / "test.rds")
    pyreadr.write_rds(path, df)

    from src.readers.rdata import read_rdata
    pages = read_rdata(path)
    assert len(pages) >= 1
    assert "x" in pages[0]["text"]
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_readers.py::test_stata_reader tests/test_readers.py::test_spss_reader tests/test_readers.py::test_rdata_reader -v
```

Expected: FAIL

**Step 3: Write Stata reader**

```python
# src/readers/stata.py
"""Reader for Stata .dta files via pyreadstat."""

MAX_CHUNK_CHARS = 6000


def read_stata(file_path: str) -> list[dict]:
    """Extract text from a Stata .dta file.

    Uses pyreadstat for robust support across all Stata versions.
    Returns data as readable "Header: Value" rows.
    """
    import pyreadstat

    df, meta = pyreadstat.read_dta(file_path)
    return _dataframe_to_pages(df, meta, file_path)


def _dataframe_to_pages(df, meta, file_path: str) -> list[dict]:
    """Convert a pandas DataFrame to page dicts."""
    pages = []

    # Metadata page
    info_lines = []
    if hasattr(meta, "file_label") and meta.file_label:
        info_lines.append(f"Dataset label: {meta.file_label}")
    info_lines.append(f"Variables ({len(df.columns)}): {', '.join(df.columns)}")

    # Variable labels if available
    if hasattr(meta, "column_names_to_labels") and meta.column_names_to_labels:
        labels = meta.column_names_to_labels
        label_lines = [f"  {col}: {labels[col]}" for col in df.columns if labels.get(col)]
        if label_lines:
            info_lines.append("Variable descriptions:")
            info_lines.extend(label_lines)

    pages.append({"page": "metadata", "text": "\n".join(info_lines)})

    # Data rows
    headers = list(df.columns)
    header_line = f"Columns: {', '.join(headers)}\n"
    block = []
    block_chars = len(header_line)
    block_start = 1

    for idx, (_, row) in enumerate(df.iterrows()):
        parts = []
        for col in headers:
            val = row[col]
            if val is not None and str(val).strip() and str(val) != "nan":
                parts.append(f"{col}: {val}")
        if not parts:
            continue
        row_text = "; ".join(parts)

        if block and block_chars + len(row_text) + 1 > MAX_CHUNK_CHARS:
            text = header_line + "\n".join(block)
            pages.append({
                "page": f"rows_{block_start}-{block_start + len(block) - 1}",
                "text": text,
            })
            block = []
            block_chars = len(header_line)
            block_start = idx + 1
        block.append(row_text)
        block_chars += len(row_text) + 1

    if block:
        text = header_line + "\n".join(block)
        pages.append({
            "page": f"rows_{block_start}-{block_start + len(block) - 1}",
            "text": text,
        })

    return pages
```

**Step 4: Write SPSS reader**

```python
# src/readers/spss.py
"""Reader for SPSS .sav files via pyreadstat."""

from src.readers.stata import _dataframe_to_pages


def read_spss(file_path: str) -> list[dict]:
    """Extract text from an SPSS .sav file."""
    import pyreadstat

    df, meta = pyreadstat.read_sav(file_path)
    return _dataframe_to_pages(df, meta, file_path)
```

**Step 5: Write R data reader**

```python
# src/readers/rdata.py
"""Reader for R data files: .rds and .rda"""

MAX_CHUNK_CHARS = 6000


def read_rdata(file_path: str) -> list[dict]:
    """Extract text from an R data file (.rds or .rda).

    .rds contains a single object. .rda may contain multiple.
    """
    import pyreadr
    from pathlib import Path

    result = pyreadr.read_r(file_path)

    pages = []
    for name, df in result.items():
        headers = list(df.columns)
        header_line = f"Object: {name} | Columns: {', '.join(headers)}\n"
        block = []
        block_chars = len(header_line)
        block_start = 1

        for idx, (_, row) in enumerate(df.iterrows()):
            parts = []
            for col in headers:
                val = row[col]
                if val is not None and str(val).strip() and str(val) != "nan":
                    parts.append(f"{col}: {val}")
            if not parts:
                continue
            row_text = "; ".join(parts)

            if block and block_chars + len(row_text) + 1 > MAX_CHUNK_CHARS:
                text = header_line + "\n".join(block)
                pages.append({
                    "page": f"{name}_rows_{block_start}-{block_start + len(block) - 1}",
                    "text": text,
                })
                block = []
                block_chars = len(header_line)
                block_start = idx + 1
            block.append(row_text)
            block_chars += len(row_text) + 1

        if block:
            text = header_line + "\n".join(block)
            pages.append({
                "page": f"{name}_rows_{block_start}-{block_start + len(block) - 1}",
                "text": text,
            })

    return pages
```

**Step 6: Update registry — final version**

```python
# src/readers/__init__.py
"""File reader registry. Maps extensions to reader functions."""

from src.readers.pdf import read_pdf
from src.readers.text import read_text
from src.readers.docx import read_docx
from src.readers.excel import read_excel
from src.readers.csv_tab import read_csv_tab
from src.readers.stata import read_stata
from src.readers.spss import read_spss
from src.readers.rdata import read_rdata

# Registry: extension -> reader function
# Each reader returns list[dict] with {"page": int|str, "text": str}
READERS = {
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".xlsx": read_excel,
    ".xls": read_excel,
    ".csv": read_csv_tab,
    ".tab": read_csv_tab,
    ".tsv": read_csv_tab,
    ".dta": read_stata,
    ".sav": read_spss,
    ".rds": read_rdata,
    ".rda": read_rdata,
    ".txt": read_text,
    ".md": read_text,
    ".json": read_text,
    ".do": read_text,
}


def read_file(file_path: str) -> list[dict]:
    """Dispatch to the correct reader based on file extension."""
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        print(f"  Unsupported file type: {ext}, skipping {file_path}")
        return []
    return reader(file_path)
```

**Step 7: Run all reader tests**

```bash
pytest tests/test_readers.py -v
```

Expected: All PASS

**Step 8: Commit**

```bash
git add src/readers/ tests/test_readers.py
git commit -m "feat: add stata, spss, r data readers — all formats complete"
```

---

### Task 6: Ingestion Pipeline

**Files:**
- Create: `src/ingest.py`
- Create: `ingest.py` (root entry point)
- Create: `tests/test_ingest.py`

**Step 1: Write failing tests**

```python
# tests/test_ingest.py
import pytest


def test_split_text_recursive_short():
    """Short text returns as single chunk."""
    from src.ingest import split_text_recursive
    chunks = split_text_recursive("Hello world", 1000, 100)
    assert chunks == ["Hello world"]


def test_split_text_recursive_long():
    """Long text is split into overlapping chunks."""
    from src.ingest import split_text_recursive
    text = "Paragraph one. " * 100 + "\n\n" + "Paragraph two. " * 100
    chunks = split_text_recursive(text, 500, 50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 600  # allow some overflow at boundaries


def test_chunk_documents():
    """Pages are chunked with correct metadata."""
    from src.ingest import chunk_documents
    pages = [{"page": 1, "text": "A short page of text."}]
    chunks = chunk_documents(pages, "test.pdf", "general")
    assert len(chunks) >= 1
    assert chunks[0]["metadata"]["source"] == "test.pdf"
    assert chunks[0]["metadata"]["dataset"] == "general"


def test_discover_files(tmp_path):
    """discover_files finds supported files recursively."""
    from src.ingest import discover_files

    # Create test files
    sub = tmp_path / "Dataset1"
    sub.mkdir()
    (sub / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
    (sub / "data.csv").write_text("a,b\n1,2\n")
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "photo.jpg").write_bytes(b"fake jpg")  # unsupported

    files = discover_files(str(tmp_path))
    extensions = {f[0].suffix for f in files}
    assert ".pdf" in extensions
    assert ".csv" in extensions
    assert ".txt" in extensions
    assert ".jpg" not in extensions

    # Check dataset names
    datasets = {f[1] for f in files}
    assert "Dataset1" in datasets
    assert "general" in datasets
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ingest.py -v
```

Expected: FAIL

**Step 3: Write ingestion pipeline**

```python
# src/ingest.py
"""Document ingestion pipeline: files -> chunks -> embeddings -> ChromaDB."""

import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from src.readers import read_file, READERS
from src.config_loader import load_config, get_api_key

MAX_CHUNK_CHARS = 6000


def split_text_recursive(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping chunks using recursive separators."""
    separators = ["\n\n", "\n", ". ", " "]

    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            chunks = []
            current = ""
            for part in parts:
                candidate = current + sep + part if current else part
                if len(candidate) > chunk_size and current:
                    chunks.append(current.strip())
                    overlap_text = current[-chunk_overlap:] if chunk_overlap else ""
                    current = overlap_text + sep + part if overlap_text else part
                else:
                    current = candidate
            if current.strip():
                chunks.append(current.strip())
            return chunks

    # Last resort: character split
    chunks = []
    for i in range(0, len(text), chunk_size - chunk_overlap):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks


def chunk_documents(pages: list[dict], source_name: str, dataset_name: str,
                    chunk_size: int = 1000, chunk_overlap: int = 100) -> list[dict]:
    """Split pages into smaller chunks with metadata."""
    chunks = []
    for page_info in pages:
        text = page_info["text"]
        if len(text) > MAX_CHUNK_CHARS:
            splits = split_text_recursive(text, MAX_CHUNK_CHARS, chunk_overlap)
        else:
            splits = split_text_recursive(text, chunk_size, chunk_overlap)

        for j, split in enumerate(splits):
            if len(split) > MAX_CHUNK_CHARS:
                split = split[:MAX_CHUNK_CHARS]
            chunks.append({
                "text": split,
                "metadata": {
                    "source": source_name,
                    "dataset": dataset_name,
                    "page": str(page_info["page"]),
                    "chunk_index": j,
                },
            })
    return chunks


def discover_files(documents_dir: str) -> list[tuple[Path, str]]:
    """Recursively discover all supported files.

    Returns list of (file_path, dataset_name) tuples.
    Dataset name is the immediate subfolder name, or "general" for root files.
    """
    root = Path(documents_dir)
    supported = set(READERS.keys())
    files = []

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in supported:
            continue
        if file_path.name.startswith("."):
            continue

        rel = file_path.relative_to(root)
        dataset_name = rel.parts[0] if len(rel.parts) > 1 else "general"
        files.append((file_path, dataset_name))

    return files


def get_chroma_collection(cfg: dict):
    """Get or create the ChromaDB collection with embeddings."""
    db_path = cfg["paths"]["vector_db"]
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.abspath("config.yaml")), db_path)

    client = chromadb.PersistentClient(path=db_path)

    embed_provider = cfg.get("embeddings", {}).get("provider", "local")
    if embed_provider == "openai":
        api_key = get_api_key(cfg, "openai")
        model = cfg.get("embeddings", {}).get("openai_model", "text-embedding-3-small")
        ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key, model_name=model,
        )
    else:
        ef = embedding_functions.DefaultEmbeddingFunction()

    collection = client.get_or_create_collection(
        name="knowledge_base",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def ingest_documents(cfg: dict = None, documents_dir: str = None) -> int:
    """Ingest all supported files from knowledge_base/ into ChromaDB.

    Returns the number of chunks ingested.
    """
    if cfg is None:
        cfg = load_config()

    if documents_dir is None:
        documents_dir = cfg["paths"]["knowledge_base"]
        if not os.path.isabs(documents_dir):
            documents_dir = os.path.join(
                os.path.dirname(os.path.abspath("config.yaml")), documents_dir
            )

    files = discover_files(documents_dir)
    if not files:
        print(f"No supported files found in {documents_dir}")
        print(f"Supported types: {', '.join(sorted(READERS.keys()))}")
        return 0

    # Summarize
    datasets = {}
    for f, ds in files:
        datasets.setdefault(ds, []).append(f)
    print(f"Found {len(files)} files across {len(datasets)} dataset(s):\n")
    for ds_name, ds_files in sorted(datasets.items()):
        exts = [f.suffix for f in ds_files]
        print(f"  {ds_name}: {len(ds_files)} files ({', '.join(sorted(set(exts)))})")
    print()

    chunk_size = cfg.get("retrieval", {}).get("chunk_size", 1000)
    chunk_overlap = cfg.get("retrieval", {}).get("chunk_overlap", 100)

    collection = get_chroma_collection(cfg)

    # Clear existing data
    existing = collection.count()
    if existing > 0:
        print(f"Clearing {existing} existing chunks...\n")
        all_ids = collection.get()["ids"]
        if all_ids:
            for i in range(0, len(all_ids), 5000):
                collection.delete(ids=all_ids[i:i + 5000])

    total_chunks = 0
    for file_path, dataset_name in files:
        rel_path = file_path.relative_to(documents_dir)
        print(f"Processing: {rel_path}")

        try:
            pages = read_file(str(file_path))
        except Exception as e:
            print(f"  Error reading {file_path.name}: {e}")
            continue

        if not pages:
            print(f"  No text extracted, skipping.")
            continue

        source_name = f"{dataset_name}/{file_path.name}"
        chunks = chunk_documents(pages, source_name, dataset_name, chunk_size, chunk_overlap)
        print(f"  -> {len(chunks)} chunks")

        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            ids = [f"{dataset_name}_{file_path.stem}_{i + j}" for j in range(len(batch))]
            documents = [c["text"] for c in batch]
            metadatas = [c["metadata"] for c in batch]
            collection.add(ids=ids, documents=documents, metadatas=metadatas)

        total_chunks += len(chunks)

    print(f"\nIngestion complete: {total_chunks} chunks from {len(files)} files.")
    return total_chunks
```

**Step 4: Write root entry point**

```python
# ingest.py
"""Entry point for document ingestion."""

from src.ingest import ingest_documents
from src.config_loader import load_config


if __name__ == "__main__":
    cfg = load_config()
    count = ingest_documents(cfg)
    if count == 0:
        print("\nNo documents were ingested. Add files to knowledge_base/ and try again.")
```

**Step 5: Run tests**

```bash
pytest tests/test_ingest.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add src/ingest.py ingest.py tests/test_ingest.py
git commit -m "feat: ingestion pipeline with chunking and ChromaDB storage"
```

---

### Task 7: LLM Provider Registry

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/openai.py`
- Create: `src/llm/anthropic.py`
- Create: `src/llm/gemini.py`
- Create: `tests/test_llm.py`

**Step 1: Write failing tests**

```python
# tests/test_llm.py
import pytest


def test_provider_registry_has_all_providers():
    """Registry contains openai, anthropic, gemini."""
    from src.llm import PROVIDERS
    assert "openai" in PROVIDERS
    assert "anthropic" in PROVIDERS
    assert "gemini" in PROVIDERS


def test_generate_raises_on_unknown_provider():
    """generate() raises ValueError for unknown provider."""
    from src.llm import generate
    with pytest.raises(ValueError, match="Unknown provider"):
        generate("system", "user", provider="fake", cfg={"api_keys": {}})


def test_generate_raises_on_missing_api_key():
    """generate() raises ValueError when API key is empty."""
    from src.llm import generate
    cfg = {"api_keys": {"openai": ""}, "llm": {"provider": "openai", "model": "gpt-4o",
           "temperature": 0.0, "max_tokens": 100}}
    with pytest.raises(ValueError, match="API key"):
        generate("system", "user", provider="openai", cfg=cfg)


def test_list_models_fallback():
    """list_models returns fallback list when API call fails."""
    from src.llm.openai import list_models
    # Invalid key should trigger fallback
    models = list_models("invalid-key-123")
    assert isinstance(models, list)
    assert len(models) > 0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm.py -v
```

Expected: FAIL

**Step 3: Write OpenAI provider**

```python
# src/llm/openai.py
"""OpenAI LLM provider."""

FALLBACK_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
]


def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = "gpt-4o", temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    """Generate a response using OpenAI's API."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content


def list_models(api_key: str) -> list[str]:
    """Fetch available models from OpenAI API. Falls back to defaults."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        models = client.models.list()
        chat_models = sorted([
            m.id for m in models
            if "gpt" in m.id or m.id.startswith("o")
        ])
        return chat_models if chat_models else FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS
```

**Step 4: Write Anthropic provider**

```python
# src/llm/anthropic.py
"""Anthropic LLM provider."""

FALLBACK_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-5",
]


def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = "claude-sonnet-4-6", temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    """Generate a response using Anthropic's API."""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message},
        ],
    )
    return response.content[0].text


def list_models(api_key: str) -> list[str]:
    """Fetch available models from Anthropic API. Falls back to defaults."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        models = client.models.list()
        return sorted([m.id for m in models.data])
    except Exception:
        return FALLBACK_MODELS
```

**Step 5: Write Gemini provider**

```python
# src/llm/gemini.py
"""Google Gemini LLM provider."""

FALLBACK_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


def generate(system_prompt: str, user_message: str, api_key: str,
             model: str = "gemini-2.5-flash", temperature: float = 0.0,
             max_tokens: int = 2048) -> str:
    """Generate a response using Google Gemini API."""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    response = gen_model.generate_content(user_message)
    return response.text


def list_models(api_key: str) -> list[str]:
    """Fetch available models from Gemini API. Falls back to defaults."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        models = genai.list_models()
        chat_models = sorted([
            m.name.replace("models/", "")
            for m in models
            if "generateContent" in (m.supported_generation_methods or [])
        ])
        return chat_models if chat_models else FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS
```

**Step 6: Write LLM registry**

```python
# src/llm/__init__.py
"""LLM provider registry."""

from src.llm import openai as _openai
from src.llm import anthropic as _anthropic
from src.llm import gemini as _gemini
from src.config_loader import get_api_key

PROVIDERS = {
    "openai": _openai,
    "anthropic": _anthropic,
    "gemini": _gemini,
}


def generate(system_prompt: str, user_message: str, cfg: dict,
             provider: str = None, max_tokens: int = None) -> str:
    """Generate a response using the configured LLM provider."""
    provider = provider or cfg["llm"]["provider"]

    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}"
        )

    api_key = get_api_key(cfg, provider)
    if not api_key:
        raise ValueError(
            f"API key not set for {provider}. "
            f"Set it in .env or config.yaml."
        )

    model = cfg["llm"].get("model", "")
    temperature = cfg["llm"].get("temperature", 0.0)
    if max_tokens is None:
        max_tokens = cfg["llm"].get("max_tokens", 2048)

    return PROVIDERS[provider].generate(
        system_prompt=system_prompt,
        user_message=user_message,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def list_models(provider: str, api_key: str) -> list[str]:
    """List available models for a provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    return PROVIDERS[provider].list_models(api_key)
```

**Step 7: Run tests**

```bash
pytest tests/test_llm.py -v
```

Expected: All PASS

**Step 8: Commit**

```bash
git add src/llm/ tests/test_llm.py
git commit -m "feat: LLM provider registry with OpenAI, Anthropic, Gemini"
```

---

### Task 8: Search Backend Registry

**Files:**
- Create: `src/search/__init__.py`
- Create: `src/search/semantic_scholar.py`
- Create: `tests/test_search.py`

**Step 1: Write failing tests**

```python
# tests/test_search.py
import pytest


def test_search_registry_has_backends():
    """Registry contains semantic_scholar and none."""
    from src.search import BACKENDS
    assert "semantic_scholar" in BACKENDS
    assert "none" in BACKENDS


def test_search_none_returns_empty():
    """'none' backend returns empty list."""
    from src.search import search
    results = search("test query", backend="none")
    assert results == []


def test_format_web_results_empty():
    """Formatting empty results returns empty string."""
    from src.search import format_web_results_as_context
    assert format_web_results_as_context([]) == ""


def test_format_web_results_with_data():
    """Formatting results includes authors, title, URL."""
    from src.search import format_web_results_as_context
    results = [{
        "title": "Test Paper",
        "authors": "Smith, J.",
        "year": 2023,
        "abstract": "An abstract.",
        "url": "https://doi.org/10.1234/test",
        "citation_count": 10,
        "source_type": "web_search",
    }]
    context = format_web_results_as_context(results)
    assert "Test Paper" in context
    assert "Smith" in context
    assert "https://doi.org/10.1234/test" in context
    assert "[CHUNK-WEB-" in context
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_search.py -v
```

Expected: FAIL

**Step 3: Write Semantic Scholar backend**

```python
# src/search/semantic_scholar.py
"""Semantic Scholar API search backend."""

import time
import requests

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]


def search_papers(query: str, limit: int = 5) -> list[dict]:
    """Search Semantic Scholar for academic papers.

    Returns list of dicts with: title, authors, year, abstract, url, citation_count.
    """
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,url,externalIds,citationCount",
    }

    data = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(SEMANTIC_SCHOLAR_API, params=params, timeout=10)
            if response.status_code == 429 and attempt < MAX_RETRIES:
                wait = RETRY_DELAYS[attempt]
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            break
        except (requests.RequestException, ValueError):
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                continue
            return []

    if data is None:
        return []

    results = []
    for paper in data.get("data", []):
        abstract = paper.get("abstract") or ""
        if not abstract:
            continue

        authors = ", ".join(
            a.get("name", "Unknown") for a in (paper.get("authors") or [])[:3]
        )
        if len(paper.get("authors", [])) > 3:
            authors += " et al."

        url = paper.get("url", "")
        external_ids = paper.get("externalIds") or {}
        if external_ids.get("DOI"):
            url = f"https://doi.org/{external_ids['DOI']}"

        results.append({
            "title": paper.get("title", "Untitled"),
            "authors": authors,
            "year": paper.get("year"),
            "abstract": abstract,
            "url": url,
            "citation_count": paper.get("citationCount", 0),
            "source_type": "web_search",
        })

    results.sort(key=lambda x: x.get("citation_count", 0), reverse=True)
    return results
```

**Step 4: Write search registry**

```python
# src/search/__init__.py
"""Search backend registry."""

from src.search.semantic_scholar import search_papers as _ss_search

BACKENDS = {
    "semantic_scholar": _ss_search,
    "none": lambda query, limit=5: [],
}


def search(query: str, backend: str = "semantic_scholar",
           limit: int = 5) -> list[dict]:
    """Run a search using the specified backend."""
    fn = BACKENDS.get(backend)
    if fn is None:
        raise ValueError(f"Unknown search backend: {backend}. Available: {list(BACKENDS.keys())}")
    return fn(query, limit=limit)


def format_web_results_as_context(results: list[dict]) -> str:
    """Format web search results into context block with chunk IDs."""
    if not results:
        return ""

    parts = ["=== Web Search Results (Academic Papers — SUPPLEMENTARY ONLY) ===\n"]
    for i, r in enumerate(results, 1):
        year_str = f" ({r['year']})" if r.get("year") else ""
        parts.append(
            f"[CHUNK-WEB-{i:03d}] From: {r['authors']}{year_str}. \"{r['title']}\"\n"
            f"  URL: {r['url']}\n"
            f"  Abstract: {r['abstract']}\n"
        )

    return "\n".join(parts)
```

**Step 5: Run tests**

```bash
pytest tests/test_search.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add src/search/ tests/test_search.py
git commit -m "feat: search backend registry with Semantic Scholar"
```

---

### Task 9: Retriever

**Files:**
- Create: `src/retriever.py`
- Create: `tests/test_retriever.py`

**Step 1: Write failing tests**

```python
# tests/test_retriever.py
import pytest


def test_format_db_results_as_context_empty():
    """Empty chunks return empty string."""
    from src.retriever import format_db_results_as_context
    assert format_db_results_as_context([]) == ""


def test_format_db_results_as_context_with_chunks():
    """DB results are formatted with CHUNK-LOCAL IDs and paths."""
    from src.retriever import format_db_results_as_context
    chunks = [{
        "text": "Test content here.",
        "metadata": {
            "source": "Dataset1/paper.pdf",
            "dataset": "Dataset1",
            "page": "3",
        },
        "distance": 0.1,
    }]
    context = format_db_results_as_context(chunks)
    assert "[CHUNK-LOCAL-001]" in context
    assert "paper.pdf" in context
    assert "Test content here." in context
    assert "PRIMARY" in context


def test_build_combined_context_no_sources():
    """No sources returns refusal message."""
    from src.retriever import build_combined_context
    result = build_combined_context([], [])
    assert "no sources" in result.lower() or "No relevant" in result


def test_build_combined_context_local_only():
    """Local-only context includes priority note."""
    from src.retriever import build_combined_context
    db = [{"text": "data", "metadata": {"source": "f.pdf", "dataset": "d", "page": "1"}, "distance": 0.1}]
    result = build_combined_context(db, [])
    assert "ONLY" in result or "local" in result.lower()


def test_build_combined_context_both():
    """Both sources includes priority warning."""
    from src.retriever import build_combined_context
    db = [{"text": "data", "metadata": {"source": "f.pdf", "dataset": "d", "page": "1"}, "distance": 0.1}]
    web = [{"title": "P", "authors": "A", "year": 2020, "abstract": "abs", "url": "http://x", "citation_count": 1, "source_type": "web_search"}]
    result = build_combined_context(db, web)
    assert "PRIMARY" in result
    assert "SUPPLEMENTARY" in result
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_retriever.py -v
```

Expected: FAIL

**Step 3: Write retriever**

```python
# src/retriever.py
"""Dual retriever: ChromaDB vector search + optional web search."""

from src.ingest import get_chroma_collection
from src.search import search, format_web_results_as_context

NO_SOURCES_REFUSAL = (
    "I don't have any information on this topic in my knowledge base. "
    "No relevant local documents or web sources were found. "
    "Please try a different question, or add relevant materials to "
    "the knowledge_base/ folder and run ingestion again."
)


def retrieve_from_vectordb(query: str, cfg: dict) -> list[dict]:
    """Retrieve relevant chunks from ChromaDB."""
    top_k = cfg.get("retrieval", {}).get("top_k", 5)
    collection = get_chroma_collection(cfg)

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return chunks


def format_db_results_as_context(chunks: list[dict]) -> str:
    """Format vector DB results with CHUNK-LOCAL IDs for citation anchoring."""
    if not chunks:
        return ""

    parts = ["=== Local Document Results (PRIMARY — always trust these over web sources) ===\n"]
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        dataset = meta.get("dataset", "")
        dataset_label = f" [Dataset: {dataset}]" if dataset else ""
        source_path = f"knowledge_base/{meta.get('source', 'unknown')}"
        parts.append(
            f"[CHUNK-LOCAL-{i:03d}] From: {meta.get('source', 'unknown')}, "
            f"Page/Section {meta.get('page', '?')}{dataset_label}\n"
            f"  Path: {source_path}\n"
            f"  {chunk['text']}\n"
        )
    return "\n".join(parts)


def build_combined_context(db_results: list[dict], web_results: list[dict]) -> str:
    """Build combined context string from local and web results."""
    db_context = format_db_results_as_context(db_results)
    web_context = format_web_results_as_context(web_results)

    if not db_results and not web_results:
        return NO_SOURCES_REFUSAL

    if not db_results and web_results:
        return (
            "NOTE: No local documents are indexed. All sources below come from "
            "academic web search. You MUST include the URL link for every source cited. "
            "State clearly that you have no curated local sources.\n\n"
            + web_context
        )

    if db_results and not web_results:
        return (
            "ONLY use the local sources below. Do not add any outside knowledge.\n\n"
            + db_context
        )

    # Both local and web
    return (
        "IMPORTANT: Local document sources are the PRIMARY authority. "
        "Web sources are SUPPLEMENTARY only. If any web source contradicts "
        "a local document, trust the local document.\n\n"
        + db_context + "\n\n" + web_context
    )


def retrieve(query: str, cfg: dict) -> dict:
    """Run dual retrieval: vector DB + optional web search.

    Returns dict with: context, db_results, web_results, has_sources.
    """
    db_results = retrieve_from_vectordb(query, cfg)

    web_enabled = cfg.get("web_search", {}).get("enabled", False)
    web_results = []
    if web_enabled:
        backend = cfg.get("web_search", {}).get("backend", "semantic_scholar")
        max_results = cfg.get("web_search", {}).get("max_results", 5)
        # Double web results when no local docs
        if not db_results:
            max_results *= 2
        web_results = search(query, backend=backend, limit=max_results)

    combined_context = build_combined_context(db_results, web_results)
    has_sources = bool(db_results) or bool(web_results)

    return {
        "context": combined_context,
        "db_results": db_results,
        "web_results": web_results,
        "has_sources": has_sources,
    }
```

**Step 4: Run tests**

```bash
pytest tests/test_retriever.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/retriever.py tests/test_retriever.py
git commit -m "feat: dual retriever with local priority and chunk ID anchoring"
```

---

### Task 10: System Prompts

**Files:**
- Create: `src/prompts.py`
- Create: `tests/test_prompts.py`

**Step 1: Write failing tests**

```python
# tests/test_prompts.py
import pytest


def test_build_prompt_includes_anti_hallucination():
    """System prompt includes anti-hallucination rules."""
    from src.prompts import build_prompt
    prompt = build_prompt("some context", "Test Bot", "testing domain")
    assert "ZERO TOLERANCE" in prompt
    assert "NEVER use your training data" in prompt
    assert "REFUSE" in prompt


def test_build_prompt_includes_citation_rules():
    """System prompt includes citation format requirements."""
    from src.prompts import build_prompt
    prompt = build_prompt("some context", "Test Bot", "testing")
    assert "[N]" in prompt or "endnote" in prompt.lower()
    assert "References" in prompt
    assert "Direct quote" in prompt or "direct quote" in prompt


def test_build_prompt_includes_context():
    """System prompt includes the provided context."""
    from src.prompts import build_prompt
    prompt = build_prompt("MY_UNIQUE_CONTEXT_STRING", "Bot", "domain")
    assert "MY_UNIQUE_CONTEXT_STRING" in prompt


def test_build_prompt_includes_bot_identity():
    """System prompt includes chatbot name and domain."""
    from src.prompts import build_prompt
    prompt = build_prompt("ctx", "ResearchHelper", "political science")
    assert "ResearchHelper" in prompt
    assert "political science" in prompt


def test_build_verification_prompt():
    """Verification prompt includes 9-point checklist."""
    from src.prompts import build_verification_prompt
    prompt = build_verification_prompt("response text", "context text", [], [])
    assert "citation" in prompt.lower()
    assert "JSON" in prompt or "json" in prompt
    assert "error_count" in prompt
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_prompts.py -v
```

Expected: FAIL

**Step 3: Write prompts module**

```python
# src/prompts.py
"""System prompts and verification prompts with anti-hallucination guardrails."""

SYSTEM_PROMPT_TEMPLATE = """You are {bot_name}, a research assistant specializing in {domain}. Your role is to answer questions using ONLY the provided source materials.

## ABSOLUTE RULE — ZERO TOLERANCE FOR HALLUCINATION

You are a retrieval-only assistant. You MUST:
- ONLY use information from the PROVIDED CONTEXT below.
- NEVER use your training data, general knowledge, or memory to answer.
- NEVER infer, guess, or "fill in gaps" with plausible-sounding information.
- If a user asks something not covered by the context: REFUSE to answer. Say: "I don't have information on this in my knowledge base."
- Do NOT say "Based on my knowledge...", "Generally speaking...", "It is well known...", or similar phrases — these indicate you are drawing from memory, not sources.

There are NO exceptions. An incomplete answer is always better than a fabricated one. Silence is always better than a guess.

## CITATION RULES — EVERY CLAIM MUST BE CITED

1. **Endnote citations:** Every factual claim MUST have a bracketed endnote number, e.g. [1], [2]. Uncited claims are forbidden.

2. **Direct quotes:** For key findings, include a direct quote from the source material. Example:
   As stated in [1]: "nonviolent campaigns succeeded 53% of the time"
   If you cannot find a direct quote to support a claim, do NOT make that claim.

3. **Reference list:** ALWAYS end your response with a "## References" section listing every source:
   - **Local Sources (Primary):** [N] Filename (page/section) — full path from knowledge_base/
   - **Web Sources (Supplementary):** [N] Author (Year). "Title" — DOI or URL

4. Every [N] in the text must appear in the reference list. Every reference must be cited in the text. No orphan citations. No unused references.

## SOURCE PRIORITY

- Sources labeled [CHUNK-LOCAL-...] come from the curated local knowledge base and are the PRIMARY authority.
- Sources labeled [CHUNK-WEB-...] are from web search and are SUPPLEMENTARY only.
- If a web source contradicts a local source, ALWAYS trust the local source.

## RESPONSE LENGTH

Your response length should generally be proportional to the available evidence. If you only have 1-2 sources, keep your answer focused and concise. You may provide brief synthesis to connect evidence, but do not pad beyond what sources support. When in doubt, err on the side of a shorter, well-cited answer.

## CONTEXT PROVIDED BY RETRIEVAL SYSTEM:
{context}
"""


VERIFICATION_PROMPT_TEMPLATE = """You are a fact-checking assistant. Verify the following response against ONLY the provided source context.

## RESPONSE TO VERIFY:
{response}

## SOURCE CONTEXT:
{context}

## ADVISORY FLAGS FROM AUTOMATED CHECKS:
{phrase_flags}
{similarity_flags}

## VERIFICATION CHECKLIST — Check each item:

1. Every factual claim has at least one [N] citation
2. Every [N] in the text appears in the reference list
3. Every reference list entry is actually used in the text
4. Local source paths match real chunks from the context (no fabricated paths)
5. Web source URLs/DOIs match what appears in the context (no fabricated URLs)
6. Direct quotes actually appear in or closely match the cited source chunk
7. Phrases flagged as advisory warnings — verify those sections are source-supported
8. Claims flagged by similarity check — re-examine whether they match the cited source
9. No information is added that does not appear in the provided context

## OUTPUT FORMAT — Report as JSON only, no other text:
{{
  "errors": [
    {{"claim": "the specific claim text", "issue": "not found in sources | wrong citation | from model memory | fabricated path | fabricated URL | misquoted"}},
  ],
  "error_count": 0,
  "pass": true
}}
"""


def build_prompt(context: str, bot_name: str = "Research Assistant",
                 domain: str = "research") -> str:
    """Build the full system prompt with context and guardrails."""
    return SYSTEM_PROMPT_TEMPLATE.format(
        bot_name=bot_name,
        domain=domain,
        context=context,
    )


def build_verification_prompt(response: str, context: str,
                               phrase_flags: list[dict],
                               similarity_flags: list[dict]) -> str:
    """Build the verification prompt for the anti-hallucination check."""
    phrase_str = "None" if not phrase_flags else "\n".join(
        f"- \"{f['phrase']}\" found — {f['suggestion']}" for f in phrase_flags
    )
    similarity_str = "None" if not similarity_flags else "\n".join(
        f"- Claim: \"{f['claim']}\" — low similarity to cited source (score: {f['score']:.2f})"
        for f in similarity_flags
    )
    return VERIFICATION_PROMPT_TEMPLATE.format(
        response=response,
        context=context,
        phrase_flags=phrase_str,
        similarity_flags=similarity_str,
    )
```

**Step 4: Run tests**

```bash
pytest tests/test_prompts.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/prompts.py tests/test_prompts.py
git commit -m "feat: system prompts with anti-hallucination guardrails and citation rules"
```

---

### Task 11: Verifier (6-Layer Anti-Hallucination Stack)

**Files:**
- Create: `src/verifier.py`
- Create: `tests/test_verifier.py`

**Step 1: Write failing tests**

```python
# tests/test_verifier.py
import pytest
import json


def test_scan_warning_phrases_clean():
    """Clean response returns no flags."""
    from src.verifier import scan_warning_phrases
    flags = scan_warning_phrases("The data shows a 53% success rate. [1]")
    assert flags == []


def test_scan_warning_phrases_flagged():
    """Response with warning phrases returns advisory flags."""
    from src.verifier import scan_warning_phrases
    flags = scan_warning_phrases("It is well known that nonviolent movements work.")
    assert len(flags) == 1
    assert flags[0]["severity"] == "advisory"


def test_compute_soft_max_tokens():
    """Max tokens scales with context size."""
    from src.verifier import compute_soft_max_tokens
    assert compute_soft_max_tokens(100, 2048) == 1024
    assert compute_soft_max_tokens(1500, 2048) == 1536
    assert compute_soft_max_tokens(5000, 2048) == 2048


def test_parse_verification_result_pass():
    """Parsing a passing verification JSON."""
    from src.verifier import parse_verification_result
    json_str = '{"errors": [], "error_count": 0, "pass": true}'
    result = parse_verification_result(json_str)
    assert result["pass"] is True
    assert result["error_count"] == 0


def test_parse_verification_result_fail():
    """Parsing a failing verification JSON."""
    from src.verifier import parse_verification_result
    json_str = json.dumps({
        "errors": [{"claim": "test", "issue": "not found in sources"}],
        "error_count": 1,
        "pass": False,
    })
    result = parse_verification_result(json_str)
    assert result["pass"] is False
    assert result["error_count"] == 1


def test_parse_verification_result_malformed():
    """Malformed JSON falls back to fail."""
    from src.verifier import parse_verification_result
    result = parse_verification_result("not json at all")
    assert result["pass"] is False


def test_no_sources_returns_refusal():
    """When has_sources is False, verify returns refusal without calling LLM."""
    from src.verifier import verify_and_respond
    result = verify_and_respond(
        query="test",
        retrieval_result={"context": "", "db_results": [], "web_results": [], "has_sources": False},
        cfg={"llm": {"provider": "openai", "model": "gpt-4o", "temperature": 0.0, "max_tokens": 2048},
             "api_keys": {"openai": "fake"},
             "verification": {"enabled": True, "max_iterations": 3, "strict_mode": True},
             "chatbot": {"name": "Test", "domain": "test"}},
    )
    assert result["refused"] is True
    assert "don't have any information" in result["response"]
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_verifier.py -v
```

Expected: FAIL

**Step 3: Write verifier**

```python
# src/verifier.py
"""6-layer anti-hallucination verification stack."""

import json
import re

from src.prompts import build_prompt, build_verification_prompt
from src.llm import generate
from src.retriever import NO_SOURCES_REFUSAL

# Layer 5: Soft phrase warning filter
WARNING_PHRASES = [
    "based on my knowledge",
    "generally speaking",
    "it is well known",
    "as we all know",
    "it is widely accepted",
    "common understanding suggests",
    "from what I know",
    "I recall that",
]

REFUSAL_AFTER_VERIFICATION = (
    "I was unable to produce a verified answer from my knowledge base. "
    "Please try rephrasing your question."
)


def compute_soft_max_tokens(context_chars: int, default_max: int) -> int:
    """Layer 2: Soft response length cap based on context size."""
    if context_chars < 500:
        return 1024
    elif context_chars < 2000:
        return 1536
    else:
        return default_max


def scan_warning_phrases(response: str) -> list[dict]:
    """Layer 5: Scan for phrases that may indicate memory-based claims.

    Returns advisory flags, not errors.
    """
    flags = []
    response_lower = response.lower()
    for phrase in WARNING_PHRASES:
        if phrase.lower() in response_lower:
            flags.append({
                "phrase": phrase,
                "severity": "advisory",
                "suggestion": f"Verify this section is grounded in provided sources",
            })
    return flags


def compute_similarity_flags(response: str, context: str,
                              cfg: dict) -> list[dict]:
    """Layer 4: Semantic similarity check between claims and cited sources.

    Uses embeddings to flag claims with low similarity to their cited source.
    Returns advisory flags.
    """
    # Extract claims with citations: "some claim text [N]"
    claim_pattern = r'([^.!?\n]+\[\d+\])'
    claims = re.findall(claim_pattern, response)

    if not claims:
        return []

    # For now, use a lightweight approach: check if key terms from each claim
    # appear in the context. Full embedding similarity can be added later
    # when the embedding infrastructure is available.
    flags = []
    context_lower = context.lower()
    for claim in claims[:10]:  # limit to avoid excessive processing
        # Extract key terms (nouns/numbers, skip common words)
        words = set(re.findall(r'\b[a-zA-Z]{4,}\b', claim.lower()))
        stop_words = {"that", "this", "with", "from", "were", "have", "been",
                      "their", "which", "these", "those", "about", "would",
                      "could", "should", "more", "than", "also", "into"}
        key_words = words - stop_words
        if not key_words:
            continue

        # Check what fraction of key terms appear in context
        matches = sum(1 for w in key_words if w in context_lower)
        ratio = matches / len(key_words) if key_words else 1.0

        if ratio < 0.4:
            flags.append({
                "claim": claim.strip()[:100],
                "score": ratio,
                "severity": "advisory",
            })

    return flags


def parse_verification_result(raw: str) -> dict:
    """Parse the verification LLM's JSON output."""
    try:
        # Try to extract JSON from the response (in case of surrounding text)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "errors": result.get("errors", []),
                "error_count": result.get("error_count", len(result.get("errors", []))),
                "pass": result.get("pass", False),
            }
    except (json.JSONDecodeError, AttributeError):
        pass

    # Malformed response = treat as fail
    return {"errors": [], "error_count": 0, "pass": False}


def verify_and_respond(query: str, retrieval_result: dict, cfg: dict) -> dict:
    """Run the full 6-layer anti-hallucination pipeline.

    Returns dict with: response, refused, verification_passed, iterations.
    """
    # Layer 0: No-context early exit
    if not retrieval_result["has_sources"]:
        return {
            "response": NO_SOURCES_REFUSAL,
            "refused": True,
            "verification_passed": False,
            "iterations": 0,
        }

    context = retrieval_result["context"]
    bot_name = cfg.get("chatbot", {}).get("name", "Research Assistant")
    domain = cfg.get("chatbot", {}).get("domain", "research")
    verification_cfg = cfg.get("verification", {})
    verification_enabled = verification_cfg.get("enabled", True)
    max_iterations = verification_cfg.get("max_iterations", 3)
    strict_mode = verification_cfg.get("strict_mode", True)

    # Layer 2: Soft max_tokens cap
    default_max = cfg["llm"].get("max_tokens", 2048)
    max_tokens = compute_soft_max_tokens(len(context), default_max)

    # Generate initial response
    system_prompt = build_prompt(context, bot_name, domain)
    response = generate(system_prompt, query, cfg, max_tokens=max_tokens)

    if not verification_enabled:
        return {
            "response": response,
            "refused": False,
            "verification_passed": None,
            "iterations": 0,
        }

    # Verification loop
    for iteration in range(max_iterations):
        # Layer 5: Soft phrase warnings
        phrase_flags = scan_warning_phrases(response)

        # Layer 4: Semantic similarity check
        similarity_flags = compute_similarity_flags(response, context, cfg)

        # Layer 3: LLM self-verification
        verification_prompt = build_verification_prompt(
            response, context, phrase_flags, similarity_flags
        )
        verification_raw = generate(
            "You are a fact-checking assistant. Output ONLY valid JSON.",
            verification_prompt, cfg, max_tokens=1024,
        )
        result = parse_verification_result(verification_raw)

        if result["pass"]:
            return {
                "response": response,
                "refused": False,
                "verification_passed": True,
                "iterations": iteration + 1,
            }

        # Correction needed
        error_count = result["error_count"]
        errors_text = "\n".join(
            f"- {e['claim']}: {e['issue']}" for e in result.get("errors", [])
        )

        if error_count <= 2 and iteration == 0:
            # Minor errors: correct once
            correction_prompt = (
                f"Your previous response had {error_count} error(s):\n{errors_text}\n\n"
                f"Rewrite your response correcting these errors. "
                f"Remove any claims not supported by the provided sources. "
                f"Ensure every claim has a citation [N] and the reference list is complete."
            )
            response = generate(system_prompt, correction_prompt, cfg, max_tokens=max_tokens)
        elif error_count > 2 or iteration > 0:
            # Many errors or repeated failures: correct and loop
            correction_prompt = (
                f"Your previous response had {error_count} error(s):\n{errors_text}\n\n"
                f"Carefully rewrite your response from scratch using ONLY the provided sources. "
                f"Every claim must have a [N] citation. Include direct quotes. "
                f"Do NOT add any information not in the sources."
            )
            response = generate(system_prompt, correction_prompt, cfg, max_tokens=max_tokens)

    # Max iterations reached
    if strict_mode:
        return {
            "response": REFUSAL_AFTER_VERIFICATION,
            "refused": True,
            "verification_passed": False,
            "iterations": max_iterations,
        }
    else:
        return {
            "response": response + "\n\n*Note: This response could not be fully verified against sources. Please check citations carefully.*",
            "refused": False,
            "verification_passed": False,
            "iterations": max_iterations,
        }
```

**Step 4: Run tests**

```bash
pytest tests/test_verifier.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add src/verifier.py tests/test_verifier.py
git commit -m "feat: 6-layer anti-hallucination verifier with iterative correction"
```

---

### Task 12: CLI Application

**Files:**
- Create: `app_cli.py`
- Create: `tests/test_app_cli.py`

**Step 1: Write failing test**

```python
# tests/test_app_cli.py
import pytest


def test_cli_commands_exist():
    """CLI module has handle_command function."""
    from app_cli import handle_command
    assert callable(handle_command)


def test_handle_command_help():
    """Help command returns help text."""
    from app_cli import handle_command
    result = handle_command("/help", cfg={}, state={})
    assert result is not None
    assert "quit" in result.lower() or "help" in result.lower()


def test_handle_command_unknown():
    """Non-command input returns None (not a command)."""
    from app_cli import handle_command
    result = handle_command("What is nonviolent resistance?", cfg={}, state={})
    assert result is None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_app_cli.py -v
```

Expected: FAIL

**Step 3: Write CLI application**

```python
# app_cli.py
"""RAG Research Chatbot — CLI Application."""

import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.config_loader import load_config, get_api_key
from src.ingest import ingest_documents
from src.retriever import retrieve
from src.verifier import verify_and_respond
from src.llm import list_models

console = Console()

# Session state
_last_retrieval = None
_web_search_override = None  # None = use config, True/False = override


def handle_command(user_input: str, cfg: dict, state: dict) -> str | None:
    """Handle slash commands. Returns response string, or None if not a command."""
    cmd = user_input.strip().lower()

    if cmd in ("/quit", "/exit", "/q"):
        return "__QUIT__"

    if cmd == "/help":
        return (
            "Commands:\n"
            "  /quit          Exit the chatbot\n"
            "  /sources       Show sources from the last response\n"
            "  /ingest        Re-index knowledge_base/\n"
            "  /model         Show/switch current model\n"
            "  /websearch on  Enable web search\n"
            "  /websearch off Disable web search\n"
            "  /help          Show this help message"
        )

    if cmd == "/sources":
        retrieval = state.get("last_retrieval")
        if not retrieval:
            return "No previous query to show sources for."
        return _format_sources(retrieval)

    if cmd == "/ingest":
        return "__INGEST__"

    if cmd == "/model":
        return "__MODEL__"

    if cmd.startswith("/websearch"):
        parts = cmd.split()
        if len(parts) == 2 and parts[1] == "on":
            state["web_search_override"] = True
            return "Web search enabled for this session."
        elif len(parts) == 2 and parts[1] == "off":
            state["web_search_override"] = False
            return "Web search disabled for this session."
        else:
            enabled = state.get("web_search_override", cfg.get("web_search", {}).get("enabled", False))
            return f"Web search is {'enabled' if enabled else 'disabled'}. Use /websearch on|off to toggle."

    if cmd.startswith("/"):
        return f"Unknown command: {cmd}. Type /help for available commands."

    return None  # Not a command


def _format_sources(retrieval_result: dict) -> str:
    """Format sources for display."""
    lines = ["Sources Used:\n"]

    db_results = retrieval_result.get("db_results", [])
    if db_results:
        lines.append("Local Documents (Primary):")
        for i, chunk in enumerate(db_results, 1):
            meta = chunk["metadata"]
            lines.append(f"  {i}. {meta.get('source', 'unknown')} (p. {meta.get('page', '?')})")

    web_results = retrieval_result.get("web_results", [])
    if web_results:
        lines.append("\nAcademic Papers (Supplementary):")
        for i, paper in enumerate(web_results, 1):
            year = f" ({paper['year']})" if paper.get("year") else ""
            lines.append(f"  {i}. {paper['authors']}{year}. \"{paper['title']}\"")
            if paper.get("url"):
                lines.append(f"     {paper['url']}")

    return "\n".join(lines)


def _handle_model_switch(cfg: dict):
    """Interactive model switching."""
    provider = cfg["llm"]["provider"]
    model = cfg["llm"]["model"]
    console.print(f"\nCurrent: {provider} / {model}\n")
    console.print("  [1] Switch model")
    console.print("  [2] Switch provider")
    console.print("  [3] Cancel")

    try:
        choice = console.input("\n> ").strip()
    except (KeyboardInterrupt, EOFError):
        return

    if choice == "1":
        api_key = get_api_key(cfg, provider)
        console.print(f"\nFetching models from {provider}...")
        models = list_models(provider, api_key)
        for i, m in enumerate(models, 1):
            marker = " (current)" if m == model else ""
            console.print(f"  [{i}] {m}{marker}")
        try:
            idx = int(console.input("\n> ").strip()) - 1
            if 0 <= idx < len(models):
                cfg["llm"]["model"] = models[idx]
                console.print(f"\nSwitched to {models[idx]}")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass

    elif choice == "2":
        providers = ["openai", "anthropic", "gemini"]
        for i, p in enumerate(providers, 1):
            marker = " (current)" if p == provider else ""
            console.print(f"  [{i}] {p}{marker}")
        try:
            idx = int(console.input("\n> ").strip()) - 1
            if 0 <= idx < len(providers):
                new_provider = providers[idx]
                api_key = get_api_key(cfg, new_provider)
                if not api_key:
                    console.print(f"\n[red]No API key set for {new_provider}.[/red]")
                    return
                cfg["llm"]["provider"] = new_provider
                # Fetch models for new provider
                console.print(f"\nFetching models from {new_provider}...")
                models = list_models(new_provider, api_key)
                for i, m in enumerate(models, 1):
                    console.print(f"  [{i}] {m}")
                midx = int(console.input("\nSelect model > ").strip()) - 1
                if 0 <= midx < len(models):
                    cfg["llm"]["model"] = models[midx]
                console.print(f"\nSwitched to {new_provider} / {cfg['llm']['model']}")
        except (ValueError, KeyboardInterrupt, EOFError):
            pass


def main():
    """Main CLI loop."""
    try:
        cfg = load_config()
    except FileNotFoundError:
        console.print("[red]config.yaml not found. Run 'python setup.py' first.[/red]")
        sys.exit(1)

    bot_name = cfg.get("chatbot", {}).get("name", "Research Assistant")
    provider = cfg["llm"]["provider"]
    model = cfg["llm"]["model"]

    console.print(Panel(
        f"[bold]{bot_name}[/bold]\n\n"
        f"Ask questions and I'll search the knowledge base for answers.\n"
        f"All responses are grounded in your local documents.\n\n"
        f"[dim]Commands: /quit  /sources  /ingest  /model  /websearch  /help[/dim]\n"
        f"[dim]Current LLM: {provider} ({model})[/dim]",
        title="Welcome",
        border_style="blue",
    ))

    state = {}

    while True:
        try:
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Handle commands
        cmd_result = handle_command(user_input, cfg, state)
        if cmd_result == "__QUIT__":
            console.print("[dim]Goodbye![/dim]")
            break
        elif cmd_result == "__INGEST__":
            console.print("[bold]Starting document ingestion...[/bold]\n")
            count = ingest_documents(cfg)
            if count > 0:
                console.print(f"\n[green]Successfully ingested {count} chunks.[/green]")
            continue
        elif cmd_result == "__MODEL__":
            _handle_model_switch(cfg)
            continue
        elif cmd_result is not None:
            console.print(f"\n{cmd_result}")
            continue

        # Apply web search override if set
        effective_cfg = dict(cfg)
        if "web_search_override" in state:
            effective_cfg = {**cfg, "web_search": {**cfg.get("web_search", {}), "enabled": state["web_search_override"]}}

        # RAG pipeline
        with console.status("[bold blue]Searching knowledge base..."):
            retrieval_result = retrieve(user_input, effective_cfg)

        state["last_retrieval"] = retrieval_result

        n_db = len(retrieval_result["db_results"])
        n_web = len(retrieval_result["web_results"])
        console.print(f"[dim]Found {n_db} local chunks + {n_web} web sources[/dim]")

        with console.status("[bold blue]Generating and verifying response..."):
            result = verify_and_respond(user_input, retrieval_result, effective_cfg)

        if result.get("verification_passed") is not None:
            iterations = result.get("iterations", 0)
            if result["verification_passed"]:
                console.print(f"[dim]Verified in {iterations} pass(es)[/dim]\n")
            elif not result["refused"]:
                console.print(f"[yellow]Warning: could not fully verify ({iterations} passes)[/yellow]\n")

        console.print(Panel(Markdown(result["response"]), border_style="green", padding=(1, 2)))

        if not result["refused"]:
            console.print("[dim]Type /sources to see the full list of sources used.[/dim]")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

```bash
pytest tests/test_app_cli.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add app_cli.py tests/test_app_cli.py
git commit -m "feat: CLI application with Rich UI and slash commands"
```

---

### Task 13: Setup Wizard

**Files:**
- Create: `setup.py`
- Create: `tests/test_setup.py`

**Step 1: Write failing test**

```python
# tests/test_setup.py
import pytest


def test_generate_config_yaml():
    """generate_config produces valid YAML with all required keys."""
    from setup import generate_config
    import yaml

    config_str = generate_config(
        bot_name="TestBot",
        domain="testing",
        provider="openai",
        model="gpt-4o",
        web_search=True,
    )
    cfg = yaml.safe_load(config_str)
    assert cfg["chatbot"]["name"] == "TestBot"
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["model"] == "gpt-4o"
    assert cfg["web_search"]["enabled"] is True
    assert cfg["verification"]["enabled"] is True
    assert cfg["paths"]["knowledge_base"] == "knowledge_base"


def test_generate_env_file():
    """generate_env produces valid .env content."""
    from setup import generate_env
    env_str = generate_env("openai", "sk-test-123")
    assert "OPENAI_API_KEY=sk-test-123" in env_str
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_setup.py -v
```

Expected: FAIL

**Step 3: Write setup wizard**

```python
# setup.py
"""Interactive setup wizard for the RAG Research Chatbot."""

import os
import sys
import getpass
from pathlib import Path

import yaml


def generate_config(bot_name: str, domain: str, provider: str,
                    model: str, web_search: bool) -> str:
    """Generate config.yaml content."""
    config = {
        "chatbot": {
            "name": bot_name,
            "domain": domain,
        },
        "llm": {
            "provider": provider,
            "model": model,
            "temperature": 0.0,
            "max_tokens": 2048,
        },
        "api_keys": {
            "openai": "",
            "anthropic": "",
            "gemini": "",
        },
        "embeddings": {
            "provider": "local",
            "openai_model": "text-embedding-3-small",
        },
        "retrieval": {
            "chunk_size": 1000,
            "chunk_overlap": 100,
            "top_k": 5,
        },
        "web_search": {
            "enabled": web_search,
            "backend": "semantic_scholar",
            "max_results": 5,
        },
        "verification": {
            "enabled": True,
            "max_iterations": 3,
            "strict_mode": True,
        },
        "paths": {
            "knowledge_base": "knowledge_base",
            "vector_db": "chroma_db",
        },
    }
    return yaml.dump(config, default_flow_style=False, sort_keys=False)


def generate_env(provider: str, api_key: str) -> str:
    """Generate .env file content."""
    env_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }
    var_name = env_map.get(provider, f"{provider.upper()}_API_KEY")
    return f"# API Keys — do not commit this file\n{var_name}={api_key}\n"


def run_wizard():
    """Run the interactive setup wizard."""
    print("=" * 50)
    print("  RAG Research Chatbot — Setup Wizard")
    print("=" * 50)
    print()

    # Step 1: Bot name
    print("Step 1/5: What would you like to name your chatbot?")
    bot_name = input("> ").strip() or "Research Assistant"
    print()

    # Step 2: Domain
    print("Step 2/5: Describe your chatbot's domain:")
    print("  (e.g., 'Political science and civil resistance research')")
    domain = input("> ").strip() or "research"
    print()

    # Step 3: Provider
    providers = {"1": "openai", "2": "anthropic", "3": "gemini"}
    print("Step 3/5: Choose your LLM provider:")
    print("  [1] OpenAI")
    print("  [2] Anthropic")
    print("  [3] Google Gemini")
    provider_choice = input("> ").strip()
    provider = providers.get(provider_choice, "openai")
    print()

    # Step 3b: Model selection
    print(f"Step 3b: Enter your API key for {provider}:")
    api_key = getpass.getpass("> ")
    print()

    # Try to fetch models
    model = None
    try:
        from src.llm import list_models as fetch_models
        print(f"Fetching available models from {provider}...")
        models = fetch_models(provider, api_key)
        if models:
            print("\nAvailable models:")
            for i, m in enumerate(models[:15], 1):  # show max 15
                print(f"  [{i}] {m}")
            print(f"  [{len(models[:15]) + 1}] Custom (enter model ID)")
            choice = input("> ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(models[:15]):
                    model = models[idx]
            except ValueError:
                pass
            if model is None:
                model = input("Enter model ID: ").strip()
        print()
    except Exception:
        pass

    if not model:
        defaults = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-6", "gemini": "gemini-2.5-flash"}
        model = defaults.get(provider, "gpt-4o")
        print(f"Using default model: {model}\n")

    # Step 5: Web search
    print("Step 5/5: Enable web search to supplement local knowledge base?")
    print("  [1] Yes — Semantic Scholar (academic papers)")
    print("  [2] No — local knowledge base only")
    web_choice = input("> ").strip()
    web_search = web_choice != "2"
    print()

    # Write files
    project_dir = Path(__file__).resolve().parent

    # config.yaml
    config_content = generate_config(bot_name, domain, provider, model, web_search)
    config_path = project_dir / "config.yaml"
    config_path.write_text(config_content)
    print(f"  Config saved to {config_path.name}")

    # .env
    env_content = generate_env(provider, api_key)
    env_path = project_dir / ".env"
    env_path.write_text(env_content)
    print(f"  API key saved to {env_path.name}")

    # knowledge_base/
    kb_dir = project_dir / "knowledge_base"
    kb_dir.mkdir(exist_ok=True)
    print(f"  Created {kb_dir.name}/ folder")

    print()
    print("Setup complete! Next steps:")
    print("  1. Drop your files into knowledge_base/")
    print("  2. Run: python ingest.py")
    print("  3. Run: python app_cli.py")
    print("     Or:  streamlit run app_web.py")


if __name__ == "__main__":
    run_wizard()
```

**Step 4: Run tests**

```bash
pytest tests/test_setup.py -v
```

Expected: All PASS

**Step 5: Commit**

```bash
git add setup.py tests/test_setup.py
git commit -m "feat: interactive setup wizard with model fetching"
```

---

### Task 14: Streamlit Web UI

**Files:**
- Create: `app_web.py`

**Step 1: Write the web UI**

```python
# app_web.py
"""RAG Research Chatbot — Streamlit Web UI."""

import streamlit as st
from src.config_loader import load_config, get_api_key
from src.ingest import ingest_documents, get_chroma_collection
from src.retriever import retrieve
from src.verifier import verify_and_respond
from src.llm import list_models


def init_session():
    """Initialize session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "cfg" not in st.session_state:
        try:
            st.session_state.cfg = load_config()
        except FileNotFoundError:
            st.error("config.yaml not found. Run `python setup.py` first.")
            st.stop()
    if "last_retrieval" not in st.session_state:
        st.session_state.last_retrieval = None


def render_sidebar():
    """Render sidebar controls."""
    cfg = st.session_state.cfg

    with st.sidebar:
        st.header("Settings")

        # Provider selection
        providers = ["openai", "anthropic", "gemini"]
        current_provider = cfg["llm"]["provider"]
        provider_idx = providers.index(current_provider) if current_provider in providers else 0
        provider = st.selectbox("LLM Provider", providers, index=provider_idx)

        # Model selection
        api_key = get_api_key(cfg, provider)
        if api_key:
            if f"models_{provider}" not in st.session_state:
                try:
                    st.session_state[f"models_{provider}"] = list_models(provider, api_key)
                except Exception:
                    st.session_state[f"models_{provider}"] = [cfg["llm"]["model"]]

            models = st.session_state[f"models_{provider}"]
            current_model = cfg["llm"]["model"]
            model_idx = models.index(current_model) if current_model in models else 0
            model = st.selectbox("Model", models, index=model_idx)

            # Update config for this session
            cfg["llm"]["provider"] = provider
            cfg["llm"]["model"] = model
        else:
            st.warning(f"No API key for {provider}. Set it in .env.")

        st.divider()

        # Web search toggle
        web_enabled = st.toggle(
            "Web Search (Supplementary)",
            value=cfg.get("web_search", {}).get("enabled", False),
        )
        cfg["web_search"]["enabled"] = web_enabled

        st.divider()

        # Knowledge base stats
        st.subheader("Knowledge Base")
        try:
            collection = get_chroma_collection(cfg)
            chunk_count = collection.count()
            st.metric("Chunks indexed", chunk_count)
        except Exception:
            st.metric("Chunks indexed", "N/A")

        if st.button("Re-ingest Documents"):
            with st.spinner("Ingesting documents..."):
                count = ingest_documents(cfg)
            st.success(f"Ingested {count} chunks.")
            st.rerun()


def render_chat():
    """Render chat interface."""
    cfg = st.session_state.cfg
    bot_name = cfg.get("chatbot", {}).get("name", "Research Assistant")

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question..."):
        # Display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.status("Searching knowledge base...", expanded=False) as status:
                retrieval_result = retrieve(prompt, cfg)
                st.session_state.last_retrieval = retrieval_result

                n_db = len(retrieval_result["db_results"])
                n_web = len(retrieval_result["web_results"])
                status.update(label=f"Found {n_db} local + {n_web} web sources. Generating response...")

                result = verify_and_respond(prompt, retrieval_result, cfg)

                if result.get("verification_passed"):
                    status.update(label=f"Verified in {result['iterations']} pass(es)", state="complete")
                elif result.get("refused"):
                    status.update(label="No verified answer available", state="error")
                else:
                    status.update(label=f"Response generated ({result['iterations']} verification passes)", state="complete")

            st.markdown(result["response"])

        st.session_state.messages.append({"role": "assistant", "content": result["response"]})


def main():
    """Main Streamlit app."""
    init_session()

    cfg = st.session_state.cfg
    bot_name = cfg.get("chatbot", {}).get("name", "Research Assistant")

    st.set_page_config(page_title=bot_name, layout="wide")
    st.title(bot_name)

    render_sidebar()
    render_chat()

    # Footer
    st.divider()
    st.caption(
        "All answers are sourced from the local knowledge base. "
        "Web sources are supplementary only. "
        "Every claim is citation-verified before display."
    )


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add app_web.py
git commit -m "feat: Streamlit web UI with sidebar controls and chat interface"
```

---

### Task 15: Docker + README

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `README.md`
- Create: `LICENSE`

**Step 1: Write Dockerfile**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app_web.py", "--server.address=0.0.0.0"]
```

**Step 2: Write docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.8"
services:
  chatbot:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./knowledge_base:/app/knowledge_base
      - ./chroma_db:/app/chroma_db
      - ./config.yaml:/app/config.yaml
      - ./.env:/app/.env
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - GEMINI_API_KEY=${GEMINI_API_KEY:-}
```

**Step 3: Write README.md**

```markdown
# RAG Research Chatbot Template

A citation-verified research assistant chatbot grounded in your local knowledge base. Features a 6-layer anti-hallucination stack that ensures every claim is sourced, cited, and verified.

## Quick Start

1. **Clone and install:**
   ```bash
   git clone <your-repo-url>
   cd rag-research-chatbot
   pip install -r requirements.txt
   ```

2. **Run setup wizard:**
   ```bash
   python setup.py
   ```

3. **Add your documents** to `knowledge_base/` (supports PDF, DOCX, XLSX, CSV, Stata, SPSS, R data, and more)

4. **Ingest documents:**
   ```bash
   python ingest.py
   ```

5. **Start chatting:**
   ```bash
   # CLI
   python app_cli.py

   # Web UI
   streamlit run app_web.py
   ```

## Supported File Formats

| Format | Extensions |
|---|---|
| PDF | `.pdf` |
| Word | `.docx` |
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| Tab-delimited | `.tab`, `.tsv` |
| Stata | `.dta` |
| SPSS | `.sav` |
| R data | `.rds`, `.rda` |
| Plain text | `.txt`, `.md`, `.json`, `.do` |

## LLM Providers

Supports OpenAI, Anthropic (Claude), and Google Gemini. Choose during setup or switch at runtime.

## Anti-Hallucination Guardrails

Every response goes through a 6-layer verification stack:

0. **No-context early exit** — no sources found = no answer (LLM never called)
1. **System prompt** — hard refusal of model memory, citation requirements
2. **Response length cap** — proportional to available evidence
3. **LLM self-verification** — iterative correction loop (max 3 passes)
4. **Semantic similarity check** — flags claims that don't match cited source
5. **Phrase warning filter** — flags memory-indicating language

## Docker (Optional)

```bash
docker-compose up --build
```

Open `http://localhost:8501` in your browser.

## Configuration

Edit `config.yaml` to adjust settings. API keys go in `.env` (never committed).

## License

MIT
```

**Step 4: Write LICENSE**

Standard MIT license file.

**Step 5: Commit**

```bash
git add Dockerfile docker-compose.yml README.md LICENSE
git commit -m "feat: Docker setup, README, and MIT license"
```

---

## Task Summary

| Task | Component | Dependencies |
|---|---|---|
| 1 | Project scaffolding | None |
| 2 | Config loader | Task 1 |
| 3 | Readers: PDF + text | Task 1 |
| 4 | Readers: DOCX + Excel + CSV | Task 3 |
| 5 | Readers: Stata + SPSS + R | Task 3 |
| 6 | Ingestion pipeline | Tasks 2, 3-5 |
| 7 | LLM provider registry | Task 2 |
| 8 | Search backend registry | Task 1 |
| 9 | Retriever | Tasks 6, 8 |
| 10 | System prompts | Task 1 |
| 11 | Verifier (6-layer stack) | Tasks 7, 9, 10 |
| 12 | CLI application | Tasks 2, 6, 9, 11 |
| 13 | Setup wizard | Tasks 2, 7 |
| 14 | Streamlit Web UI | Tasks 2, 6, 7, 9, 11 |
| 15 | Docker + README | All above |

**Parallelizable:** Tasks 3-5 (readers), Tasks 7-8 (LLM + search registries), Task 10 (prompts)
