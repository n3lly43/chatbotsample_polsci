"""Reader for Stata .dta files via pyreadstat."""
MAX_CHUNK_CHARS = 6000

def read_stata(file_path: str) -> list[dict]:
    try:
        import pyreadstat
        df, meta = pyreadstat.read_dta(file_path)
        return _dataframe_to_pages(df, meta)
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []

def _dataframe_to_pages(df, meta) -> list[dict]:
    pages = []
    info_lines = []
    if hasattr(meta, "file_label") and meta.file_label:
        info_lines.append(f"Dataset label: {meta.file_label}")
    info_lines.append(f"Variables ({len(df.columns)}): {', '.join(df.columns)}")
    if hasattr(meta, "column_names_to_labels") and meta.column_names_to_labels:
        labels = meta.column_names_to_labels
        label_lines = [f"  {col}: {labels[col]}" for col in df.columns if labels.get(col)]
        if label_lines:
            info_lines.append("Variable descriptions:")
            info_lines.extend(label_lines)
    pages.append({"page": "metadata", "text": "\n".join(info_lines)})

    headers = list(df.columns)
    header_line = f"Columns: {', '.join(headers)}\n"
    block = []
    block_chars = len(header_line)
    block_start = 1
    for idx, (_, row) in enumerate(df.iterrows()):
        parts = []
        for col in headers:
            val = row[col]
            if val is not None and str(val).strip() and str(val).lower() not in ("nan", "nat", "<na>", "inf", "-inf"):
                parts.append(f"{col}: {val}")
        if not parts:
            continue
        row_text = "; ".join(parts)
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
