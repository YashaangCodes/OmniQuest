"""
Unit and integration tests for document sanitization and the v1.0 RAG pipeline.

Covers all 9 required document validation tests including realistic Photosynthesis DOCX samples,
newline preservation, control character removal, size ceilings, and prompt structure verification.
"""

import io
from unittest.mock import MagicMock, patch
import pytest
import docx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from game_logic import (
    DEFAULT_MAX_DOCUMENT_LENGTH,
    GenerateGameRequest,
    sanitize_document_text,
    sanitize_input_text,
)
from gemini_service import (
    build_generation_prompt,
    generate_gauntlet_with_gemini,
    validate_context_budget,
)
from document_parser import extract_text_from_file

client = TestClient(app)

PHOTOSYNTHESIS_SAMPLE = """Photosynthesis is the biological process by which autotrophic organisms convert light energy into chemical energy stored in glucose molecules.

The process takes place within the chloroplasts of plant cells and consists of two primary stages:

Stage 1: The Light-Dependent Reactions
These reactions occur across the thylakoid membranes inside the chloroplast. Chlorophyll pigments absorb photons, exciting electrons that move through an electron transport chain. Water molecules are split through photolysis into oxygen, protons, and electrons. This stage produces ATP and NADPH, releasing diatomic oxygen gas as a byproduct.

Stage 2: The Light-Independent Reactions (Calvin Cycle)
Taking place in the stroma of the chloroplast, this stage uses the chemical energy from ATP and NADPH to fix atmospheric carbon dioxide into 3-phosphoglycerate (3-PGA), catalyzed by the enzyme RuBisCO. Through a series of reduction and regeneration steps, glyceraldehyde-3-phosphate (G3P) is synthesized and ultimately converted into glucose.

Overall Net Equation:
6 CO2 + 6 H2O + Light Energy -> C6H12O6 + 6 O2

Environmental factors such as light intensity, carbon dioxide concentration, and ambient temperature significantly affect the rate of photosynthetic activity."""


def _create_photosynthesis_docx() -> bytes:
    """Generate a realistic multi-paragraph Photosynthesis DOCX document."""
    doc = docx.Document()
    doc.add_heading("Photosynthesis Overview", level=1)
    for paragraph in PHOTOSYNTHESIS_SAMPLE.split("\n\n"):
        doc.add_paragraph(paragraph)
    
    # Add a table summarizing stages
    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Stage"
    hdr_cells[1].text = "Location"
    hdr_cells[2].text = "Key Products"

    row1 = table.add_row().cells
    row1[0].text = "Light-Dependent"
    row1[1].text = "Thylakoid Membrane"
    row1[2].text = "ATP, NADPH, O2"

    row2 = table.add_row().cells
    row2[0].text = "Calvin Cycle"
    row2[1].text = "Stroma"
    row2[2].text = "G3P, Glucose"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Test 1: A document shorter than 50 characters
# ---------------------------------------------------------------------------

def test_document_shorter_than_50_chars():
    short_doc = "Photosynthesis creates plant energy."
    assert len(short_doc) < 50
    # Dedicated document sanitizer accepts it
    sanitized = sanitize_document_text(short_doc)
    assert sanitized == short_doc

    # GenerateGameRequest accepts it without triggering short metadata constraints
    req = GenerateGameRequest(
        topic="Photosynthesis",
        source_text=short_doc,
        generation_mode="Strict Material Only",
    )
    assert req.source_text == short_doc


# ---------------------------------------------------------------------------
# Test 2: A document longer than 50 characters
# ---------------------------------------------------------------------------

def test_document_longer_than_50_chars():
    long_doc = (
        "Chlorophyll a and chlorophyll b absorb blue and red wavelengths of light "
        "while reflecting green light, giving plant leaves their characteristic appearance."
    )
    assert len(long_doc) > 50
    sanitized = sanitize_document_text(long_doc)
    assert sanitized == long_doc

    # Metadata sanitizer WOULD reject this due to 50-char limit
    with pytest.raises(ValueError, match="must not exceed 50 characters"):
        sanitize_input_text(long_doc, "topic")

    # Document sanitizer accepts it seamlessly
    req = GenerateGameRequest(topic="Plant Biology", source_text=long_doc)
    assert req.source_text == long_doc


# ---------------------------------------------------------------------------
# Test 3: A document containing multiple paragraphs
# ---------------------------------------------------------------------------

def test_document_multiple_paragraphs_preserves_breaks():
    doc_text = "Paragraph 1: Light reactions.\n\nParagraph 2: Calvin cycle.\n\nParagraph 3: Energy storage."
    sanitized = sanitize_document_text(doc_text)
    # Paragraph breaks are intact
    assert "\n\n" in sanitized
    paragraphs = sanitized.split("\n\n")
    assert len(paragraphs) == 3
    assert paragraphs[0] == "Paragraph 1: Light reactions."
    assert paragraphs[1] == "Paragraph 2: Calvin cycle."
    assert paragraphs[2] == "Paragraph 3: Energy storage."

    # Compare with metadata sanitizer which would destroy paragraphs into a single line
    flattened = sanitize_input_text("Para 1.\n\nPara 2.", "topic")
    assert "\n" not in flattened
    assert flattened == "Para 1. Para 2."


# ---------------------------------------------------------------------------
# Test 4: Windows-style CRLF and Unix-style LF line endings
# ---------------------------------------------------------------------------

def test_document_windows_and_unix_line_endings_normalized():
    mixed_doc = "Header Line\r\n\r\nParagraph with CRLF.\r\nNext line.\nUnix paragraph.\rMac old line."
    sanitized = sanitize_document_text(mixed_doc)
    # All CRLF (\r\n) and CR (\r) must be normalized to LF (\n)
    assert "\r\n" not in sanitized
    assert "\r" not in sanitized
    assert "Header Line\n\nParagraph with CRLF.\nNext line.\nUnix paragraph.\nMac old line." == sanitized


# ---------------------------------------------------------------------------
# Test 5: Tabs and blank lines preserved
# ---------------------------------------------------------------------------

def test_document_tabs_and_blank_lines_preserved():
    doc_with_tabs = "Section 1:\n\t- Indented concept A\n\t- Indented concept B\n\n\n\nSection 2:\n\t- Concept C"
    sanitized = sanitize_document_text(doc_with_tabs)
    # Tabs are strictly preserved
    assert "\t- Indented concept A" in sanitized
    assert "\t- Indented concept B" in sanitized
    # Excessive 4 newlines are collapsed to standard paragraph break (2 newlines)
    assert "\n\nSection 2:" in sanitized
    assert "\n\n\n" not in sanitized


# ---------------------------------------------------------------------------
# Test 6: Null bytes and unwanted control characters stripped
# ---------------------------------------------------------------------------

def test_document_null_bytes_and_unwanted_control_characters():
    dirty_doc = "Clean title\x00\x01\x02\x07\x08 with nulls.\n\tPreserved tab\x0b\x0c and formfeed.\ufeff\x7fEnd."
    sanitized = sanitize_document_text(dirty_doc)
    # Null bytes and control codes removed
    assert "\x00" not in sanitized
    assert "\x01" not in sanitized
    assert "\x07" not in sanitized
    assert "\x08" not in sanitized
    assert "\x0b" not in sanitized
    assert "\x0c" not in sanitized
    assert "\x7f" not in sanitized
    assert "\ufeff" not in sanitized
    # Meaningful whitespace preserved
    assert "\n" in sanitized
    assert "\t" in sanitized
    assert "Clean title with nulls.\n\tPreserved tab and formfeed.End." == sanitized


# ---------------------------------------------------------------------------
# Test 7: Empty or whitespace-only documents rejected
# ---------------------------------------------------------------------------

def test_empty_or_whitespace_document_rejected():
    with pytest.raises(ValueError, match="empty or whitespace-only"):
        sanitize_document_text("")

    with pytest.raises(ValueError, match="empty or whitespace-only"):
        sanitize_document_text("   \n\t\n   ")

    # Document with only punctuation/symbols is rejected
    with pytest.raises(ValueError, match="at least one alphanumeric character"):
        sanitize_document_text("..... --- !!! ??? &&&")

    # GenerateGameRequest rejects empty string
    with pytest.raises(ValidationError):
        GenerateGameRequest(topic="Physics", source_text="   \n  ")


# ---------------------------------------------------------------------------
# Test 8: Document exceeding configured maximum
# ---------------------------------------------------------------------------

