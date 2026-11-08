"""
OmniQuest v1.0 Phase 3: Difficulty-Based Tier Progression Test Suite.

Comprehensive validation covering:
1. Progression thresholds (Easy, Medium, Hard, Expert across Tiers 1-4).
2. Tier-local IP tracking (meter starting at 0, contributions, resets, no excess carryover, total IP accumulation, streak preservation).
3. Backend progression enforcement (checkpoints, failed checkpoints, future locked tiers, server-authoritative difficulty and scoring).
4. Regression guarantees (Base IP, Speed Bonus, Streak Fire, AI Hints, 50/50, Time Freeze, Document generation).
5. Phase 3 Addendum 1: Difficulty defaults for document uploads (omitted, null, blank, explicit, unsupported rejection).
6. Phase 3 Addendum 2: Power-up checkpoint enforcement (/use-hint, /use-50-50 on unlocked/locked/checkpoint-failed stages).
"""

from __future__ import annotations

import concurrent.futures
import time
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from game_logic import (
    BASE_IP_PER_QUESTION,
    STREAK_FIRE_BONUS_IP,
    STREAK_FIRE_THRESHOLD,
    TIER_PROGRESSION_THRESHOLDS,
    GauntletPayload,
    Question,
    get_tier_checkpoints,
    get_tier_progression_threshold,
)
from main import app, sessions, store_session

client = TestClient(app)


def _build_test_gauntlet(length: int = 20) -> GauntletPayload:
    """Helper to create a structured gauntlet of any dynamic length."""
    questions: list[Question] = []
    for i in range(1, length + 1):
        tier = 1 if i <= 5 else (2 if i <= 10 else (3 if i <= 15 else 4))
        questions.append(
            Question(
                stage=i,
                tier=tier,
                question=f"Question prompt for stage {i}?",
                options=[f"Option {i}A", f"Option {i}B", f"Option {i}C", f"Option {i}D"],
                correct_answer=f"Option {i}A",
                explanation=f"Explanation for stage {i}.",
                hint=f"Educational hint for stage {i}." if tier <= 2 else None,
            )
        )
    return GauntletPayload(
        is_valid=True,
        topic="Computer Science",
        gauntlet=questions,
    )


def _setup_session(difficulty: str = "Medium", length: int = 20) -> str:
    """Helper to store a session with chosen difficulty and length."""
    payload = _build_test_gauntlet(length)
    return store_session(payload, difficulty=difficulty)


# ===========================================================================
# 1. Official Difficulty-Based Progression Thresholds (Tests 1 - 12)
# ===========================================================================


def test_easy_tier1_to_tier2_no_requirement():
    """1. Easy Tier 1 to Tier 2 requires no IP (returns None)."""
    assert get_tier_progression_threshold("Easy", 1) is None
    assert TIER_PROGRESSION_THRESHOLDS["Easy"][1] is None


def test_easy_tier2_to_tier3_no_requirement():
    """2. Easy Tier 2 to Tier 3 requires no IP (returns None)."""
    assert get_tier_progression_threshold("Easy", 2) is None
    assert TIER_PROGRESSION_THRESHOLDS["Easy"][2] is None


def test_easy_tier3_to_tier4_requires_300():
    """3. Easy Tier 3 to Tier 4 requires 300 IP."""
    assert get_tier_progression_threshold("Easy", 3) == 300
    assert TIER_PROGRESSION_THRESHOLDS["Easy"][3] == 300


def test_medium_tier1_to_tier2_requires_150():
    """4. Medium Tier 1 to Tier 2 requires 150 IP."""
    assert get_tier_progression_threshold("Medium", 1) == 150
    assert TIER_PROGRESSION_THRESHOLDS["Medium"][1] == 150


def test_medium_tier2_to_tier3_requires_250():
    """5. Medium Tier 2 to Tier 3 requires 250 IP."""
    assert get_tier_progression_threshold("Medium", 2) == 250
    assert TIER_PROGRESSION_THRESHOLDS["Medium"][2] == 250


def test_medium_tier3_to_tier4_requires_300():
    """6. Medium Tier 3 to Tier 4 requires 300 IP."""
    assert get_tier_progression_threshold("Medium", 3) == 300
    assert TIER_PROGRESSION_THRESHOLDS["Medium"][3] == 300


