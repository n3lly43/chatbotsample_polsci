"""Reader for Word .docx files."""
from docx import Document

def read_docx(file_path: str) -> list[dict]:
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return []
    return [{"page": 1, "text": "\n\n".join(paragraphs)}]
