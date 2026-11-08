"""
Automated test suite for OmniQuest v1.0 Phase 1: Document & Topic Logic Refinement.

Covers the complete 4-way input matrix and rules:
1. Provided Topic + No Document -> Generate using topic.
2. Empty Topic + Uploaded Document -> Automatically identify primary topic.
3. Provided Topic + Uploaded Document -> Validate topic-document relevance (including subtopics).
4. Empty Topic + No Document -> Reject request with clear error.
5. Strict Material Only & AI Enhanced modes with document-only input.
6. Ambiguous document / ambiguous topic handling.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from game_logic import (
    GauntletPayload,
    GenerateGameRequest,
    Question,
)
from gemini_service import (
    AmbiguousDocumentError,
    InsufficientMaterialError,
    TopicDocumentMismatchError,
    TopicIdentificationResult,
    TopicRelevanceResult,
    identify_document_topic,
    validate_topic_document_relevance,
)

client = TestClient(app)

SAMPLE_MARATHA_DOC = """The Maratha Empire, also known as the Maratha Confederacy, was an early modern Indian confederacy that dominated much of the Indian subcontinent in the 17th and 18th centuries.

Chhatrapati Shivaji Maharaj was an Indian ruler and a member of the Bhonsle Maratha clan. Shivaji carved out an enclave from the declining Adilshahi sultanate of Bijapur that formed the genesis of the Maratha Empire. In 1674, he was formally crowned as the Chhatrapati of his realm at Raigad.

Under Shivaji Maharaj and subsequent Peshwas, the Marathas established an efficient administrative and military system characterized by light cavalry and guerrilla warfare tactics known as Ganimi Kawa."""

SAMPLE_PHOTOSYNTHESIS_DOC = """Photosynthesis is a biological process used by many cellular organisms to convert light energy into chemical energy. This chemical energy is stored in carbohydrate molecules, such as sugars and starches, which are synthesized from carbon dioxide and water.

Oxygenic photosynthesis is the most common form, performed by plants, algae, and cyanobacteria. During oxygenic photosynthesis, light energy transfers electrons from water (H2O) to carbon dioxide (CO2), producing carbohydrates and releasing oxygen (O2) as a byproduct. The net chemical equation is:
6 CO2 + 6 H2O + photons -> C6H12O6 + 6 O2."""


def _make_dummy_questions(count: int, topic: str = "Test Topic") -> list[Question]:
    return [
        Question(
            stage=i,
            tier=1,
            question=f"Question {i} about {topic}?",
            options=[f"Correct {i}", f"Wrong A {i}", f"Wrong B {i}", f"Wrong C {i}"],
            correct_answer=f"Correct {i}",
            explanation=f"Explanation for question {i}.",
        )
        for i in range(1, count + 1)
    ]


# ---------------------------------------------------------------------------
# 1. Pydantic Model-Level Input Validation
# ---------------------------------------------------------------------------


def test_empty_topic_and_no_document_rejected_in_schema():
    """Verify that GenerateGameRequest rejects empty topic and missing document."""
    # Both None
    with pytest.raises(ValidationError) as exc_info:
        GenerateGameRequest()
    assert "Either a topic or an uploaded document must be provided." in str(exc_info.value)

    # Empty string topic and None document
    with pytest.raises(ValidationError) as exc_info:
        GenerateGameRequest(topic="", source_text=None)
    assert "Either a topic or an uploaded document must be provided." in str(exc_info.value)

    # Whitespace-only topic and None document
    with pytest.raises(ValidationError) as exc_info:
        GenerateGameRequest(topic="   ", source_text=None)
    assert "Either a topic or an uploaded document must be provided." in str(exc_info.value)


def test_document_only_allowed_in_schema():
    """Verify that GenerateGameRequest allows empty or None topic when source_text is provided."""
    req_none = GenerateGameRequest(topic=None, source_text=SAMPLE_MARATHA_DOC)
    assert req_none.topic is None
    assert req_none.source_text is not None

    req_empty = GenerateGameRequest(topic="", source_text=SAMPLE_MARATHA_DOC)
    assert req_empty.topic is None
    assert req_empty.source_text is not None

    req_whitespace = GenerateGameRequest(topic="   ", source_text=SAMPLE_MARATHA_DOC)
    assert req_whitespace.topic is None
    assert req_whitespace.source_text is not None


def test_topic_only_allowed_in_schema():
    """Verify that GenerateGameRequest allows topic when source_text is omitted."""
    req = GenerateGameRequest(topic="Photosynthesis")
    assert req.topic == "Photosynthesis"
    assert req.source_text is None


# ---------------------------------------------------------------------------
# 2. Endpoint Input Rule Matrix (/generate-game)
# ---------------------------------------------------------------------------


def test_endpoint_rejects_empty_topic_and_no_document():
    """POST /generate-game rejects requests with neither topic nor document."""
    resp = client.post("/generate-game", json={"question_count": 5})
    assert resp.status_code in (400, 422)
    assert "Either a topic or an uploaded document must be provided." in resp.text


def test_endpoint_topic_only_succeeds():
    """POST /generate-game succeeds when only topic is provided."""
    mock_payload = GauntletPayload(
        is_valid=True,
        topic="Photosynthesis",
        gauntlet=_make_dummy_questions(5, "Photosynthesis"),
    )
    with patch("main.generate_gauntlet_with_gemini", return_value=mock_payload):
        resp = client.post("/generate-game", json={"topic": "Photosynthesis", "question_count": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Photosynthesis"
        assert len(data["gauntlet"]) == 5


def test_endpoint_document_only_auto_identifies_topic():
    """POST /generate-game with document and empty topic automatically identifies topic."""
    mock_payload = GauntletPayload(
        is_valid=True,
        topic="The Maratha Empire",
        gauntlet=_make_dummy_questions(5, "The Maratha Empire"),
    )
    with (
        patch("main.identify_document_topic", return_value="The Maratha Empire") as mock_id,
        patch("main.generate_gauntlet_with_gemini", return_value=mock_payload),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "",
                "source_text": SAMPLE_MARATHA_DOC,
                "question_count": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "The Maratha Empire"
        assert mock_id.called


def test_endpoint_relevant_topic_and_document_succeeds():
    """POST /generate-game with relevant topic and document passes relevance validation."""
    mock_payload = GauntletPayload(
        is_valid=True,
        topic="Maratha Empire",
        gauntlet=_make_dummy_questions(5, "Maratha Empire"),
    )
    with (
        patch("main.validate_topic_document_relevance", return_value=(True, "Direct match")) as mock_rel,
        patch("main.generate_gauntlet_with_gemini", return_value=mock_payload),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "Maratha Empire",
                "source_text": SAMPLE_MARATHA_DOC,
                "question_count": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Maratha Empire"
        assert mock_rel.called


def test_endpoint_related_subtopic_and_document_succeeds():
    """POST /generate-game accepts a relevant subtopic even if wording differs from document title."""
    mock_payload = GauntletPayload(
        is_valid=True,
        topic="Shivaji Maharaj",
        gauntlet=_make_dummy_questions(5, "Shivaji Maharaj"),
    )
    with (
        patch("main.validate_topic_document_relevance", return_value=(True, "Relevant historical figure")) as mock_rel,
        patch("main.generate_gauntlet_with_gemini", return_value=mock_payload),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "Shivaji Maharaj",
                "source_text": SAMPLE_MARATHA_DOC,
                "question_count": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Shivaji Maharaj"
        assert mock_rel.called


def test_endpoint_unrelated_topic_and_document_rejected():
    """POST /generate-game rejects unrelated topic and document with HTTP 400 and clear error."""
    with patch(
        "main.validate_topic_document_relevance",
        side_effect=TopicDocumentMismatchError(
            "The provided topic 'Photosynthesis' is not relevant to the uploaded document: "
            "Photosynthesis is a biological process and is completely unrelated to the Maratha Empire. "
            "Please provide a relevant topic or clear the topic to generate from the document automatically."
        ),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "Photosynthesis",
                "source_text": SAMPLE_MARATHA_DOC,
                "question_count": 5,
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "not relevant" in detail
        assert "Photosynthesis" in detail


def test_endpoint_ambiguous_document_without_topic_rejected():
    """POST /generate-game rejects ambiguous document when no topic is provided."""
    with patch(
        "main.identify_document_topic",
        side_effect=AmbiguousDocumentError(
            "The uploaded document does not contain sufficient clear information to automatically identify a primary topic. "
            "Please enter a topic manually."
        ),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "",
                "source_text": "Random numbers: 12345 67890 111213. Fragmented notes.",
                "question_count": 5,
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "Please enter a topic manually" in detail


# ---------------------------------------------------------------------------
# 3. Direct Unit Tests for identify_document_topic
# ---------------------------------------------------------------------------


def test_identify_document_topic_success_with_gemini_mock():
    """Verify identify_document_topic parses Gemini response and returns clean topic."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.parsed = TopicIdentificationResult(
        is_identifiable=True,
        topic="History of the Maratha Empire",
    )
    mock_client.models.generate_content.return_value = mock_resp

    identified = identify_document_topic(SAMPLE_MARATHA_DOC, client=mock_client)
    assert identified == "History of the Maratha Empire"
    assert mock_client.models.generate_content.called


def test_identify_document_topic_ambiguous_rejected():
    """Verify identify_document_topic raises AmbiguousDocumentError when document is ambiguous."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.parsed = TopicIdentificationResult(
        is_identifiable=False,
        topic="",
        clarification_reason="The text contains disconnected fragments.",
    )
    mock_client.models.generate_content.return_value = mock_resp

    with pytest.raises(AmbiguousDocumentError) as exc_info:
        identify_document_topic("Fragmented text.", client=mock_client)
    assert "disconnected fragments" in str(exc_info.value)


def test_identify_document_topic_heuristic_fallback():
    """Verify offline heuristic identification detects clean heading as topic."""
    doc = "# Photosynthesis in Plants\nPhotosynthesis converts light into energy."
    identified = identify_document_topic(doc, client=None)
    assert identified == "Photosynthesis in Plants"


def test_identify_document_topic_empty_raises_error():
    """Verify empty document text raises AmbiguousDocumentError immediately."""
    with pytest.raises(AmbiguousDocumentError):
        identify_document_topic("   ", client=None)


# ---------------------------------------------------------------------------
# 4. Direct Unit Tests for validate_topic_document_relevance
# ---------------------------------------------------------------------------


def test_validate_relevance_matching_topic():
    """Verify validate_topic_document_relevance passes for matching topic."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.parsed = TopicRelevanceResult(
        is_relevant=True,
        is_ambiguous=False,
        reason="Direct match with document subject.",
    )
    mock_client.models.generate_content.return_value = mock_resp

    is_rel, reason = validate_topic_document_relevance(
        "Maratha Empire", SAMPLE_MARATHA_DOC, client=mock_client
    )
    assert is_rel is True
    assert "Direct match" in reason


def test_validate_relevance_subtopic():
    """Verify validate_topic_document_relevance passes for related subtopic."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.parsed = TopicRelevanceResult(
        is_relevant=True,
        is_ambiguous=False,
        reason="Shivaji Maharaj is the founder of the Maratha Empire described in the text.",
    )
    mock_client.models.generate_content.return_value = mock_resp

    is_rel, reason = validate_topic_document_relevance(
        "Shivaji Maharaj", SAMPLE_MARATHA_DOC, client=mock_client
    )
    assert is_rel is True
    assert "Shivaji Maharaj" in reason


def test_validate_relevance_unrelated_topic_rejected():
    """Verify validate_topic_document_relevance raises TopicDocumentMismatchError for unrelated topic."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.parsed = TopicRelevanceResult(
        is_relevant=False,
        is_ambiguous=False,
        reason="Photosynthesis is a botanical process unrelated to historical dynasties.",
    )
    mock_client.models.generate_content.return_value = mock_resp

    with pytest.raises(TopicDocumentMismatchError) as exc_info:
        validate_topic_document_relevance(
            "Photosynthesis", SAMPLE_MARATHA_DOC, client=mock_client
        )
    assert "Photosynthesis" in str(exc_info.value)
    assert "not relevant" in str(exc_info.value)