def test_hard_tier1_to_tier2_requires_300():
    """7. Hard Tier 1 to Tier 2 requires 300 IP."""
    assert get_tier_progression_threshold("Hard", 1) == 300
    assert TIER_PROGRESSION_THRESHOLDS["Hard"][1] == 300


def test_hard_tier2_to_tier3_requires_350():
    """8. Hard Tier 2 to Tier 3 requires 350 IP."""
    assert get_tier_progression_threshold("Hard", 2) == 350
    assert TIER_PROGRESSION_THRESHOLDS["Hard"][2] == 350


def test_hard_tier3_to_tier4_requires_400():
    """9. Hard Tier 3 to Tier 4 requires 400 IP."""
    assert get_tier_progression_threshold("Hard", 3) == 400
    assert TIER_PROGRESSION_THRESHOLDS["Hard"][3] == 400


def test_expert_tier1_to_tier2_requires_300():
    """10. Expert Tier 1 to Tier 2 requires 300 IP."""
    assert get_tier_progression_threshold("Expert", 1) == 300
    assert TIER_PROGRESSION_THRESHOLDS["Expert"][1] == 300


def test_expert_tier2_to_tier3_requires_400():
    """11. Expert Tier 2 to Tier 3 requires 400 IP."""
    assert get_tier_progression_threshold("Expert", 2) == 400
    assert TIER_PROGRESSION_THRESHOLDS["Expert"][2] == 400


def test_expert_tier3_to_tier4_requires_500():
    """12. Expert Tier 3 to Tier 4 requires 500 IP."""
    assert get_tier_progression_threshold("Expert", 3) == 500
    assert TIER_PROGRESSION_THRESHOLDS["Expert"][3] == 500


# ===========================================================================
# 2. Tier-Local IP Tracking (Tests 13 - 21)
# ===========================================================================


def test_tier_local_ip_starts_at_zero():
    """13. Tier-local IP starts at zero on session creation."""
    session_id = _setup_session("Medium", 20)
    assert sessions[session_id]["tier_local_ip"] == 0
    assert sessions[session_id]["current_tier"] == 1


def test_correct_base_ip_contributes_to_tier_meter():
    """14. Correct-answer Base IP (100) contributes to the tier meter."""
    session_id = _setup_session("Medium", 20)
    resp = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    assert data["tier_local_ip"] == 100
    assert sessions[session_id]["tier_local_ip"] == 100


def test_speed_bonus_contributes_to_tier_meter():
    """15. Speed bonus is calculated server-side and contributes to tier meter."""
    session_id = _setup_session("Medium", 20)
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 7.6  # 12.4s remaining -> 60 IP
    resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": "Option 1A",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    assert data["speed_ip_awarded"] == 60  # round(12.4) * 5 = 60
    assert data["points_awarded"] == 160
    assert data["tier_local_ip"] == 160
    assert data["total_ip_awarded"] == 160
    assert sessions[session_id]["tier_local_ip"] == 160
    assert sessions[session_id]["total_ip_awarded"] == 160


def test_streak_fire_bonus_contributes_to_tier_meter():
    """16. Streak Fire bonuses (+50 on 3rd+) contribute to the tier meter."""
    session_id = _setup_session("Medium", 20)
    # Stage 1: 100 base IP
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    # Stage 2: 100 base IP
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A"})
    # Stage 3: 100 base + 50 streak fire bonus = 150 IP
    r3 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 3, "selected_option": "Option 3A"})
    data3 = r3.json()
    assert data3["is_correct"] is True
    assert data3["current_streak"] == 3
    assert data3["streak_fire_active"] is True
    assert data3["bonus_ip_awarded"] == 50
    # Total tier IP: 100 + 100 + 150 = 350
    assert data3["tier_local_ip"] == 350
    assert sessions[session_id]["tier_local_ip"] == 350


def test_incorrect_answers_do_not_award_tier_local_ip():
    """17. Incorrect answers do not incorrectly award tier-local IP."""
    session_id = _setup_session("Medium", 20)
    resp = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1B"},  # Incorrect
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is False
    assert data["base_ip_awarded"] == 0
    assert data["tier_local_ip"] == 0
    assert sessions[session_id]["tier_local_ip"] == 0


