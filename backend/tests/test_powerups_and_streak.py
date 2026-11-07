"""
Comprehensive unit and integration tests for Live Power-Ups (AI Hint, 50/50)
and server-side Streak Multiplier scoring.
"""

import concurrent.futures
import time
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


def _create_mock_session(
    topic: str = "Biology",
    length: int = 5,
    difficulty: str = "Medium",
) -> str:
    """Helper to generate a clean mock game session."""
    questions = [
        Question(
            stage=i,
            tier=1 if i <= 5 else (2 if i <= 10 else (3 if i <= 15 else 4)),
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
            json={"topic": topic, "question_count": length, "difficulty": difficulty},
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


# ---------------------------------------------------------------------------
# Difficulty-Based Power-Up Allocation Tests
# ---------------------------------------------------------------------------


def test_powerup_limits_easy_difficulty():
    """Easy difficulty allows 2 hints, 2 50/50s, 2 time freezes. 3rd hint/50-50 rejected."""
    session_id = _create_mock_session(difficulty="Easy", length=5)
    assert sessions[session_id]["difficulty"] == "Easy"
    assert sessions[session_id]["power_up_limits"] == {"hint": 2, "fifty_fifty": 2, "time_freeze": 2}

    with patch("gemini_service.create_gemini_client") as mock_client:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Clue for stage"
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_gemini

        # Hint 1 (Stage 1) -> Success (remaining 1)
        h1 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
        assert h1.status_code == 200
        assert h1.json()["remaining_hints"] == 1

        # Hint 2 (Stage 2) -> Success (remaining 0)
        h2 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 2})
        assert h2.status_code == 200
        assert h2.json()["remaining_hints"] == 0

        # Hint 3 (Stage 3) -> 400 Bad Request (Limit exhausted)
        h3 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 3})
        assert h3.status_code == 400
        assert "limit exhausted" in h3.json()["detail"].lower()

    # 50/50 #1 (Stage 1) -> Success (remaining 1)
    f1 = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert f1.status_code == 200
    assert f1.json()["remaining_fifty_fifty"] == 1

    # 50/50 #2 (Stage 2) -> Success (remaining 0)
    f2 = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 2})
    assert f2.status_code == 200
    assert f2.json()["remaining_fifty_fifty"] == 0

    # 50/50 #3 (Stage 3) -> 400 Bad Request (Limit exhausted)
    f3 = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 3})
    assert f3.status_code == 400
    assert "limit exhausted" in f3.json()["detail"].lower()


def test_powerup_limits_medium_difficulty():
    """Medium difficulty allows 1 hint, 1 50/50, 2 time freezes. 2nd hint/50-50 rejected."""
    session_id = _create_mock_session(difficulty="Medium", length=5)
    assert sessions[session_id]["difficulty"] == "Medium"
    assert sessions[session_id]["power_up_limits"] == {"hint": 1, "fifty_fifty": 1, "time_freeze": 2}

    with patch("gemini_service.create_gemini_client") as mock_client:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Clue for stage 1"
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_gemini

        # Hint 1 -> Success
        h1 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
        assert h1.status_code == 200
        assert h1.json()["remaining_hints"] == 0

        # Hint 2 -> Rejected
        h2 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 2})
        assert h2.status_code == 400
        assert "limit exhausted" in h2.json()["detail"].lower()

    # 50/50 #1 -> Success
    f1 = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert f1.status_code == 200
    assert f1.json()["remaining_fifty_fifty"] == 0

    # 50/50 #2 -> Rejected
    f2 = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 2})
    assert f2.status_code == 400
    assert "limit exhausted" in f2.json()["detail"].lower()


def test_powerup_limits_hard_difficulty():
    """Hard difficulty allows 0 hints, 0 50/50, 2 time freezes. All hints and 50/50 rejected."""
    session_id = _create_mock_session(difficulty="Hard", length=5)
    assert sessions[session_id]["difficulty"] == "Hard"
    assert sessions[session_id]["power_up_limits"] == {"hint": 0, "fifty_fifty": 0, "time_freeze": 2}

    # Hint on Hard -> Rejected immediately
    h = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert h.status_code == 400
    assert "not available on hard" in h.json()["detail"].lower()

    # 50/50 on Hard -> Rejected immediately
    f = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert f.status_code == 400
    assert "not available on hard" in f.json()["detail"].lower()


