"""Reader for SPSS .sav files via pyreadstat."""
from src.readers.stata import _dataframe_to_pages

def read_spss(file_path: str) -> list[dict]:
    import pyreadstat
    df, meta = pyreadstat.read_sav(file_path)
    return _dataframe_to_pages(df, meta)
