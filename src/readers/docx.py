"""Reader for Word .docx files."""


def read_docx(file_path: str) -> list[dict]:
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return []
    return [{"page": 1, "text": "\n\n".join(paragraphs)}]