def test_powerup_limits_expert_difficulty():
    """Expert difficulty allows 0 hints, 0 50/50, 0 time freezes. All rejected."""
    session_id = _create_mock_session(difficulty="Expert", length=5)
    assert sessions[session_id]["difficulty"] == "Expert"
    assert sessions[session_id]["power_up_limits"] == {"hint": 0, "fifty_fifty": 0, "time_freeze": 0}

    # Hint on Expert -> Rejected immediately
    h = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert h.status_code == 400
    assert "not available on expert" in h.json()["detail"].lower()

    # 50/50 on Expert -> Rejected immediately
    f = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert f.status_code == 400
    assert "not available on expert" in f.json()["detail"].lower()


@pytest.mark.parametrize("length", [5, 10, 15, 20])
def test_powerup_limits_uniform_across_gauntlet_lengths(length: int):
    """Confirm official limits apply uniformly regardless of dynamic length 5, 10, 15, 20."""
    session_id = _create_mock_session(difficulty="Medium", length=length)
    assert sessions[session_id]["power_up_limits"] == {"hint": 1, "fifty_fifty": 1, "time_freeze": 2}

    # Verify 1st 50/50 succeeds and 2nd fails across any gauntlet length
    f1 = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert f1.status_code == 200

    f2 = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 2})
    assert f2.status_code == 400
    assert "limit exhausted" in f2.json()["detail"].lower()


def test_fresh_session_starts_with_full_powerup_allowance():
    """A new session must have fresh power-up limits even if a prior session exhausted theirs."""
    # Session 1: Exhaust Medium allowance (1 hint)
    s1 = _create_mock_session(difficulty="Medium", length=5)
    with patch("gemini_service.create_gemini_client") as mock_client:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Clue for session 1"
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_gemini

        h1 = client.post("/use-hint", json={"session_id": s1, "stage_number": 1})
        assert h1.status_code == 200

        # 2nd hint in session 1 is exhausted
        h2 = client.post("/use-hint", json={"session_id": s1, "stage_number": 2})
        assert h2.status_code == 400

    # Session 2: New game has fresh counter
    s2 = _create_mock_session(difficulty="Medium", length=5)
    assert len(sessions[s2]["hints"]) == 0
    with patch("gemini_service.create_gemini_client") as mock_client:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Clue for session 2"
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_gemini

        h_new = client.post("/use-hint", json={"session_id": s2, "stage_number": 1})
        assert h_new.status_code == 200
        assert h_new.json()["remaining_hints"] == 0


def test_failed_hint_generation_does_not_consume_charge():
    """If Gemini hint generation encounters an unexpected error, no charge is consumed."""
    session_id = _create_mock_session(difficulty="Medium", length=5)

    with patch("main.generate_hint_with_gemini", side_effect=RuntimeError("API Network Drop")):
        resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
        # FastApi raises 500 or handles error
        assert resp.status_code == 500

    # Ensure no hints were recorded in the session
    assert len(sessions[session_id]["hints"]) == 0

    # Subsequent valid hint call succeeds and consumes the charge
    with patch("gemini_service.create_gemini_client") as mock_client:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Valid recovery clue"
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_gemini

        valid_resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
        assert valid_resp.status_code == 200
        assert valid_resp.json()["hint"] == "Valid recovery clue"
        assert len(sessions[session_id]["hints"]) == 1


