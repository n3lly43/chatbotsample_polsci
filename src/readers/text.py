"""Reader for plain text files: .txt, .md, .json, .do"""


def read_text(file_path: str) -> list[dict]:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        if not text.strip():
            return []
        return [{"page": 1, "text": text.strip()}]
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []
