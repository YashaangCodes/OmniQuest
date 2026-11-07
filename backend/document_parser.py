"""
Document parsing service for OmniQuest v1.0.

Supports PDF, DOCX, PPTX, and TXT files.
Extracts readable text in document order without executing any file content.
"""

from __future__ import annotations

import io
import os
import zipfile
from typing import BinaryIO

import docx
import pptx
import pypdf
from fastapi import HTTPException

from game_logic import sanitize_document_text

# Default upload limit: 10 MB (configurable via MAX_UPLOAD_SIZE_BYTES)
DEFAULT_MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def get_max_upload_size_bytes() -> int:
    """Retrieve maximum upload size from environment or use default."""
    env_val = os.getenv("MAX_UPLOAD_SIZE_BYTES")
    if env_val:
        try:
            parsed = int(env_val.strip())
            if parsed > 0:
                return parsed
        except ValueError:
            pass
    return DEFAULT_MAX_UPLOAD_SIZE_BYTES


class DocumentParsingError(HTTPException):
    """HTTP 400 exception with a specific document parsing failure message."""

    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


class FileTooLargeError(HTTPException):
    """HTTP 413 exception for files exceeding the allowed size."""

    def __init__(self, detail: str):
        super().__init__(status_code=413, detail=detail)


def _validate_file_size(content: bytes, max_bytes: int, filename: str) -> None:
    """Validate that file content is non-empty and within size limit."""
    if not content or len(content) == 0:
        raise DocumentParsingError(f"Uploaded file '{filename}' is empty.")
    if len(content) > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        raise FileTooLargeError(
            f"File '{filename}' exceeds maximum allowed size of {max_mb:.1f} MB."
        )


def _extract_pdf(stream: BinaryIO, filename: str) -> str:
    """Extract text from a PDF file using pypdf in document page order."""
    stream.seek(0)
    magic = stream.read(4)
    if magic != b"%PDF":
        raise DocumentParsingError(
            f"File '{filename}' does not appear to be a valid PDF (invalid header)."
        )

    stream.seek(0)
    try:
        reader = pypdf.PdfReader(stream)
        if len(reader.pages) == 0:
            raise DocumentParsingError(f"PDF file '{filename}' has no pages.")

        page_texts: list[str] = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            cleaned = text.strip()
            if cleaned:
                page_texts.append(cleaned)

        full_text = "\n\n".join(page_texts).strip()
        if not full_text:
            raise DocumentParsingError(
                f"PDF file '{filename}' contains no readable or extractable text."
            )
        return full_text
    except DocumentParsingError:
        raise
    except Exception as exc:
        raise DocumentParsingError(
            f"Failed to parse PDF file '{filename}': {exc}"
        ) from exc


def _extract_docx(stream: BinaryIO, filename: str) -> str:
    """Extract text from a DOCX file using python-docx in document order."""
    stream.seek(0)
    # Validate ZIP archive header
    magic = stream.read(4)
    if magic != b"PK\x03\x04":
        raise DocumentParsingError(
            f"File '{filename}' does not appear to be a valid DOCX file (invalid header)."
        )

    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as zf:
            if "word/document.xml" not in zf.namelist():
                raise DocumentParsingError(
                    f"File '{filename}' is not a valid DOCX document (missing document structure)."
                )
    except DocumentParsingError:
        raise
    except Exception as exc:
        raise DocumentParsingError(
            f"File '{filename}' is corrupted or not a valid DOCX archive: {exc}"
        ) from exc

    stream.seek(0)
    try:
        doc = docx.Document(stream)
        parts: list[str] = []

        # Extract paragraph text
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                parts.append(text)

        # Extract table text preserving row/cell order
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    parts.append(" | ".join(row_texts))

        full_text = "\n\n".join(parts).strip()
        if not full_text:
            raise DocumentParsingError(
                f"DOCX file '{filename}' contains no readable text."
            )
        return full_text
    except DocumentParsingError:
        raise
    except Exception as exc:
        raise DocumentParsingError(
            f"Failed to extract text from DOCX file '{filename}': {exc}"
        ) from exc


def _extract_pptx(stream: BinaryIO, filename: str) -> str:
    """Extract text from a PPTX file using python-pptx in slide/shape order."""
    stream.seek(0)
    magic = stream.read(4)
    if magic != b"PK\x03\x04":
        raise DocumentParsingError(
            f"File '{filename}' does not appear to be a valid PPTX file (invalid header)."
        )

    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as zf:
            if "ppt/presentation.xml" not in zf.namelist():
                raise DocumentParsingError(
                    f"File '{filename}' is not a valid PPTX presentation (missing presentation structure)."
                )
    except DocumentParsingError:
        raise
    except Exception as exc:
        raise DocumentParsingError(
            f"File '{filename}' is corrupted or not a valid PPTX archive: {exc}"
        ) from exc

    stream.seek(0)
    try:
        prs = pptx.Presentation(stream)
        slide_texts: list[str] = []

        for slide_num, slide in enumerate(prs.slides, start=1):
            shape_texts: list[str] = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if text:
                            shape_texts.append(text)
                elif shape.has_table:
                    for row in shape.table.rows:
                        row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_texts:
                            shape_texts.append(" | ".join(row_texts))
            if shape_texts:
                slide_texts.append(f"[Slide {slide_num}]\n" + "\n".join(shape_texts))

        full_text = "\n\n".join(slide_texts).strip()
        if not full_text:
            raise DocumentParsingError(
                f"PPTX file '{filename}' contains no readable text."
            )
        return full_text
    except DocumentParsingError:
        raise
    except Exception as exc:
        raise DocumentParsingError(
            f"Failed to extract text from PPTX file '{filename}': {exc}"
        ) from exc


def _extract_txt(content: bytes, filename: str) -> str:
    """Extract text from raw text bytes, handling common encodings and binary detection."""
    # Check for excessive binary null bytes
    if b"\x00" in content[:1024]:
        raise DocumentParsingError(
            f"File '{filename}' appears to be a binary file, not a valid plain text document."
        )

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            cleaned = text.strip().lstrip("\ufeff").strip()
            if not cleaned:
                raise DocumentParsingError(
                    f"Text file '{filename}' is empty or contains only whitespace."
                )
            return cleaned
        except UnicodeDecodeError:
            continue

    raise DocumentParsingError(
        f"Unable to decode text file '{filename}'. Please provide UTF-8 encoded text."
    )


def extract_text_from_file(
    content: bytes,
    filename: str,
    max_bytes: int | None = None,
) -> str:
    """
    Main extraction entrypoint. Validates file extension, size, format headers,
    and extracts text safely in document order.
    """
    if max_bytes is None:
        max_bytes = get_max_upload_size_bytes()

    _validate_file_size(content, max_bytes, filename)

    lower_name = filename.lower()
    stream = io.BytesIO(content)

    if lower_name.endswith(".pdf"):
        raw_text = _extract_pdf(stream, filename)
    elif lower_name.endswith(".docx"):
        raw_text = _extract_docx(stream, filename)
    elif lower_name.endswith(".pptx"):
        raw_text = _extract_pptx(stream, filename)
    elif lower_name.endswith(".txt"):
        raw_text = _extract_txt(content, filename)
    else:
        raise DocumentParsingError(
            f"Unsupported file format for '{filename}'. Supported formats are: .pdf, .docx, .pptx, .txt"
        )

    try:
        return sanitize_document_text(raw_text)
    except ValueError as exc:
        raise DocumentParsingError(str(exc)) from exc