def test_inferred_difficulty_from_target_level():
    """If difficulty is omitted but target_level contains '- Hard Level', infer Hard."""
    payload = GauntletPayload(
        is_valid=True,
        topic="Physics",
        gauntlet=[
            Question(
                stage=i,
                tier=1,
                question=f"Q{i}",
                options=["A", "B", "C", "D"],
                correct_answer="A",
                explanation="Exp",
            )
            for i in range(1, 6)
        ],
    )
    with patch("main.generate_gauntlet_with_gemini", return_value=payload):
        resp = client.post(
            "/generate-game",
            json={"topic": "Physics", "target_level": "Undergraduate - Hard Level", "question_count": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["difficulty"] == "Hard"
        assert data["power_up_limits"]["hint"] == 0
        assert data["power_up_limits"]["fifty_fifty"] == 0
        assert data["power_up_limits"]["time_freeze"] == 2


def test_invalid_difficulty_rejected():
    """Verify that an invalid difficulty string is rejected with 422."""
    resp = client.post(
        "/generate-game",
        json={"topic": "Physics", "difficulty": "SuperGodMode", "question_count": 5},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Concurrency and Forfeit Lifecycle Tests
# ---------------------------------------------------------------------------


def test_concurrent_hints_medium_difficulty_quota_enforced():
    """Two simultaneous hint requests on Medium (limit 1) must not both succeed."""
    session_id = _create_mock_session(difficulty="Medium", length=5)

    def slow_gemini(*args, **kwargs):
        time.sleep(0.12)
        return "Slow generated clue"

    with patch("main.generate_hint_with_gemini", side_effect=slow_gemini):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 1}))
            f2 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 2}))
            r1 = f1.result()
            r2 = f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    # Exactly one must succeed (200) and one must be rejected (400 limit exhausted)
    assert statuses == [200, 400]
    failed_resp = r1 if r1.status_code == 400 else r2
    assert "limit exhausted" in failed_resp.json()["detail"].lower()
    # Distinct recorded hints in session must strictly be 1
    assert len(sessions[session_id]["hints"]) == 1


def test_concurrent_hints_easy_difficulty_quota_enforced():
    """Four simultaneous hint requests on Easy (limit 2) must result in at most 2 successes."""
    session_id = _create_mock_session(difficulty="Easy", length=5)

    def slow_gemini(*args, **kwargs):
        time.sleep(0.12)
        return "Slow easy clue"

    with patch("main.generate_hint_with_gemini", side_effect=slow_gemini):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(lambda s=stage: client.post("/use-hint", json={"session_id": session_id, "stage_number": s}))
                for stage in [1, 2, 3, 4]
            ]
            results = [f.result() for f in futures]

    successes = [r for r in results if r.status_code == 200]
    failures = [r for r in results if r.status_code == 400]

    assert len(successes) == 2
    assert len(failures) == 2
    for f in failures:
        assert "limit exhausted" in f.json()["detail"].lower()
    assert len(sessions[session_id]["hints"]) == 2


def test_concurrent_hints_expert_difficulty_all_rejected():
    """Simultaneous hint requests on Expert (limit 0) must both be rejected."""
    session_id = _create_mock_session(difficulty="Expert", length=5)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 1}))
        f2 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 2}))
        r1 = f1.result()
        r2 = f2.result()

    assert r1.status_code == 400
    assert r2.status_code == 400
    assert "not available on expert" in r1.json()["detail"].lower()
    assert "not available on expert" in r2.json()["detail"].lower()
    assert len(sessions[session_id]["hints"]) == 0


def test_concurrent_hints_same_stage_prevents_duplicate_generation():
    """Two simultaneous requests for the exact same stage must not generate two separate Gemini calls."""
    session_id = _create_mock_session(difficulty="Medium", length=5)
    call_counter = {"count": 0}

    def slow_gemini(*args, **kwargs):
        call_counter["count"] += 1
        time.sleep(0.15)
        return "Single generation clue"

    with patch("main.generate_hint_with_gemini", side_effect=slow_gemini):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 1}))
            f2 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 1}))
            r1 = f1.result()
            r2 = f2.result()

    # One request gets 200 (succeeded), the concurrent duplicate gets 409 (conflict/in-flight)
    codes = sorted([r1.status_code, r2.status_code])
    assert codes == [200, 409]
    conflict_resp = r1 if r1.status_code == 409 else r2
    assert "currently being generated" in conflict_resp.json()["detail"].lower()

    # Gemini was only called once
    assert call_counter["count"] == 1
    assert len(sessions[session_id]["hints"]) == 1

    # Subsequent retry for Stage 1 returns the cached result cleanly
    retry = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert retry.status_code == 200
    assert retry.json()["hint"] == "Single generation clue"
    assert retry.json()["remaining_hints"] == 0