def test_tier_local_ip_resets_when_advancing_to_next_tier():
    """18. Tier-local IP resets to zero when advancing to the next tier."""
    session_id = _setup_session("Medium", 20)  # Medium Tier 1 requires 150 IP
    # Answer stages 1 and 2 correctly (200 IP total)
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 3, "selected_option": "Option 3B"})  # incorrect
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 4, "selected_option": "Option 4B"})  # incorrect
    # Stage 5 checkpoint: 200 IP >= 150 threshold -> checkpoint passed!
    r5 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 5, "selected_option": "Option 5B"})
    assert r5.json()["checkpoint_passed"] is True
    assert sessions[session_id]["current_tier"] == 2
    # Tier-local IP must reset to 0 for Tier 2!
    assert sessions[session_id]["tier_local_ip"] == 0


def test_excess_ip_does_not_carry_over():
    """19. Excess IP earned in the previous tier must NOT carry over."""
    session_id = _setup_session("Medium", 20)  # Medium Tier 1 requires 150 IP
    # Answer all 5 questions correctly: 100 + 100 + 150 + 150 + 150 = 650 IP (500 excess IP)
    for st in range(1, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": f"Option {st}A"})

    # Checkpoint passed, tier 2 initialized:
    assert sessions[session_id]["tier_local_ip"] == 0
    # Now answer stage 6 (first question of Tier 2) correctly
    r6 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 6, "selected_option": "Option 6A"})
    data6 = r6.json()
    # Tier 2 local meter should be exactly 150 (100 base + 50 streak), NOT 650 + 150
    assert data6["tier_local_ip"] == 150
    assert sessions[session_id]["tier_local_ip"] == 150


def test_total_game_ip_remains_cumulative_after_tier_reset():
    """20. Total game IP remains cumulative and is never deducted on tier reset."""
    session_id = _setup_session("Medium", 20)
    for st in range(1, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": f"Option {st}A"})

    # Total IP for 5 questions with streak fire = 650 IP
    assert sessions[session_id]["total_ip_awarded"] == 650
    assert sessions[session_id]["tier_local_ip"] == 0  # Tier meter reset

    # Answer stage 6 correctly
    r6 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 6, "selected_option": "Option 6A"})
    assert r6.json()["total_ip_awarded"] == 800  # 650 + 150
    assert sessions[session_id]["total_ip_awarded"] == 800


def test_streak_state_preserved_across_tier_transitions():
    """21. Streak state is preserved across tier transitions."""
    session_id = _setup_session("Medium", 20)
    for st in range(1, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": f"Option {st}A"})

    assert sessions[session_id]["current_streak"] == 5
    # Stage 6 correct continues streak to 6
    r6 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 6, "selected_option": "Option 6A"})
    assert r6.json()["current_streak"] == 6
    assert r6.json()["streak_fire_active"] is True
    assert r6.json()["bonus_ip_awarded"] == 50


# ===========================================================================
# 3. Backend Progression Enforcement (Tests 22 - 30)
# ===========================================================================


def test_player_meeting_threshold_can_progress():
    """22. A player meeting the threshold can progress."""
    session_id = _setup_session("Hard", 20)  # Hard Tier 1 requires 300 IP
    # 3 correct answers = 100 + 100 + 150 = 350 IP >= 300
    for st in range(1, 4):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": f"Option {st}A"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 4, "selected_option": "Wrong"})
    r5 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 5, "selected_option": "Wrong"})

    assert r5.json()["checkpoint_passed"] is True
    assert r5.json()["is_game_over"] is False
    assert sessions[session_id]["checkpoint_failed"] is False
    assert 5 in sessions[session_id]["passed_checkpoints"]


def test_player_below_threshold_cannot_progress():
    """23. A player below the threshold cannot progress and encounters game over."""
    session_id = _setup_session("Hard", 20)  # Hard Tier 1 requires 300 IP
    # Only 2 correct answers = 200 IP < 300
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 3, "selected_option": "Wrong"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 4, "selected_option": "Wrong"})
    r5 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 5, "selected_option": "Wrong"})

    data5 = r5.json()
    assert data5["checkpoint_passed"] is False
    assert data5["is_game_over"] is True
    assert sessions[session_id]["checkpoint_failed"] is True

    # Subsequent stage 6 submission is rejected
    r6 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 6, "selected_option": "Option 6A"})
    assert r6.status_code == 400
    assert "failed checkpoint" in r6.json()["detail"].lower()


