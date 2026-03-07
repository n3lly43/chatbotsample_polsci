"""Reader for PDF files."""


def read_pdf(file_path: str) -> list[dict]:
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append({"page": i + 1, "text": text.strip()})
    return pages
