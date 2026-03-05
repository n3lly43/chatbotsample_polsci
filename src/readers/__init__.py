"""File reader registry. Maps extensions to reader functions."""

from src.readers.pdf import read_pdf
from src.readers.text import read_text
from src.readers.docx import read_docx
from src.readers.excel import read_excel
from src.readers.csv_tab import read_csv_tab
from src.readers.stata import read_stata
from src.readers.spss import read_spss
from src.readers.rdata import read_rdata

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
    from pathlib import Path
    ext = Path(file_path).suffix.lower()
    reader = READERS.get(ext)
    if reader is None:
        print(f"  Unsupported file type: {ext}, skipping {file_path}")
        return []
    return reader(file_path)