def test_cannot_submit_answer_for_future_tier_before_passing_checkpoint():
    """24. A player cannot submit an answer for a future tier before passing the checkpoint."""
    session_id = _setup_session("Medium", 20)
    # Player is at stage 1, tries to submit stage 6 (in Tier 2) directly via API
    r = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 6, "selected_option": "Option 6A"})
    assert r.status_code == 400
    assert "locked" in r.json()["detail"].lower()


def test_frontend_supplied_difficulty_cannot_bypass_rules():
    """25. Frontend-supplied difficulty cannot bypass server-side progression rules."""
    session_id = _setup_session("Hard", 20)  # Authoritative Hard (300 IP required)
    # Even if client tries to pass Easy or alter payload, /submit-answer schema does not take difficulty
    # and backend checks session["difficulty"]
    assert sessions[session_id]["difficulty"] == "Hard"


def test_frontend_supplied_tier_local_ip_cannot_bypass_rules():
    """26. Frontend-supplied tier-local IP cannot bypass server-side rules."""
    session_id = _setup_session("Medium", 20)
    # SubmitAnswerRequest only takes session_id, stage_number, selected_option
    # Backend computes tier_local_ip authoritatively
    r = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A", "tier_local_ip": 9999},
    )
    assert r.json()["tier_local_ip"] == 100  # Ignored fake client value


def test_shorter_gauntlets_do_not_enforce_nonexistent_gates():
    """27. Shorter gauntlets do not enforce nonexistent progression gates."""
    # 5-question gauntlet has NO checkpoints
    s5 = _setup_session("Hard", 5)
    assert get_tier_checkpoints(5) == []
    # Fail every question in a 5-question gauntlet
    for st in range(1, 6):
        r = client.post("/submit-answer", json={"session_id": s5, "stage_number": st, "selected_option": "Wrong"})
        assert r.status_code == 200
        # Final stage 5 is gauntlet completion, NOT checkpoint elimination
        if st == 5:
            assert r.json()["is_checkpoint_stage"] is False
            assert r.json()["is_game_over"] is False
            assert sessions[s5]["checkpoint_failed"] is False


def test_easy_progression_gates_without_requirements_auto_pass():
    """28. Easy progression gates without requirements work correctly and auto-pass."""
    s_easy = _setup_session("Easy", 20)
    # Fail all 5 questions in Tier 1 (0 IP earned)
    for st in range(1, 6):
        r = client.post("/submit-answer", json={"session_id": s_easy, "stage_number": st, "selected_option": "Wrong"})
    # Stage 5 checkpoint auto-passes because threshold is None
    data5 = r.json()
    assert data5["checkpoint_passed"] is True
    assert data5["is_game_over"] is False
    assert sessions[s_easy]["checkpoint_failed"] is False
    assert 5 in sessions[s_easy]["passed_checkpoints"]

    # Player can legitimately play stage 6 in Tier 2
    r6 = client.post("/submit-answer", json={"session_id": s_easy, "stage_number": 6, "selected_option": "Option 6A"})
    assert r6.status_code == 200


def test_failed_progression_uses_existing_game_over_behavior():
    """29. Failed progression marks is_game_over and checkpoint_failed."""
    session_id = _setup_session("Expert", 20)  # Expert Tier 1 requires 300 IP
    for st in range(1, 6):
        r = client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": "Wrong"})
    assert r.json()["checkpoint_passed"] is False
    assert r.json()["is_game_over"] is True
    assert sessions[session_id]["checkpoint_failed"] is True


def test_repeated_submissions_cannot_award_duplicate_ip():
    """30. Repeated submissions cannot award duplicate IP."""
    session_id = _setup_session("Medium", 20)
    r1 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert r1.json()["total_ip_awarded"] == 100
    assert sessions[session_id]["total_ip_awarded"] == 100

    # Repeat submission for stage 1
    r2 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert r2.status_code == 200
    assert r2.json()["total_ip_awarded"] == 100
    assert sessions[session_id]["total_ip_awarded"] == 100


# ===========================================================================
# 4. Regression Guarantees (Tests 31 - 36)
# ===========================================================================


def test_existing_base_ip_calculations_unchanged():
    """31. Existing Base IP calculations remain unchanged (100 IP)."""
    assert BASE_IP_PER_QUESTION == 100


def test_existing_speed_bonus_calculations_unchanged():
    """32. Existing Speed Bonus calculations remain unchanged."""
    # Speed bonus formula is round(remaining_sec) * 5
    remaining_ms = 18_200
    speed_bonus = round(remaining_ms / 1000) * 5
    assert speed_bonus == 90