def test_concurrent_fifty_fifty_medium_quota_enforced():
    """Two simultaneous 50/50 requests on Medium (limit 1) must allow only 1 activation."""
    session_id = _create_mock_session(difficulty="Medium", length=5)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(lambda: client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1}))
        f2 = executor.submit(lambda: client.post("/use-50-50", json={"session_id": session_id, "stage_number": 2}))
        r1 = f1.result()
        r2 = f2.result()

    codes = sorted([r1.status_code, r2.status_code])
    assert codes == [200, 400]
    assert len(sessions[session_id]["fifty_fifty"]) == 1


def test_forfeit_game_endpoint_and_powerup_rejection():
    """Forfeiting a session rejects subsequent hints, 50/50s, and answer submissions."""
    session_id = _create_mock_session(difficulty="Easy", length=5)

    # Forfeit the game
    forfeit_resp = client.post("/forfeit-game", json={"session_id": session_id})
    assert forfeit_resp.status_code == 200
    data = forfeit_resp.json()
    assert data["session_id"] == session_id
    assert data["status"] == "forfeited"
    assert sessions[session_id]["is_forfeited"] is True

    # Try activating a hint after forfeit -> 400
    h_resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert h_resp.status_code == 400
    assert "forfeited" in h_resp.json()["detail"].lower()

    # Try activating 50/50 after forfeit -> 400
    f_resp = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert f_resp.status_code == 400
    assert "forfeited" in f_resp.json()["detail"].lower()

    # Try submitting answer after forfeit -> 400
    s_resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert s_resp.status_code == 400
    assert "forfeited" in s_resp.json()["detail"].lower()


def test_forfeit_game_future_unanswered_stages_rejected():
    """Even future, unvisited stages cannot have power-ups activated after forfeit."""
    session_id = _create_mock_session(difficulty="Easy", length=10)

    # Answer Stage 1
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})

    # Forfeit on stage 2
    client.post("/forfeit-game", json={"session_id": session_id})

    # Attempt to use hint on stage 5 (future stage) -> 400
    fut_hint = client.post("/use-hint", json={"session_id": session_id, "stage_number": 5})
    assert fut_hint.status_code == 400
    assert "forfeited" in fut_hint.json()["detail"].lower()

    # Attempt to use 50/50 on stage 8 (future stage) -> 400
    fut_fifty = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 8})
    assert fut_fifty.status_code == 400
    assert "forfeited" in fut_fifty.json()["detail"].lower()


def test_powerup_rejection_after_normal_game_completion():
    """When all stages are completed, power-up activations are rejected."""
    session_id = _create_mock_session(difficulty="Easy", length=5)

    # Complete all 5 stages
    for st in range(1, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": f"Option {st}A"})

    # Attempt hint on stage 1 -> rejected
    h = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert h.status_code == 400

    # Attempt 50/50 on stage 2 -> rejected
    f = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 2})
    assert f.status_code == 400


def test_forfeit_invalid_session_rejected():
    """Forfeiting a nonexistent session returns 404."""
    resp = client.post("/forfeit-game", json={"session_id": "nonexistent-uuid-12345"})
    assert resp.status_code == 404


def test_new_game_session_active_after_previous_forfeit():
    """A new game session starts fresh and active after an earlier session was forfeited."""
    # Session 1: Forfeited
    s1 = _create_mock_session(difficulty="Medium", length=5)
    client.post("/forfeit-game", json={"session_id": s1})
    assert sessions[s1]["is_forfeited"] is True

    # Session 2: Fresh
    s2 = _create_mock_session(difficulty="Medium", length=5)
    assert sessions[s2]["is_forfeited"] is False
    assert len(sessions[s2]["hints"]) == 0

    # Power-up works on Session 2
    with patch("gemini_service.create_gemini_client") as mock_client:
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Fresh hint"
        mock_gemini.models.generate_content.return_value = mock_response
        mock_client.return_value = mock_gemini

        resp = client.post("/use-hint", json={"session_id": s2, "stage_number": 1})
        assert resp.status_code == 200
        assert resp.json()["hint"] == "Fresh hint"

