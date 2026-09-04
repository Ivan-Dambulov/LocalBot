from pathlib import Path

import pandas as pd
from docx import Document
from pypdf import PdfReader

MAX_FILE_CHARS = 50000


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in [".txt", ".md"]:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

    elif suffix == ".pdf":
        text = extract_pdf(path)

    elif suffix == ".docx":
        text = extract_docx(path)

    elif suffix in [".xlsx", ".xls"]:
        text = extract_excel(path)

    else:
        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    return text[:MAX_FILE_CHARS]


def extract_pdf(path):
    reader = PdfReader(path)

    chunks = []

    for page in reader.pages:
        chunks.append(
            page.extract_text() or ""
        )

    return "\n".join(chunks)


def extract_docx(path):
    document = Document(path)

    return "\n".join(
        paragraph.text
        for paragraph in document.paragraphs
    )


def extract_excel(path):
    sheets = pd.read_excel(
        path,
        sheet_name=None
    )

    parts = []

    for name, frame in sheets.items():
        parts.append(
            f"Sheet: {name}\n"
            f"{frame.to_string(index=False)}"
        )

    return "\n\n".join(parts)