"""
Integration tests for FastAPI endpoints in backend/main.py.
"""

import io
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from main import app, sessions
from game_logic import GauntletPayload, Question, expected_tier_for_stage
from gemini_service import TopicRejectedError, InsufficientMaterialError
from tests.test_document_parser import _make_docx, _make_pdf, _make_pptx

client = TestClient(app)


# ---------------------------------------------------------------------------
# /upload-document Tests
# ---------------------------------------------------------------------------


def test_upload_document_txt_success():
    content = b"OmniQuest is an adaptive learning game."
    response = client.post(
        "/upload-document",
        files={"file": ("notes.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "notes.txt"
    assert "OmniQuest is an adaptive learning game." in data["text"]
    assert data["word_count"] == 6
    assert data["character_count"] > 0


def test_upload_document_docx_success():
    docx_bytes = _make_docx(["Paragraph 1", "Paragraph 2"])
    response = client.post(
        "/upload-document",
        files={"file": ("doc.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Paragraph 1" in data["text"]
    assert "Paragraph 2" in data["text"]


def test_upload_document_pptx_success():
    pptx_bytes = _make_pptx([["Slide One Header"]])
    response = client.post(
        "/upload-document",
        files={"file": ("slides.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Slide One Header" in data["text"]


def test_upload_document_pdf_success():
    pdf_bytes = _make_pdf(["PDF Document Content"])
    response = client.post(
        "/upload-document",
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "PDF Document Content" in data["text"]


def test_upload_document_empty_rejected():
    response = client.post(
        "/upload-document",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert "is empty" in response.json()["detail"]


def test_upload_document_unsupported_rejected():
    response = client.post(
        "/upload-document",
        files={"file": ("app.exe", b"binarycontent", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_upload_document_corrupted_pdf_rejected():
    response = client.post(
        "/upload-document",
        files={"file": ("broken.pdf", b"%PDF-corrupt", "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_document_size_limit():
    with patch("document_parser.get_max_upload_size_bytes", return_value=50):
        response = client.post(
            "/upload-document",
            files={"file": ("large.txt", b"a" * 100, "text/plain")},
        )
        assert response.status_code == 413
        assert "exceeds maximum allowed size" in response.json()["detail"]


# ---------------------------------------------------------------------------
# /generate-game Tests
# ---------------------------------------------------------------------------


def _dummy_payload_for_mock(topic: str, count: int) -> GauntletPayload:
    questions = []
    for s in range(1, count + 1):
        tier = expected_tier_for_stage(s, count)
        opts = [f"A{s}", f"B{s}", f"C{s}", f"D{s}"]
        questions.append(
            Question(
                stage=s,
                tier=tier,
                question=f"Q{s}?",
                options=opts,
                correct_answer=opts[0],
                explanation=f"Exp{s}",
            )
        )
    return GauntletPayload(is_valid=True, topic=topic, gauntlet=questions)


def test_generate_game_default_20_questions():
    mock_payload = _dummy_payload_for_mock("Biology", 20)
    with patch("main.generate_gauntlet_with_gemini", return_value=mock_payload):
        resp = client.post("/generate-game", json={"topic": "Biology"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_count"] == 20
        assert len(data["gauntlet"]) == 20
        assert data["tier_checkpoints"] == [5, 10, 15]
        assert data["tier_target_ip"] == 300
        # Critical security check: answers and explanations must NOT be in public gauntlet!
        for q in data["gauntlet"]:
            assert "correct_answer" not in q
            assert "explanation" not in q


@pytest.mark.parametrize("count,checkpoints", [(5, []), (10, [5]), (15, [5, 10]), (20, [5, 10, 15])])
def test_generate_game_dynamic_counts(count, checkpoints):
    mock_payload = _dummy_payload_for_mock("Science", count)
    with patch("main.generate_gauntlet_with_gemini", return_value=mock_payload):
        resp = client.post("/generate-game", json={"topic": "Science", "question_count": count})
        assert resp.status_code == 200
        data = resp.json()
        assert data["question_count"] == count
        assert len(data["gauntlet"]) == count
        assert data["tier_checkpoints"] == checkpoints


def test_generate_game_invalid_counts():
    for invalid in (1, 4, 7, 12, 19, 21, 25):
        resp = client.post("/generate-game", json={"topic": "Science", "question_count": invalid})
        assert resp.status_code == 422  # Pydantic validation error


def test_generate_game_topic_rejected():
    with patch(
        "main.generate_gauntlet_with_gemini",
        side_effect=TopicRejectedError("Topic is uninterpretable gibberish."),
    ):
        resp = client.post("/generate-game", json={"topic": "asdfghjkl123", "question_count": 5})
        assert resp.status_code == 400
        assert "uninterpretable gibberish" in resp.json()["detail"]


def test_generate_game_strict_mode_insufficient_material_no_fallback():
    """Verify that Strict Material Only NEVER silently loads fallback."""
    with patch(
        "main.generate_gauntlet_with_gemini",
        side_effect=InsufficientMaterialError("Not enough facts in text for 10 questions."),
    ):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "History",
                "question_count": 10,
                "source_text": "Brief history text.",
                "generation_mode": "Strict Material Only",
            },
        )
        assert resp.status_code == 400
        assert "Not enough facts" in resp.json()["detail"]


def test_generate_game_fallback_slicing():
    """Verify fallback activates for AI Enhanced / standard topic when Gemini fails."""
    with patch(
        "main.generate_gauntlet_with_gemini",
        side_effect=RuntimeError("API quota exceeded"),
    ):
        resp = client.post(
            "/generate-game",
            json={"topic": "Technology", "question_count": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_fallback"] is True
        assert data["question_count"] == 10
        assert len(data["gauntlet"]) == 10
        assert data["tier_checkpoints"] == [5]


# ---------------------------------------------------------------------------
# /submit-answer Tests
# ---------------------------------------------------------------------------


def test_submit_answer_full_flow():
    # Generate a 5-question game session via fallback or mock
    mock_payload = _dummy_payload_for_mock("Math", 5)
    with patch("main.generate_gauntlet_with_gemini", return_value=mock_payload):
        gen_resp = client.post("/generate-game", json={"topic": "Math", "question_count": 5})
        assert gen_resp.status_code == 200
        session_id = gen_resp.json()["session_id"]

    # Verify session is stored server-side
    assert session_id in sessions
    stored_questions = sessions[session_id]["gauntlet"]
    correct_opt_1 = stored_questions[0]["correct_answer"]
    wrong_opt_1 = [o for o in stored_questions[0]["options"] if o != correct_opt_1][0]

    # Submit correct answer
    ans_resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": correct_opt_1,
        },
    )
    assert ans_resp.status_code == 200
    res_data = ans_resp.json()
    assert res_data["is_correct"] is True
    assert res_data["correct_answer"] == correct_opt_1
    assert "Exp1" in res_data["explanation"]

    # Submit incorrect answer on stage 2
    correct_opt_2 = stored_questions[1]["correct_answer"]
    wrong_opt_2 = [o for o in stored_questions[1]["options"] if o != correct_opt_2][0]
    ans_resp_wrong = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 2,
            "selected_option": wrong_opt_2,
        },
    )
    assert ans_resp_wrong.status_code == 200
    assert ans_resp_wrong.json()["is_correct"] is False

    # Duplicate submission on stage 1 returns original cached response
    dup_resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": wrong_opt_1,
        },
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["is_correct"] is True

    # Out of bounds stage (> 5 for a 5-question game)
    oob_resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 6,
            "selected_option": "A",
        },
    )
    assert oob_resp.status_code == 400
    assert "Invalid stage_number" in oob_resp.json()["detail"]

    # Unknown session_id
    unknown_resp = client.post(
        "/submit-answer",
        json={
            "session_id": "non-existent-session-id",
            "stage_number": 1,
            "selected_option": "A",
        },
    )
    assert unknown_resp.status_code == 404
