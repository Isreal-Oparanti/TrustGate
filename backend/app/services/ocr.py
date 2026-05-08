from app.models.document import Document
from app.utils.file_handler import read_text_file


def parse_documents(documents: list[Document]) -> str:
    extracted_chunks: list[str] = []
    for document in documents:
        text = read_text_file(document.path)
        if text:
            extracted_chunks.append(text)
        else:
            extracted_chunks.append(
                f"OCR placeholder for {document.filename}: document accepted for AI parsing."
            )
    return "\n".join(extracted_chunks).strip()