def test_document_exceeding_maximum_limit():
    # 1. Custom ceiling
    with pytest.raises(ValueError, match="exceeds maximum allowed size of 100 characters"):
        sanitize_document_text("a" * 150, max_length=100)

    # 2. Default ceiling (100,000 characters)
    oversized = "x" * (DEFAULT_MAX_DOCUMENT_LENGTH + 1)
    with pytest.raises(ValueError, match="exceeds maximum allowed size of 100,000 characters"):
        sanitize_document_text(oversized)

    # 3. Context budget check
    with pytest.raises(ValueError, match="exceeds the practical context budget"):
        validate_context_budget("w" * 100_001)


# ---------------------------------------------------------------------------
# Test 9: Verification that Gemini prompt retains paragraph structure
# ---------------------------------------------------------------------------

def test_gemini_prompt_retains_meaningful_paragraph_structure():
    docx_bytes = _create_photosynthesis_docx()
    # 1. Extract via document_parser
    extracted = extract_text_from_file(docx_bytes, "photosynthesis.docx")
    assert "\n\n" in extracted
    assert "Stage 1: The Light-Dependent Reactions" in extracted
    assert "Stage 2: The Light-Independent Reactions" in extracted

    # 2. Build GenerateGameRequest
    req = GenerateGameRequest(
        topic="Photosynthesis",
        target_level="High School",
        question_count=10,
        source_text=extracted,
        generation_mode="Strict Material Only",
    )

    # 3. Build generation prompt
    prompt = build_generation_prompt(req)

    # 4. Verify prompt contents
    assert "<untrusted_user_input>" in prompt
    assert "</untrusted_user_input>" in prompt
    assert "STRICT MATERIAL ONLY RULES:" in prompt
    # Structure must be preserved inside untrusted_user_input without flattening
    assert "\n\nStage 1: The Light-Dependent Reactions" in prompt
    assert "\n\nStage 2: The Light-Independent Reactions (Calvin Cycle)" in prompt
    assert "Overall Net Equation:" in prompt
    assert "Light-Dependent | Thylakoid Membrane | ATP, NADPH, O2" in prompt


# ---------------------------------------------------------------------------
# Test 10: Full RAG API pipeline with Photosynthesis document
# ---------------------------------------------------------------------------

def test_rag_api_pipeline_photosynthesis_integration():
    docx_bytes = _create_photosynthesis_docx()
    # Step 1: Upload document to /upload-document
    upload_resp = client.post(
        "/upload-document",
        files={"file": ("photosynthesis.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    extracted_text = upload_data["text"]

    # Verify extracted text is structured and multi-paragraph
    assert "\n\n" in extracted_text
    assert upload_data["character_count"] > 200
    assert upload_data["word_count"] > 40

    # Step 2: Call /generate-game with the extracted text in Strict Material Only mode
    mock_payload = MagicMock()
    mock_payload.is_valid = True
    mock_payload.topic = "Photosynthesis"
    mock_payload.gauntlet = []

    with patch("main.generate_gauntlet_with_gemini") as mock_gemini:
        # Verify the mock receives request with preserved paragraph formatting
        def mock_impl(req):
            assert "\n\n" in req.source_text
            assert "Stage 1: The Light-Dependent Reactions" in req.source_text
            assert req.generation_mode == "Strict Material Only"
            assert req.question_count == 10
            # Return dummy valid gauntlet
            from game_logic import Question, GauntletPayload
            q_list = []
            for s in range(1, 11):
                tier = 1 if s <= 5 else 2
                q_list.append(
                    Question(
                        stage=s,
                        tier=tier,
                        question=f"Q{s} about photosynthesis?",
                        options=[f"A{s}", f"B{s}", f"C{s}", f"D{s}"],
                        correct_answer=f"A{s}",
                        explanation=f"Exp{s}",
                    )
                )
            return GauntletPayload(is_valid=True, topic="Photosynthesis", gauntlet=q_list)

        mock_gemini.side_effect = mock_impl

        gen_resp = client.post(
            "/generate-game",
            json={
                "topic": "Photosynthesis",
                "target_level": "Undergraduate",
                "question_count": 10,
                "source_text": extracted_text,
                "generation_mode": "Strict Material Only",
            },
        )
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        assert gen_data["topic"] == "Photosynthesis"
        assert gen_data["question_count"] == 10
        assert len(gen_data["gauntlet"]) == 10