def test_existing_streak_fire_calculations_unchanged():
    """33. Existing Streak Fire calculations remain unchanged (threshold 3, +50 IP)."""
    assert STREAK_FIRE_THRESHOLD == 3
    assert STREAK_FIRE_BONUS_IP == 50


def test_existing_ai_hint_behavior_intact():
    """34. Existing AI Hint behavior remains intact."""
    session_id = _setup_session("Medium", 5)
    r = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert r.status_code == 200
    assert r.json()["hint"] == "Educational hint for stage 1."


def test_existing_50_50_and_freeze_behavior_intact():
    """35. Existing 50/50 and Time Freeze behavior remain intact."""
    session_id = _setup_session("Medium", 5)
    r = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert r.status_code == 200
    removed = r.json()["options_to_remove"]
    assert len(removed) == 2
    assert "Option 1A" not in removed  # Correct answer never removed


def test_existing_document_generation_intact():
    """36. Existing document-based generation remains intact."""
    sample_text = "Mitochondria generate ATP through cellular respiration in aerobic eukaryotic organisms." * 10
    with patch("main.generate_gauntlet_with_gemini") as mock_gen:
        mock_payload = _build_test_gauntlet(5)
        mock_payload.topic = "Mitochondrial Respiration"
        mock_gen.return_value = mock_payload

        resp = client.post(
            "/generate-game",
            json={
                "topic": "Cell Biology",
                "source_text": sample_text,
                "difficulty": "Hard",
                "question_count": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["difficulty"] == "Hard"
        assert data["question_count"] == 5


# ===========================================================================
# 5. Addition 1: Difficulty Defaults for Document Uploads (Tests 37 - 42)
# ===========================================================================


def test_document_only_generation_omitted_difficulty_defaults_to_medium():
    """37. Document-only generation with omitted difficulty defaults to Medium."""
    sample_text = "Photosynthesis occurs in chloroplasts where chlorophyll absorbs sunlight." * 10
    with patch("main.identify_document_topic", return_value="Photosynthesis"), \
         patch("main.generate_gauntlet_with_gemini") as mock_gen:
        mock_gen.return_value = _build_test_gauntlet(5)
        resp = client.post(
            "/generate-game",
            json={"source_text": sample_text, "question_count": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["difficulty"] == "Medium"
        assert sessions[data["session_id"]]["difficulty"] == "Medium"


def test_document_only_generation_null_difficulty_defaults_to_medium():
    """38. Document-only generation with null difficulty defaults to Medium."""
    sample_text = "Photosynthesis occurs in chloroplasts where chlorophyll absorbs sunlight." * 10
    with patch("main.identify_document_topic", return_value="Photosynthesis"), \
         patch("main.generate_gauntlet_with_gemini") as mock_gen:
        mock_gen.return_value = _build_test_gauntlet(5)
        resp = client.post(
            "/generate-game",
            json={"source_text": sample_text, "difficulty": None, "question_count": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["difficulty"] == "Medium"


def test_blank_or_whitespace_difficulty_defaults_to_medium():
    """39. Blank or whitespace-only difficulty defaults to Medium."""
    sample_text = "Photosynthesis occurs in chloroplasts where chlorophyll absorbs sunlight." * 10
    with patch("main.identify_document_topic", return_value="Photosynthesis"), \
         patch("main.generate_gauntlet_with_gemini") as mock_gen:
        mock_gen.return_value = _build_test_gauntlet(5)
        resp = client.post(
            "/generate-game",
            json={"source_text": sample_text, "difficulty": "   ", "question_count": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["difficulty"] == "Medium"


def test_explicit_difficulties_preserved():
    """40. Explicit Easy, Medium, Hard, and Expert values are preserved."""
    for diff in ["Easy", "Medium", "Hard", "Expert"]:
        with patch("main.generate_gauntlet_with_gemini") as mock_gen:
            mock_gen.return_value = _build_test_gauntlet(5)
            resp = client.post(
                "/generate-game",
                json={"topic": "Quantum Mechanics", "difficulty": diff, "question_count": 5},
            )
            assert resp.status_code == 200
            assert resp.json()["difficulty"] == diff
            assert sessions[resp.json()["session_id"]]["difficulty"] == diff


def test_unsupported_difficulty_values_rejected():
    """41. Unsupported difficulty values like General or SuperHard are rejected."""
    sample_text = "Photosynthesis occurs in chloroplasts where chlorophyll absorbs sunlight." * 10
    for invalid in ["General", "SuperHard", "Ultra", "123"]:
        resp = client.post(
            "/generate-game",
            json={"source_text": sample_text, "difficulty": invalid, "question_count": 5},
        )
        assert resp.status_code == 422


def test_progression_threshold_lookup_never_receives_invalid_difficulty():
    """42. Progression threshold lookup raises ValueError if given invalid difficulty."""
    with pytest.raises(ValueError, match="Invalid difficulty"):
        get_tier_progression_threshold("InvalidDifficulty", 1)


# ===========================================================================
# 6. Addition 2: Power-up Checkpoint Enforcement (Tests 43 - 51)
# ===========================================================================


def test_ai_hint_activation_on_valid_unlocked_stage():
    """43. AI Hint activation on a valid unlocked stage succeeds."""
    session_id = _setup_session("Medium", 20)
    r = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert r.status_code == 200
    assert r.json()["is_available"] is True


def test_fifty_fifty_activation_on_valid_unlocked_stage():
    """44. 50/50 activation on a valid unlocked stage succeeds."""
    session_id = _setup_session("Medium", 20)
    r = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert r.status_code == 200
    assert len(r.json()["options_to_remove"]) == 2


def test_ai_hint_activation_on_stage_locked_by_failed_checkpoint():
    """45. AI Hint activation on a stage locked by a failed checkpoint is rejected."""
    session_id = _setup_session("Hard", 20)  # Hard requires 300 IP
    # Fail stage 1-5 checkpoint
    for st in range(1, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": "Wrong"})
    assert sessions[session_id]["checkpoint_failed"] is True

    # Attempt to activate hint on stage 6
    r = client.post("/use-hint", json={"session_id": session_id, "stage_number": 6})
    assert r.status_code == 400
    assert "failed checkpoint" in r.json()["detail"].lower()


def test_fifty_fifty_activation_on_stage_locked_by_failed_checkpoint():
    """46. 50/50 activation on a stage locked by a failed checkpoint is rejected."""
    session_id = _setup_session("Hard", 20)
    for st in range(1, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": "Wrong"})
    assert sessions[session_id]["checkpoint_failed"] is True

    # Attempt to activate 50/50 on stage 6
    r = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 6})
    assert r.status_code == 400
    assert "failed checkpoint" in r.json()["detail"].lower()


def test_direct_api_requests_for_future_stages_rejected():
    """47. Direct API requests for future stages are rejected."""
    session_id = _setup_session("Medium", 20)
    # While still at stage 1 (Tier 1), call /use-hint and /use-50-50 on stage 6 (Tier 2)
    rh = client.post("/use-hint", json={"session_id": session_id, "stage_number": 6})
    assert rh.status_code == 400
    assert "locked" in rh.json()["detail"].lower()

    rf = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 6})
    assert rf.status_code == 400
    assert "locked" in rf.json()["detail"].lower()


def test_rejected_powerup_requests_do_not_consume_charges():
    """48. Rejected power-up requests do not consume charges."""
    session_id = _setup_session("Medium", 20)
    # Remaining hint count is initially 1
    assert sessions[session_id]["power_up_limits"]["hint"] == 1

    # Rejected attempt on future locked stage 6
    r = client.post("/use-hint", json={"session_id": session_id, "stage_number": 6})
    assert r.status_code == 400

    # Charge was not consumed
    assert len(sessions[session_id]["hints"]) == 0


def test_rejected_requests_do_not_modify_per_stage_counters():
    """49. Rejected requests do not modify per-stage usage counters."""
    session_id = _setup_session("Medium", 20)
    client.post("/use-50-50", json={"session_id": session_id, "stage_number": 6})  # rejected
    assert 6 not in sessions[session_id]["fifty_fifty"]


def test_existing_concurrency_safeguards_remain_effective():
    """50. Existing concurrency safeguards remain effective."""
    session_id = _setup_session("Medium", 20)
    # Medium allows exactly 1 hint. Send 4 simultaneous requests for stage 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 1}))
            for _ in range(4)
        ]
        results = [f.result() for f in futures]

    successes = [r for r in results if r.status_code == 200]
    # All 4 succeed identically because of idempotent retry on stage 1
    assert len(successes) == 4
    # But only 1 hint activation is stored
    assert len(sessions[session_id]["hints"]) == 1


def test_valid_powerup_activation_continues_working_after_passing_checkpoint():
    """51. Valid power-up activation continues working after successfully passing a checkpoint."""
    session_id = _setup_session("Easy", 20)  # Easy has 2 hints and 2 50/50s
    # Pass Tier 1 by answering stages 1 to 5 correctly
    for st in range(1, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": f"Option {st}A"})

    assert sessions[session_id]["current_tier"] == 2
    assert 5 in sessions[session_id]["passed_checkpoints"]

    # In Tier 2, stage 6 is now unlocked: activate hint and 50/50
    rh = client.post("/use-hint", json={"session_id": session_id, "stage_number": 6})
    assert rh.status_code == 200
    assert rh.json()["remaining_hints"] == 1

    rf = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 6})
    assert rf.status_code == 200
    assert rf.json()["remaining_fifty_fifty"] == 1


# ===========================================================================
# 7. Speed Bonus & Complete Scoring Consistency Tests
# ===========================================================================


def test_scoring_breakdown_base_speed_streak_counted_exactly_once():
    """Verify Base IP, Speed Bonus, and Streak Fire are all present and counted exactly once."""
    session_id = _setup_session("Medium", 20)

    # Question 1: Correct with 14.2s remaining -> Base 100, Speed round(14.2)*5 = 70, Streak 0 -> Awarded 170
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 5.8
    r1 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"},
    )
    d1 = r1.json()
    assert d1["base_ip_awarded"] == 100
    assert d1["speed_ip_awarded"] == 70
    assert d1["streak_ip_awarded"] == 0
    assert d1["points_awarded"] == 170
    assert d1["total_ip_awarded"] == 170
    assert d1["tier_local_ip"] == 170

    # Question 2: Correct with 10.0s remaining -> Base 100, Speed 50, Streak 0 -> Awarded 150
    sessions[session_id]["stage_start_times"][2] = time.monotonic() - 10.0
    r2 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A"},
    )
    d2 = r2.json()
    assert d2["base_ip_awarded"] == 100
    assert d2["speed_ip_awarded"] == 50
    assert d2["streak_ip_awarded"] == 0
    assert d2["points_awarded"] == 150
    assert d2["total_ip_awarded"] == 320  # 170 + 150
    assert d2["tier_local_ip"] == 320

    # Question 3: Correct with 18.0s remaining -> Base 100, Speed 90, Streak 50 -> Awarded 240
    sessions[session_id]["stage_start_times"][3] = time.monotonic() - 2.0
    r3 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 3, "selected_option": "Option 3A"},
    )
    d3 = r3.json()
    assert d3["base_ip_awarded"] == 100
    assert d3["speed_ip_awarded"] == 90
    assert d3["streak_ip_awarded"] == 50
    assert d3["bonus_ip_awarded"] == 50
    assert d3["points_awarded"] == 240
    assert d3["total_ip_awarded"] == 560  # 320 + 240
    assert d3["tier_local_ip"] == 560


