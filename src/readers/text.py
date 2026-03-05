"""Reader for plain text files: .txt, .md, .json, .do"""


def read_text(file_path: str) -> list[dict]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if not text.strip():
        return []
    return [{"page": 1, "text": text.strip()}]
