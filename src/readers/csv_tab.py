"""Reader for CSV, tab-delimited, and TSV files."""
import csv
MAX_CHUNK_CHARS = 6000

def read_csv_tab(file_path: str, delimiter: str = None) -> list[dict]:
    from pathlib import Path
    if delimiter is None:
        ext = Path(file_path).suffix.lower()
        delimiter = "\t" if ext in (".tab", ".tsv") else ","

    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        return []

    headers = [h.strip().strip('"') for h in rows[0]]
    row_texts = []
    for row in rows[1:]:
        parts = []
        padded_row = list(row) + [""] * max(0, len(headers) - len(row))
        for header, val in zip(headers, padded_row[:len(headers)]):
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
            pages.append({"page": f"rows_{block_start}-{block_start + len(block) - 1}", "text": text})
            block = []
            block_chars = len(header_line)
            block_start = idx + 1
        block.append(row_text)
        block_chars += len(row_text) + 1

    if block:
        text = header_line + "\n".join(block)
        pages.append({"page": f"rows_{block_start}-{block_start + len(block) - 1}", "text": text})
    return pages
