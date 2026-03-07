"""Reader for SPSS .sav files via pyreadstat."""
from src.readers.stata import _dataframe_to_pages

def read_spss(file_path: str) -> list[dict]:
    try:
        import pyreadstat
        df, meta = pyreadstat.read_sav(file_path)
        return _dataframe_to_pages(df, meta)
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []
