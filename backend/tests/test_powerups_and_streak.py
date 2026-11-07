"""
Comprehensive unit and integration tests for Live Power-Ups (AI Hint, 50/50)
and server-side Streak Multiplier scoring.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app, sessions
from game_logic import (
    BASE_IP_PER_QUESTION,
    GauntletPayload,
    Question,
    STREAK_FIRE_BONUS_IP,
    STREAK_FIRE_THRESHOLD,
)
from gemini_service import (
    build_hint_prompt,
    generate_fallback_hint,
    generate_hint_with_gemini,
)

client = TestClient(app)


def _create_mock_session(topic: str = "Biology", length: int = 5) -> str:
    """Helper to generate a clean mock game session."""
    questions = [
        Question(
            stage=i,
            tier=1 if i <= 5 else 2,
            question=f"Question {i} about {topic}?",
            options=[f"Option {i}A", f"Option {i}B", f"Option {i}C", f"Option {i}D"],
            correct_answer=f"Option {i}A",
            explanation=f"Explanation for question {i}.",
        )
        for i in range(1, length + 1)
    ]
    payload = GauntletPayload(
        is_valid=True,
        topic=topic,
        gauntlet=questions,
    )
    with patch("main.generate_gauntlet_with_gemini", return_value=payload):
        resp = client.post(
            "/generate-game",
            json={"topic": topic, "question_count": length},
        )
        assert resp.status_code == 200
        return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# AI Hint Tests
# ---------------------------------------------------------------------------


def test_use_hint_successful_generation():
    session_id = _create_mock_session(length=5)

    with patch("gemini_service.create_gemini_client") as mock_client_factory:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Look closely at the metabolic pathway."
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client_factory.return_value = mock_gemini

        resp = client.post(
            "/use-hint",
            json={"session_id": session_id, "stage_number": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "hint" in data
        assert data["hint"] == "Look closely at the metabolic pathway."
        # Confirm correct answer and explanation are not leaked in the payload
        assert "correct_answer" not in data
        assert "explanation" not in data


def test_use_hint_caching_on_repeated_requests():
    session_id = _create_mock_session(length=5)

    with patch("gemini_service.create_gemini_client") as mock_client_factory:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Focus on the primary enzyme involved."
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client_factory.return_value = mock_gemini

        # First hint request
        resp1 = client.post(
            "/use-hint",
            json={"session_id": session_id, "stage_number": 1},
        )
        assert resp1.status_code == 200
        hint1 = resp1.json()["hint"]
        assert mock_gemini.models.generate_content.call_count == 1

        # Second hint request on same stage
        resp2 = client.post(
            "/use-hint",
            json={"session_id": session_id, "stage_number": 1},
        )
        assert resp2.status_code == 200
        hint2 = resp2.json()["hint"]
        assert hint2 == hint1
        # Gemini should NOT have been called a second time
        assert mock_gemini.models.generate_content.call_count == 1


def test_use_hint_after_question_answered_is_rejected():
    session_id = _create_mock_session(length=5)
    # Submit answer for stage 1
    submit_resp = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"},
    )
    assert submit_resp.status_code == 200

    # Attempting to use hint after answering
    resp = client.post(
        "/use-hint",
        json={"session_id": session_id, "stage_number": 1},
    )
    assert resp.status_code == 400
    assert "already been answered" in resp.json()["detail"]


def test_use_hint_invalid_stage_and_session():
    session_id = _create_mock_session(length=5)

    # Out of bounds stage (< 1)
    resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 0})
    assert resp.status_code == 400

    # Out of bounds stage (> 5 for a 5-question game)
    resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 6})
    assert resp.status_code == 400

    # Nonexistent session
    resp = client.post("/use-hint", json={"session_id": "invalid-session-id", "stage_number": 1})
    assert resp.status_code == 404


def test_use_hint_fallback_when_gemini_unavailable():
    session_id = _create_mock_session(length=5)

    # Test fallback hint when client is None
    with patch("gemini_service.create_gemini_client", return_value=None):
        resp = client.post(
            "/use-hint",
            json={"session_id": session_id, "stage_number": 1},
        )
        assert resp.status_code == 200
        hint = resp.json()["hint"]
        assert len(hint) > 0
        # Correct answer must not be leaked
        assert "Option 1A" not in hint


def test_use_hint_prevents_verbatim_answer_leak():
    # If Gemini returns the exact answer in its text, service must catch and replace it
    mock_gemini = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "The answer is Option 1A obviously."
    mock_gemini.models.generate_content.return_value = mock_response

    hint = generate_hint_with_gemini(
        topic="Biology",
        question="What is it?",
        options=["Option 1A", "Option 1B", "Option 1C", "Option 1D"],
        correct_answer="Option 1A",
        explanation="Explanation here.",
        client=mock_gemini,
    )
    assert "Option 1A" not in hint


# ---------------------------------------------------------------------------
# 50/50 Power-Up Tests
# ---------------------------------------------------------------------------


def test_use_fifty_fifty_success_and_properties():
    session_id = _create_mock_session(length=5)
    stored_q = sessions[session_id]["gauntlet"][0]
    correct_answer = stored_q["correct_answer"]
    original_options = stored_q["options"]

    resp = client.post(
        "/use-50-50",
        json={"session_id": session_id, "stage_number": 1},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "options_to_remove" in data
    removed = data["options_to_remove"]

    # Exactly 2 options removed
    assert len(removed) == 2
    # Correct answer NEVER eliminated
    assert correct_answer not in removed
    # All removed options are from the original options
    for opt in removed:
        assert opt in original_options
    # Exactly 1 incorrect option remains with the correct answer
    remaining = [opt for opt in original_options if opt not in removed]
    assert len(remaining) == 2
    assert correct_answer in remaining


def test_use_fifty_fifty_caching_on_repeated_requests():
    session_id = _create_mock_session(length=5)

    resp1 = client.post(
        "/use-50-50",
        json={"session_id": session_id, "stage_number": 1},
    )
    assert resp1.status_code == 200
    removed1 = resp1.json()["options_to_remove"]

    # Second call for the same stage should return identical eliminated options
    resp2 = client.post(
        "/use-50-50",
        json={"session_id": session_id, "stage_number": 1},
    )
    assert resp2.status_code == 200
    removed2 = resp2.json()["options_to_remove"]
    assert removed1 == removed2


def test_use_fifty_fifty_after_answered_rejected():
    session_id = _create_mock_session(length=5)
    # Answer stage 1 first
    submit_resp = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"},
    )
    assert submit_resp.status_code == 200

    resp = client.post(
        "/use-50-50",
        json={"session_id": session_id, "stage_number": 1},
    )
    assert resp.status_code == 400
    assert "already been answered" in resp.json()["detail"]


def test_use_fifty_fifty_invalid_stage_and_session():
    session_id = _create_mock_session(length=5)

    resp = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 0})
    assert resp.status_code == 400

    resp = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 10})
    assert resp.status_code == 400

    resp = client.post("/use-50-50", json={"session_id": "unknown-session", "stage_number": 1})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Streak Multiplier and IP Scoring Tests
# ---------------------------------------------------------------------------


def test_streak_progression_fire_and_reset():
    session_id = _create_mock_session(length=5)
    gauntlet = sessions[session_id]["gauntlet"]

    # Stage 1: Correct -> Streak 1, Fire False, Base 100, Bonus 0, Total 100
    ans1 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": gauntlet[0]["correct_answer"]},
    ).json()
    assert ans1["is_correct"] is True
    assert ans1["current_streak"] == 1
    assert ans1["streak_fire_active"] is False
    assert ans1["base_ip_awarded"] == BASE_IP_PER_QUESTION
    assert ans1["bonus_ip_awarded"] == 0
    assert ans1["total_ip_awarded"] == 100

    # Stage 2: Correct -> Streak 2, Fire False, Base 100, Bonus 0, Total 200
    ans2 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 2, "selected_option": gauntlet[1]["correct_answer"]},
    ).json()
    assert ans2["is_correct"] is True
    assert ans2["current_streak"] == 2
    assert ans2["streak_fire_active"] is False
    assert ans2["base_ip_awarded"] == BASE_IP_PER_QUESTION
    assert ans2["bonus_ip_awarded"] == 0
    assert ans2["total_ip_awarded"] == 200

    # Stage 3: Correct -> Streak 3, Fire True (Threshold reached!), Base 100, Bonus 50, Total 350
    ans3 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 3, "selected_option": gauntlet[2]["correct_answer"]},
    ).json()
    assert ans3["is_correct"] is True
    assert ans3["current_streak"] == 3
    assert ans3["streak_fire_active"] is True
    assert ans3["base_ip_awarded"] == BASE_IP_PER_QUESTION
    assert ans3["bonus_ip_awarded"] == STREAK_FIRE_BONUS_IP
    assert ans3["total_ip_awarded"] == 350

    # Stage 4: Correct -> Streak 4, Fire True continues, Base 100, Bonus 50, Total 500
    ans4 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 4, "selected_option": gauntlet[3]["correct_answer"]},
    ).json()
    assert ans4["is_correct"] is True
    assert ans4["current_streak"] == 4
    assert ans4["streak_fire_active"] is True
    assert ans4["base_ip_awarded"] == BASE_IP_PER_QUESTION
    assert ans4["bonus_ip_awarded"] == STREAK_FIRE_BONUS_IP
    assert ans4["total_ip_awarded"] == 500

    # Stage 5: Incorrect -> Streak resets to 0, Fire False, Base 0, Bonus 0, Total stays 500
    wrong_opt = [o for o in gauntlet[4]["options"] if o != gauntlet[4]["correct_answer"]][0]
    ans5 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 5, "selected_option": wrong_opt},
    ).json()
    assert ans5["is_correct"] is False
    assert ans5["current_streak"] == 0
    assert ans5["streak_fire_active"] is False
    assert ans5["base_ip_awarded"] == 0
    assert ans5["bonus_ip_awarded"] == 0
    assert ans5["total_ip_awarded"] == 500


def test_streak_recovery_after_reset():
    session_id = _create_mock_session(length=10)
    gauntlet = sessions[session_id]["gauntlet"]

    # Stage 1: Incorrect -> Streak 0, Total 0
    wrong_opt_1 = [o for o in gauntlet[0]["options"] if o != gauntlet[0]["correct_answer"]][0]
    ans1 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": wrong_opt_1},
    ).json()
    assert ans1["is_correct"] is False
    assert ans1["current_streak"] == 0
    assert ans1["total_ip_awarded"] == 0

    # Stage 2: Correct -> Streak resumes at 1, Total 100
    ans2 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 2, "selected_option": gauntlet[1]["correct_answer"]},
    ).json()
    assert ans2["is_correct"] is True
    assert ans2["current_streak"] == 1
    assert ans2["total_ip_awarded"] == 100


def test_duplicate_submission_protection():
    session_id = _create_mock_session(length=5)
    gauntlet = sessions[session_id]["gauntlet"]

    # Stage 1: Initial correct submission
    ans1 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": gauntlet[0]["correct_answer"]},
    ).json()
    assert ans1["is_correct"] is True
    assert ans1["total_ip_awarded"] == 100
    assert ans1["current_streak"] == 1

    # Stage 2: Correct submission
    ans2 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 2, "selected_option": gauntlet[1]["correct_answer"]},
    ).json()
    assert ans2["total_ip_awarded"] == 200
    assert ans2["current_streak"] == 2

    # Duplicate submission for Stage 1 (even with wrong answer)
    wrong_opt = [o for o in gauntlet[0]["options"] if o != gauntlet[0]["correct_answer"]][0]
    dup_resp = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": wrong_opt},
    )
    assert dup_resp.status_code == 200
    dup_data = dup_resp.json()

    # Returns the original cached response for Stage 1
    assert dup_data["is_correct"] is True
    assert dup_data["current_streak"] == 1
    assert dup_data["total_ip_awarded"] == 100

    # Verify session total IP and streak were not corrupted by the duplicate
    assert sessions[session_id]["total_ip_awarded"] == 200
    assert sessions[session_id]["current_streak"] == 2


def test_session_isolation_for_streaks_and_powerups():
    session_a = _create_mock_session(length=5)
    session_b = _create_mock_session(length=5)

    gauntlet_a = sessions[session_a]["gauntlet"]
    gauntlet_b = sessions[session_b]["gauntlet"]

    # Session A scores 3 consecutive correct answers -> Fire active
    for i in range(1, 4):
        client.post(
            "/submit-answer",
            json={"session_id": session_a, "stage_number": i, "selected_option": gauntlet_a[i - 1]["correct_answer"]},
        )
    assert sessions[session_a]["current_streak"] == 3
    assert sessions[session_a]["total_ip_awarded"] == 350

    # Session B has answered nothing yet
    assert sessions[session_b]["current_streak"] == 0
    assert sessions[session_b]["total_ip_awarded"] == 0

    # Session B answers 1 question incorrectly
    wrong_b = [o for o in gauntlet_b[0]["options"] if o != gauntlet_b[0]["correct_answer"]][0]
    ans_b = client.post(
        "/submit-answer",
        json={"session_id": session_b, "stage_number": 1, "selected_option": wrong_b},
    ).json()
    assert ans_b["current_streak"] == 0
    assert sessions[session_b]["total_ip_awarded"] == 0

    # Session A is unaffected
    assert sessions[session_a]["current_streak"] == 3
    assert sessions[session_a]["total_ip_awarded"] == 350