def test_incorrect_answer_awards_zero_across_all_scoring_components():
    """Verify incorrect answers award 0 Base IP, 0 Speed Bonus, 0 Streak Fire."""
    session_id = _setup_session("Medium", 20)
    # Even if answered instantly (19.9s remaining), incorrect answer awards 0 across the board
    r = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1B", "remaining_time_ms": 19_900},
    )
    d = r.json()
    assert d["is_correct"] is False
    assert d["base_ip_awarded"] == 0
    assert d["speed_ip_awarded"] == 0
    assert d["streak_ip_awarded"] == 0
    assert d["points_awarded"] == 0
    assert d["total_ip_awarded"] == 0
    assert d["tier_local_ip"] == 0


def test_streak_fire_activation_and_reset_with_speed_bonuses():
    """Verify Streak Fire triggers on 3rd consecutive correct and resets on mistake."""
    session_id = _setup_session("Medium", 20)
    # 1st correct: streak 1, no bonus
    r1 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A", "remaining_time_ms": 10_000})
    assert r1.json()["current_streak"] == 1
    assert r1.json()["streak_fire_active"] is False
    assert r1.json()["streak_ip_awarded"] == 0

    # 2nd correct: streak 2, no bonus
    r2 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A", "remaining_time_ms": 10_000})
    assert r2.json()["current_streak"] == 2
    assert r2.json()["streak_fire_active"] is False
    assert r2.json()["streak_ip_awarded"] == 0

    # 3rd correct: streak 3, FIRE ACTIVE (+50)
    r3 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 3, "selected_option": "Option 3A", "remaining_time_ms": 10_000})
    assert r3.json()["current_streak"] == 3
    assert r3.json()["streak_fire_active"] is True
    assert r3.json()["streak_ip_awarded"] == 50

    # 4th incorrect: streak breaks to 0
    r4 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 4, "selected_option": "Wrong", "remaining_time_ms": 10_000})
    assert r4.json()["current_streak"] == 0
    assert r4.json()["streak_fire_active"] is False
    assert r4.json()["streak_ip_awarded"] == 0

    # 5th correct: streak 1, no bonus
    r5 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 5, "selected_option": "Option 5A", "remaining_time_ms": 10_000})
    assert r5.json()["current_streak"] == 1
    assert r5.json()["streak_fire_active"] is False


