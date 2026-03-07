"""Reader for R data files: .rds and .rda"""
MAX_CHUNK_CHARS = 6000

def read_rdata(file_path: str) -> list[dict]:
    try:
        import pyreadr
        result = pyreadr.read_r(file_path)
        pages = []
        for name, df in result.items():
            name_display = name if name is not None else "data"
            headers = list(df.columns)
            header_line = f"Object: {name_display} | Columns: {', '.join(headers)}\n"
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
                    pages.append({"page": f"{name_display}_rows_{block_start}-{block_start + len(block) - 1}", "text": text})
                    block = []
                    block_chars = len(header_line)
                    block_start = idx + 1
                block.append(row_text)
                block_chars += len(row_text) + 1
            if block:
                text = header_line + "\n".join(block)
                pages.append({"page": f"{name_display}_rows_{block_start}-{block_start + len(block) - 1}", "text": text})
        return pages
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []
