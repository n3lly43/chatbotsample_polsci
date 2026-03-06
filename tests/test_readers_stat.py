import pytest

def test_stata_reader(tmp_path):
    pytest.importorskip("pyreadstat")
    import pandas as pd
    import pyreadstat
    df = pd.DataFrame({"country": ["India", "Poland"], "year": [1930, 1980]})
    path = str(tmp_path / "test.dta")
    pyreadstat.write_dta(df, path)
    from src.readers.stata import read_stata
    pages = read_stata(path)
    assert len(pages) >= 1
    assert "India" in pages[0]["text"] or "India" in pages[1]["text"]

def test_spss_reader(tmp_path):
    pytest.importorskip("pyreadstat")
    import pandas as pd
    import pyreadstat
    df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [85.0, 92.0]})
    path = str(tmp_path / "test.sav")
    pyreadstat.write_sav(df, path)
    from src.readers.spss import read_spss
    pages = read_spss(path)
    assert len(pages) >= 1
    found = any("Alice" in p["text"] for p in pages)
    assert found

def test_rdata_reader(tmp_path):
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