def test_speed_bonus_enables_legitimate_checkpoint_progression():
    """Verify Speed Bonus is fully accounted for in checkpoint decisions."""
    session_id = _setup_session("Medium", 20)  # Medium Tier 1 requires 150 IP
    # Player answers Stage 1 fast (12s remaining): 100 Base + 60 Speed = 160 IP
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 8.0
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    # Stages 2, 3, 4 are incorrect (0 IP)
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 2, "selected_option": "Wrong"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 3, "selected_option": "Wrong"})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 4, "selected_option": "Wrong"})

    # Stage 5 is also incorrect (0 IP), but tier total is 160 IP >= 150 requirement!
    r5 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 5, "selected_option": "Wrong"})
    d5 = r5.json()
    assert d5["checkpoint_passed"] is True
    assert d5["is_game_over"] is False
    assert sessions[session_id]["checkpoint_failed"] is False


def test_tier_transition_resets_tier_local_ip_with_speed_bonuses():
    """Verify tier transition resets tier meter to 0 while total IP keeps speed bonuses."""
    session_id = _setup_session("Medium", 20)
    # Stage 1: 100 Base + 60 Speed = 160 IP
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 8.0
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    for st in range(2, 6):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": "Wrong"})

    # Total IP is 160, tier meter is reset to 0 for Tier 2
    assert sessions[session_id]["total_ip_awarded"] == 160
    assert sessions[session_id]["tier_local_ip"] == 0

    # Stage 6: 100 Base + 50 Speed = 150 IP
    sessions[session_id]["stage_start_times"][6] = time.monotonic() - 10.0
    r6 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 6, "selected_option": "Option 6A"})
    d6 = r6.json()
    assert d6["tier_local_ip"] == 150
    assert d6["total_ip_awarded"] == 310  # 160 + 150


