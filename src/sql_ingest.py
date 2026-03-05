"""SQL ingestion: load tabular files into SQLite for structured queries."""

import re

# Extensions that trigger SQL ingestion (tabular formats)
SQL_EXTENSIONS = {".csv", ".tab", ".tsv", ".xlsx", ".xls", ".dta", ".sav", ".rds", ".rda"}


def _sanitize_part(s: str) -> str:
    """Sanitize a single name part: replace non-alnum with _, collapse, strip."""
    s = re.sub(r"[^a-zA-Z0-9]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _sanitize_table_name(dataset: str, stem: str, ext: str, sheet: str = None) -> str:
    """Convert dataset/filename/ext into a valid SQL table identifier."""
    suffix = f"{_sanitize_part(stem)}_{ext.lstrip('.')}"
    if sheet:
        suffix += f"_{_sanitize_part(sheet)}"
    name = f"{_sanitize_part(dataset)}__{suffix}".lower()
    if not name or not name[0].isalpha():
        name = "t_" + name
    return name


def _infer_column_type(values: list) -> str:
    """Infer SQLite column type from a list of raw string values."""
    non_empty = [v for v in values if v is not None and str(v).strip() and str(v).lower() != "nan"]
    if not non_empty:
        return "TEXT"
    # Try INTEGER
    try:
        for v in non_empty:
            int(str(v).strip())
        return "INTEGER"
    except (ValueError, TypeError):
        pass
    # Try REAL
    try:
        for v in non_empty:
            float(str(v).strip())
        return "REAL"
    except (ValueError, TypeError):
        pass
    return "TEXT"


def _get_sample_values(values: list, n: int = 3) -> list:
    """Get up to n unique non-empty sample values."""
    seen = set()
    samples = []
    for v in values:
        if v is not None and str(v).strip() and str(v).lower() != "nan":
            v_str = str(v).strip()
            if v_str not in seen:
                seen.add(v_str)
                samples.append(v_str)
                if len(samples) >= n:
                    break
    return samples