def test_validate_relevance_ambiguous_relationship_rejected():
    """Verify validate_topic_document_relevance raises AmbiguousDocumentError when relationship is ambiguous."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.parsed = TopicRelevanceResult(
        is_relevant=False,
        is_ambiguous=True,
        reason="The document is too fragmented to verify connection to the topic.",
    )
    mock_client.models.generate_content.return_value = mock_resp

    with pytest.raises(AmbiguousDocumentError) as exc_info:
        validate_topic_document_relevance(
            "Science", "Vague notes.", client=mock_client
        )
    assert "ambiguous" in str(exc_info.value)


def test_validate_relevance_heuristic_offline():
    """Verify heuristic offline relevance check accepts matching words and rejects disjoint words."""
    # Relevant: "maratha" is in document
    is_rel, _ = validate_topic_document_relevance(
        "Maratha Empire", SAMPLE_MARATHA_DOC, client=None
    )
    assert is_rel is True

    # Unrelated: "photosynthesis" is NOT in Maratha document
    with pytest.raises(TopicDocumentMismatchError):
        validate_topic_document_relevance(
            "Photosynthesis", SAMPLE_MARATHA_DOC, client=None
        )


# ---------------------------------------------------------------------------
# 5. Generation Modes (Strict Material Only vs AI Enhanced) with Document-Only
# ---------------------------------------------------------------------------


def test_strict_material_only_document_only_success():
    """Verify Strict Material Only generates successfully with document-only input."""
    mock_payload = GauntletPayload(
        is_valid=True,
        topic="Photosynthesis",
        gauntlet=_make_dummy_questions(5, "Photosynthesis"),
    )
    with (
        patch("main.identify_document_topic", return_value="Photosynthesis"),
        patch("main.generate_gauntlet_with_gemini", return_value=mock_payload),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": None,
                "source_text": SAMPLE_PHOTOSYNTHESIS_DOC,
                "question_count": 5,
                "generation_mode": "Strict Material Only",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Photosynthesis"
        assert len(data["gauntlet"]) == 5
        assert data["is_fallback"] is None  # Never fallback in Strict Material Only


def test_strict_material_only_document_only_insufficient_material_fails_cleanly():
    """Verify Strict Material Only never falls back to sample round when material is insufficient."""
    with (
        patch("main.identify_document_topic", return_value="Short Document"),
        patch(
            "main.generate_gauntlet_with_gemini",
            side_effect=InsufficientMaterialError("Document lacks sufficient facts for 20 questions."),
        ),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "",
                "source_text": "One short sentence.",
                "question_count": 20,
                "generation_mode": "Strict Material Only",
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "Document lacks sufficient facts" in detail


def test_ai_enhanced_document_only_success():
    """Verify AI Enhanced generates successfully with document-only input."""
    mock_payload = GauntletPayload(
        is_valid=True,
        topic="Photosynthesis",
        gauntlet=_make_dummy_questions(10, "Photosynthesis"),
    )
    with (
        patch("main.identify_document_topic", return_value="Photosynthesis"),
        patch("main.generate_gauntlet_with_gemini", return_value=mock_payload),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": None,
                "source_text": SAMPLE_PHOTOSYNTHESIS_DOC,
                "question_count": 10,
                "generation_mode": "AI Enhanced",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Photosynthesis"
        assert len(data["gauntlet"]) == 10