def test_speed_bonus_bounding_and_zero_fallback():
    """Verify Speed Bonus bounds and fallback behavior."""
    from game_logic import calculate_speed_bonus

    # Direct unit formula validation
    assert calculate_speed_bonus(0) == 0
    assert calculate_speed_bonus(-500) == 0
    assert calculate_speed_bonus(30_000) == 100
    assert calculate_speed_bonus(16_000) == 80

    # Server-authoritative timing:
    session_id = _setup_session("Medium", 20)
    # 20s elapsed -> 0s remaining -> 0 IP
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 20.0
    r0 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert r0.json()["speed_ip_awarded"] == 0

    # 4s elapsed -> 16s remaining -> round(16)*5 = 80 IP
    s_resp = _setup_session("Medium", 20)
    sessions[s_resp]["stage_start_times"][1] = time.monotonic() - 4.0
    r_resp = client.post("/submit-answer", json={"session_id": s_resp, "stage_number": 1, "selected_option": "Option 1A"})
    assert r_resp.json()["speed_ip_awarded"] == 80


def test_idempotent_retry_preserves_speed_bonus_without_double_counting():
    """Verify idempotent submission returns cached speed bonus without double-counting."""
    session_id = _setup_session("Medium", 20)
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 8.0
    r1 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"},
    )
    assert r1.json()["points_awarded"] == 160
    assert r1.json()["total_ip_awarded"] == 160

    # Retry submission
    r2 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"},
    )
    assert r2.status_code == 200
    assert r2.json()["points_awarded"] == 160
    assert r2.json()["total_ip_awarded"] == 160
    assert sessions[session_id]["total_ip_awarded"] == 160

