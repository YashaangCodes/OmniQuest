"""
Unit tests for backend/document_parser.py.
"""

import io
import pytest
import docx
import pptx
from pypdf import PdfWriter
from fastapi import HTTPException

from document_parser import (
    extract_text_from_file,
    DocumentParsingError,
    FileTooLargeError,
)


def _make_pdf(text_pages: list[str]) -> bytes:
    """Create a minimal valid PDF in memory with text."""
    # Since pypdf is primarily a reader/writer rather than a layout engine,
    # we can construct a basic valid PDF with text streams.
    buffer = io.BytesIO()
    # Minimal valid PDF with text in a stream
    content = b"%PDF-1.4\n"
    content += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    content += b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    content += b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    
    stream_data = f"BT /F1 12 Tf 72 712 Td ({text_pages[0]}) Tj ET".encode("latin-1")
    content += f"4 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1") + stream_data + b"\nendstream\nendobj\n"
    content += b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    content += b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n0000000350 00000 n \n"
    content += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n435\n%%EOF\n"
    return content


def _make_docx(paragraphs: list[str]) -> bytes:
    """Create a valid DOCX in memory."""
    doc = docx.Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    # Add a table as well
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "TableKey"
    table.rows[0].cells[1].text = "TableValue"
    
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _make_pptx(slide_texts: list[list[str]]) -> bytes:
    """Create a valid PPTX in memory."""
    prs = pptx.Presentation()
    blank_layout = prs.slide_layouts[6]  # Blank slide
    for texts in slide_texts:
        slide = prs.slides.add_slide(blank_layout)
        tx_box = slide.shapes.add_textbox(100, 100, 400, 200)
        tf = tx_box.text_frame
        for idx, text in enumerate(texts):
            if idx == 0:
                tf.text = text
            else:
                p = tf.add_paragraph()
                p.text = text
    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()


def test_extract_txt_valid():
    content = "Hello, OmniQuest!\nThis is a test document.".encode("utf-8")
    extracted = extract_text_from_file(content, "test.txt")
    assert "Hello, OmniQuest!" in extracted
    assert "This is a test document." in extracted


def test_extract_txt_utf8_sig():
    content = "BOM text content".encode("utf-8-sig")
    extracted = extract_text_from_file(content, "bom.txt")
    assert extracted == "BOM text content"


def test_extract_txt_rejects_binary():
    content = b"Some text\x00\x00\x01\x02binary junk"
    with pytest.raises(DocumentParsingError, match="binary file"):
        extract_text_from_file(content, "junk.txt")


def test_extract_docx_valid():
    docx_bytes = _make_docx(["First paragraph.", "Second paragraph."])
    extracted = extract_text_from_file(docx_bytes, "notes.docx")
    assert "First paragraph." in extracted
    assert "Second paragraph." in extracted
    assert "TableKey | TableValue" in extracted


def test_extract_pptx_valid():
    pptx_bytes = _make_pptx([["Slide 1 Title", "Slide 1 Bullet"], ["Slide 2 Content"]])
    extracted = extract_text_from_file(pptx_bytes, "presentation.pptx")
    assert "[Slide 1]" in extracted
    assert "Slide 1 Title" in extracted
    assert "Slide 1 Bullet" in extracted
    assert "[Slide 2]" in extracted
    assert "Slide 2 Content" in extracted


def test_extract_pdf_valid():
    pdf_bytes = _make_pdf(["Hello from PDF content"])
    extracted = extract_text_from_file(pdf_bytes, "doc.pdf")
    assert "Hello from PDF content" in extracted


def test_empty_file_rejected():
    with pytest.raises(DocumentParsingError, match="is empty"):
        extract_text_from_file(b"", "empty.txt")


def test_file_too_large():
    content = b"a" * 100
    with pytest.raises(FileTooLargeError, match="exceeds maximum allowed size"):
        extract_text_from_file(content, "big.txt", max_bytes=50)


def test_unsupported_format():
    with pytest.raises(DocumentParsingError, match="Unsupported file format"):
        extract_text_from_file(b"some content", "data.xyz")


def test_corrupted_pdf():
    corrupted = b"%PDF-corrupted-header-garbage"
    with pytest.raises(DocumentParsingError):
        extract_text_from_file(corrupted, "broken.pdf")


def test_fake_pdf():
    fake = b"Not a pdf at all"
    with pytest.raises(DocumentParsingError, match="invalid header"):
        extract_text_from_file(fake, "fake.pdf")


def test_corrupted_docx():
    fake = b"PK\x03\x04corrupted-zip-data"
    with pytest.raises(DocumentParsingError):
        extract_text_from_file(fake, "broken.docx")


def test_corrupted_pptx():
    fake = b"PK\x03\x04corrupted-pptx-data"
    with pytest.raises(DocumentParsingError):
        extract_text_from_file(fake, "broken.pptx")
