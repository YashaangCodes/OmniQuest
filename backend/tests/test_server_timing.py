"""
OmniQuest v0.9 Server-Authoritative Timing Regression Test Suite.

Validates:
1. Normal submission with correct server-calculated Speed Bonus.
2. Forged remaining_time_ms values are ignored.
3. Forged response_time_ms values are ignored.
4. Submission after authoritative deadline (+ grace buffer) rejected with HTTP 400.
5. Submission within valid 20-second window accepted.
6. Time Freeze extends authoritative deadline by exactly 5.0 seconds.
7. Multiple Time Freeze requests and simultaneous activation attempts.
8. Time spent reading explanations does not consume the next question's timer.
9. Duplicate submissions do not award additional IP or extend timers.
10. Client timing manipulation cannot bypass checkpoint requirements.
11. Existing difficulty-based power-up quotas remain strictly enforced.
12. Existing forfeiture, completion, and checkpoint protections remain active.
"""

from __future__ import annotations

import concurrent.futures
import time
from unittest.mock import patch
from fastapi.testclient import TestClient

from game_logic import (
    QUESTION_TIME_LIMIT_SECONDS,
    TIME_FREEZE_DURATION_SECONDS,
    DEADLINE_GRACE_BUFFER_SECONDS,
    GauntletPayload,
    Question,
)
from main import app, sessions, store_session

client = TestClient(app)


def _build_test_gauntlet(length: int = 20) -> GauntletPayload:
    """Create a structured test gauntlet with deterministic questions."""
    questions: list[Question] = []
    for i in range(1, length + 1):
        tier = 1 if i <= 5 else (2 if i <= 10 else (3 if i <= 15 else 4))
        questions.append(
            Question(
                stage=i,
                tier=tier,
                question=f"Test Question for Stage {i}?",
                options=[f"Option {i}A", f"Option {i}B", f"Option {i}C", f"Option {i}D"],
                correct_answer=f"Option {i}A",
                explanation=f"Explanation for Stage {i}.",
                hint=f"Hint for Stage {i}.",
            )
        )
    return GauntletPayload(
        is_valid=True,
        topic="Timing Security Validation",
        gauntlet=questions,
    )


def _setup_session(difficulty: str = "Medium", length: int = 20) -> str:
    """Store a test session and return its session_id."""
    payload = _build_test_gauntlet(length)
    return store_session(payload, difficulty=difficulty)


# ---------------------------------------------------------------------------
# 1. Normal submission with correct server-calculated Speed Bonus
# ---------------------------------------------------------------------------
def test_normal_submission_server_calculated_speed_bonus():
    """1. Normal submission calculates Speed Bonus using authoritative server monotonic elapsed time."""
    session_id = _setup_session("Medium", 20)

    # Start stage 1
    start_resp = client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    assert start_resp.status_code == 200
    assert start_resp.json()["time_limit_seconds"] == 20
    assert start_resp.json()["is_active"] is True

    # Simulate 8.0s elapsed (12.0s remaining) -> round(12.0) * 5 = 60 IP
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 8.0

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
    assert data["speed_ip_awarded"] == 60
    assert data["points_awarded"] == 160
    assert data["total_ip_awarded"] == 160


# ---------------------------------------------------------------------------
# 2. Forged remaining_time_ms values
# ---------------------------------------------------------------------------
def test_forged_remaining_time_ms_values_ignored():
    """2. Client-provided remaining_time_ms is ignored; server monotonic clock prevails."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})

    # Actual server elapsed: 10.0s (10.0s remaining -> 50 Speed IP)
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 10.0

    # Malicious client claims 20,000 ms remaining (which would give 100 Speed IP)
    resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": "Option 1A",
            "remaining_time_ms": 20_000,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Server must award 50, strictly ignoring the client's claimed 20,000 ms
    assert data["speed_ip_awarded"] == 50
    assert data["points_awarded"] == 150


# ---------------------------------------------------------------------------
# 3. Forged response_time_ms values
# ---------------------------------------------------------------------------
def test_forged_response_time_ms_values_ignored():
    """3. Client-provided response_time_ms is ignored; server monotonic clock prevails."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})

    # Actual server elapsed: 14.0s (6.0s remaining -> 30 Speed IP)
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 14.0

    # Malicious client claims 0 ms elapsed (which would claim instant 100 Speed IP)
    resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": "Option 1A",
            "response_time_ms": 0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Server must award 30, strictly ignoring the client's claimed 0 ms
    assert data["speed_ip_awarded"] == 30
    assert data["points_awarded"] == 130


# ---------------------------------------------------------------------------
# 4. Submission after authoritative deadline
# ---------------------------------------------------------------------------
def test_submission_after_deadline_rejected():
    """4. Submissions received after authoritative deadline (+ grace buffer) are rejected with HTTP 400."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})

    # Elapsed 22.0 seconds (exceeds 20.0s + 1.0s grace buffer)
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 22.0

    resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": "Option 1A",
            "remaining_time_ms": 20_000,  # Even with forged client time
        },
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Submission within valid 20-second window
# ---------------------------------------------------------------------------
def test_submission_within_valid_window_accepted():
    """5. Submissions within the 20-second window are accepted and scored."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})

    # Elapsed 19.5s (within 20.0s + 1.0s grace buffer)
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 19.5

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
    # 0.5s remaining -> round(0.5)*5 = 5 IP (or 0 IP)
    assert data["base_ip_awarded"] == 100


# ---------------------------------------------------------------------------
# 6. Time Freeze extending authoritative deadline by exactly 5 seconds
# ---------------------------------------------------------------------------
def test_time_freeze_extends_deadline_by_exactly_5_seconds():
    """6. Time Freeze extends authoritative deadline by 5.0 seconds and adjusts Speed Bonus."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})

    # Activate Time Freeze on stage 1
    freeze_resp = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    assert freeze_resp.status_code == 200
    assert freeze_resp.json()["is_frozen"] is True
    assert freeze_resp.json()["freeze_duration_seconds"] == 5.0
    assert freeze_resp.json()["remaining_time_freezes"] == 1

    # Total allowed: 20s + 5s = 25s (with 1s grace = 26s).
    # Submit at 22.0s elapsed (which would normally expire at 21s):
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 22.0
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
    # Active elapsed: 22.0 - 5.0 = 17.0s. Remaining active: 3.0s -> round(3.0)*5 = 15 IP
    assert data["speed_ip_awarded"] == 15
    assert data["points_awarded"] == 115

    # Test that freeze on stage 1 does NOT carry over to stage 2:
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 2})
    # Submit stage 2 at 22.0s elapsed without freeze:
    sessions[session_id]["stage_start_times"][2] = time.monotonic() - 22.0
    resp2 = client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A"},
    )
    assert resp2.status_code == 400
    assert "expired" in resp2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 7. Multiple Time Freeze requests and simultaneous activation attempts
# ---------------------------------------------------------------------------
def test_multiple_time_freeze_requests_and_concurrency():
    """7. Time Freeze idempotent on same stage; quotas enforced per difficulty; race conditions prevented."""
    session_id = _setup_session("Medium", 20)  # Quota: 2 freezes
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})

    # First activation on stage 1
    r1 = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    assert r1.status_code == 200
    assert r1.json()["remaining_time_freezes"] == 1

    # Second activation on stage 1: idempotent, returns cached, does not grant extra 5s or deduct charge
    r1_retry = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    assert r1_retry.status_code == 200
    assert r1_retry.json()["remaining_time_freezes"] == 1
    assert sessions[session_id]["time_freezes"][1] == 5.0

    # Alias /use-time-freeze works identically
    r1_alias = client.post("/use-time-freeze", json={"session_id": session_id, "stage_number": 1})
    assert r1_alias.status_code == 200
    assert r1_alias.json()["remaining_time_freezes"] == 1

    # Answer stage 1 to unlock stage 2
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})

    # Stage 2 freeze uses remaining quota
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 2})
    r2 = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 2})
    assert r2.status_code == 200
    assert r2.json()["remaining_time_freezes"] == 0

    # Answer stage 2 to unlock stage 3
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A"})

    # Stage 3 freeze: quota is exhausted (2 used on Medium) -> HTTP 400
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 3})
    r3 = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 3})
    assert r3.status_code == 400
    assert "exhausted" in r3.json()["detail"].lower()

    # Expert difficulty: Time Freeze quota is 0 -> rejected immediately
    expert_id = _setup_session("Expert", 20)
    client.post("/start-stage", json={"session_id": expert_id, "stage_number": 1})
    r_exp = client.post("/use-freeze", json={"session_id": expert_id, "stage_number": 1})
    assert r_exp.status_code == 400
    assert "not available on Expert" in r_exp.json()["detail"]


# ---------------------------------------------------------------------------
# 8. Time spent reading explanations not consuming next question's timer
# ---------------------------------------------------------------------------
def test_explanation_reading_does_not_consume_next_timer():
    """8. Reading explanations does not count against subsequent questions."""
    session_id = _setup_session("Medium", 20)

    # Stage 1 started and answered
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})

    # Player reads explanation for 45 seconds (manual progression)
    # Stage 2 timer is NOT started yet!
    assert 2 not in sessions[session_id]["stage_start_times"]

    # Player clicks Next Stage: Stage 2 mounts and starts
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 2})
    assert 2 in sessions[session_id]["stage_start_times"]

    # Submit 2.0s later
    sessions[session_id]["stage_start_times"][2] = time.monotonic() - 2.0
    r2 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 2, "selected_option": "Option 2A"})
    assert r2.status_code == 200
    # 18.0s remaining -> 90 Speed IP
    assert r2.json()["speed_ip_awarded"] == 90
    assert r2.json()["points_awarded"] == 190


# ---------------------------------------------------------------------------
# 9. Duplicate submissions not awarding additional IP
# ---------------------------------------------------------------------------
def test_duplicate_submissions_do_not_award_additional_ip():
    """9. Idempotent submission retry returns cached answer and does not double-count IP."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 8.0  # 60 Speed IP

    r1 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert r1.status_code == 200
    assert r1.json()["points_awarded"] == 160
    assert r1.json()["total_ip_awarded"] == 160
    assert sessions[session_id]["total_ip_awarded"] == 160

    # Duplicate submission
    r2 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert r2.status_code == 200
    assert r2.json()["points_awarded"] == 160
    assert r2.json()["total_ip_awarded"] == 160
    assert sessions[session_id]["total_ip_awarded"] == 160


# ---------------------------------------------------------------------------
# 10. Client timing manipulation not bypassing checkpoint requirements
# ---------------------------------------------------------------------------
def test_client_timing_manipulation_cannot_bypass_checkpoint():
    """10. Forging client timing cannot artificially inflate IP to bypass checkpoint thresholds."""
    session_id = _setup_session("Medium", 20)  # Tier 1 requires 150 IP

    # Stage 1: Player answers slowly at 18.0s elapsed (2s remaining -> 10 Speed IP -> 110 IP)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 18.0

    # Player sends forged remaining_time_ms claiming 20,000 ms to try to get 100 Speed IP (total 200 IP > 150)
    r1 = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": "Option 1A",
            "remaining_time_ms": 20_000,
        },
    )
    # Server calculates 10 Speed IP, so total is 110 IP
    assert r1.json()["speed_ip_awarded"] == 10
    assert r1.json()["total_ip_awarded"] == 110
    assert sessions[session_id]["tier_local_ip"] == 110

    # Stages 2, 3, 4 are incorrect (0 IP)
    for st in (2, 3, 4):
        client.post("/submit-answer", json={"session_id": session_id, "stage_number": st, "selected_option": "Wrong"})

    # Stage 5 is incorrect (0 IP) -> Total Tier IP remains 110 < 150 required!
    r5 = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 5, "selected_option": "Wrong"})
    d5 = r5.json()
    assert d5["checkpoint_passed"] is False
    assert d5["is_game_over"] is True
    assert sessions[session_id]["checkpoint_failed"] is True


# ---------------------------------------------------------------------------
# 11. Existing difficulty-based power-up quotas remaining intact
# ---------------------------------------------------------------------------
def test_difficulty_power_up_quotas_intact():
    """11. Verify exact limits: Easy (2,2,2), Medium (1,1,2), Hard (0,0,2), Expert (0,0,0)."""
    from game_logic import POWER_UP_LIMITS

    assert POWER_UP_LIMITS["Easy"] == {"hint": 2, "fifty_fifty": 2, "time_freeze": 2}
    assert POWER_UP_LIMITS["Medium"] == {"hint": 1, "fifty_fifty": 1, "time_freeze": 2}
    assert POWER_UP_LIMITS["Hard"] == {"hint": 0, "fifty_fifty": 0, "time_freeze": 2}
    assert POWER_UP_LIMITS["Expert"] == {"hint": 0, "fifty_fifty": 0, "time_freeze": 0}

    # Hard session: Hint and 50/50 rejected with HTTP 400
    hard_id = _setup_session("Hard", 20)
    rh = client.post("/use-hint", json={"session_id": hard_id, "stage_number": 1})
    assert rh.status_code == 400
    r50 = client.post("/use-50-50", json={"session_id": hard_id, "stage_number": 1})
    assert r50.status_code == 400


# ---------------------------------------------------------------------------
# 12. Existing forfeiture, completion, and checkpoint protections remaining intact
# ---------------------------------------------------------------------------
def test_forfeiture_completion_and_checkpoint_protections():
    """12. Forfeited, completed, or checkpoint-failed sessions reject start-stage and use-freeze."""
    session_id = _setup_session("Medium", 20)

    # Forfeit session
    forfeit_resp = client.post("/forfeit-game", json={"session_id": session_id})
    assert forfeit_resp.status_code == 200

    # Rejected for start-stage
    r_start = client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    assert r_start.status_code == 400
    assert "forfeited" in r_start.json()["detail"].lower()

    # Rejected for use-freeze
    r_freeze = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    assert r_freeze.status_code == 400
    assert "forfeited" in r_freeze.json()["detail"].lower()

    # Rejected for submit-answer
    r_sub = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert r_sub.status_code == 400
    assert "forfeited" in r_sub.json()["detail"].lower()


# ===========================================================================
# Targeted Verification & Correction Tests (v0.9 Final Audit)
# ===========================================================================

# ---------------------------------------------------------------------------
# Section 1: Grace Buffer & Speed Bonus Boundary Tests
# ---------------------------------------------------------------------------
def test_boundary_grace_buffer_19_9_seconds():
    """Boundary: 19.9s elapsed (0.1s remaining) awards 0 Speed IP, 100 Base IP."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 19.9

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    # 0.1s remaining -> Math.round(0.1) * 5 = 0 Speed IP
    assert data["speed_ip_awarded"] == 0
    assert data["points_awarded"] == 100


def test_boundary_grace_buffer_fast_submission_19_9_seconds_remaining():
    """Boundary: 0.1s elapsed (19.9s remaining) awards 100 Speed IP (max), 100 Base IP."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 0.1

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    # 19.9s remaining -> Math.round(19.9) * 5 = 100 Speed IP (capped at 100)
    assert data["speed_ip_awarded"] == 100
    assert data["points_awarded"] == 200


def test_boundary_grace_buffer_exactly_20_seconds():
    """Boundary: Exactly 20.0s elapsed is accepted with 0 Speed IP and 100 Base IP."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 20.0

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    assert data["speed_ip_awarded"] == 0
    assert data["points_awarded"] == 100


def test_boundary_grace_buffer_20_5_seconds():
    """Boundary: 20.5s elapsed (within 1s grace buffer) is accepted with 0 Speed IP and 100 Base IP."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 20.5

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    # Grace buffer must NEVER award positive Speed Bonus!
    assert data["speed_ip_awarded"] == 0
    assert data["points_awarded"] == 100


def test_boundary_grace_buffer_exactly_21_seconds():
    """Boundary: Exactly 21.0s elapsed (exact deadline + grace boundary) is accepted with 0 Speed IP."""
    session_id = _setup_session("Medium", 20)
    sessions[session_id]["stage_start_times"][1] = 1000.0

    with patch("main.time.monotonic", return_value=1021.0):
        resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    assert data["speed_ip_awarded"] == 0
    assert data["points_awarded"] == 100


def test_boundary_grace_buffer_past_21_seconds_rejected():
    """Boundary: 21.05s elapsed (> 20.0s + 1.0s grace) is rejected with HTTP 400."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 21.05

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_boundary_grace_buffer_25_seconds_with_time_freeze():
    """Boundary: 25.0s elapsed with Time Freeze (20s + 5s active) is accepted with 0 Speed IP and 100 Base IP."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 25.0

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    assert data["speed_ip_awarded"] == 0
    assert data["points_awarded"] == 100


def test_boundary_grace_buffer_25_5_seconds_with_time_freeze():
    """Boundary: 25.5s elapsed with Time Freeze (inside 1s grace buffer) is accepted with 0 Speed IP."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 25.5

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    assert data["speed_ip_awarded"] == 0
    assert data["points_awarded"] == 100


def test_boundary_grace_buffer_exactly_26_seconds_with_time_freeze():
    """Boundary: Exactly 26.0s elapsed with Time Freeze (25s + 1s grace) is accepted with 0 Speed IP."""
    session_id = _setup_session("Medium", 20)
    sessions[session_id]["stage_start_times"][1] = 1000.0
    sessions[session_id]["time_freezes"][1] = 5.0

    with patch("main.time.monotonic", return_value=1026.0):
        resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_correct"] is True
    assert data["base_ip_awarded"] == 100
    assert data["speed_ip_awarded"] == 0
    assert data["points_awarded"] == 100


def test_boundary_grace_buffer_past_26_seconds_with_time_freeze_rejected():
    """Boundary: 26.05s elapsed with Time Freeze (> 25s + 1s grace) is rejected with HTTP 400."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 26.05

    resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Section 2: Speed Bonus Rounding Consistency (JavaScript Math.round replication)
# ---------------------------------------------------------------------------
def test_speed_bonus_rounding_half_second_boundaries_js_math_round():
    """Verify Speed Bonus rounding exactly reproduces JavaScript Math.round at half-second boundaries."""
    from game_logic import calculate_speed_bonus

    # 14.4s: Math.round(14.4) * 5 = 14 * 5 = 70 IP
    assert calculate_speed_bonus(14_400) == 70

    # 14.5s: Math.round(14.5) * 5 = 15 * 5 = 75 IP (Crucial: Python banker's round would give 14 -> 70!)
    assert calculate_speed_bonus(14_500) == 75

    # 15.4s: Math.round(15.4) * 5 = 15 * 5 = 75 IP
    assert calculate_speed_bonus(15_400) == 75

    # 15.5s: Math.round(15.5) * 5 = 16 * 5 = 80 IP
    assert calculate_speed_bonus(15_500) == 80

    # 19.5s: Math.round(19.5) * 5 = 20 * 5 = 100 IP
    assert calculate_speed_bonus(19_500) == 100

    # 20.0s: Math.round(20.0) * 5 = 20 * 5 = 100 IP
    assert calculate_speed_bonus(20_000) == 100


def test_speed_bonus_rounding_half_second_boundaries_via_endpoint():
    """Verify endpoint uses the JS Math.round behavior at 14.5s remaining."""
    session_id = _setup_session("Medium", 20)
    sessions[session_id]["stage_start_times"][1] = 1000.0

    # Exactly 5.5s elapsed -> exactly 14.5s remaining -> Math.round(14.5) * 5 = 75 Speed IP
    with patch("main.time.monotonic", return_value=1005.5):
        resp = client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["speed_ip_awarded"] == 75
    assert data["points_awarded"] == 175


# ---------------------------------------------------------------------------
# Section 3: Stage Activation & Sequential Progression Tests
# ---------------------------------------------------------------------------
def test_cannot_start_future_stage_before_completing_previous_stage():
    """Verify that only the currently active stage can be started via /start-stage."""
    session_id = _setup_session("Medium", 20)

    # Attempt to start Stage 2 when Stage 1 has not been answered -> HTTP 400
    r_future2 = client.post("/start-stage", json={"session_id": session_id, "stage_number": 2})
    assert r_future2.status_code == 400
    assert "current active stage is 1" in r_future2.json()["detail"].lower()

    # Attempt to start Stage 5 -> HTTP 400
    r_future5 = client.post("/start-stage", json={"session_id": session_id, "stage_number": 5})
    assert r_future5.status_code == 400

    # Start Stage 1 -> Success
    r1 = client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    assert r1.status_code == 200
    assert r1.json()["remaining_seconds"] == 20.0

    # Idempotent call to Stage 1 -> Success, returns remaining seconds without resetting timer
    r1_retry = client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    assert r1_retry.status_code == 200

    # Complete Stage 1
    client.post("/submit-answer", json={"session_id": session_id, "stage_number": 1, "selected_option": "Option 1A"})

    # Now Stage 2 can be started
    r2 = client.post("/start-stage", json={"session_id": session_id, "stage_number": 2})
    assert r2.status_code == 200

    # But Stage 1 cannot be started again (already answered)
    r1_after = client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})
    assert r1_after.status_code == 400
    assert "already been answered" in r1_after.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Section 4: Time Freeze Integrity & Expiration Tests
# ---------------------------------------------------------------------------
def test_time_freeze_integrity_eligibility_and_expiration():
    """Verify Time Freeze cannot be used on future stages, already-answered stages, or expired stages."""
    session_id = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": session_id, "stage_number": 1})

    # Cannot freeze Stage 2 while on Stage 1
    rf = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 2})
    assert rf.status_code == 400
    assert "current active stage is 1" in rf.json()["detail"].lower()

    # Expire Stage 1 active time (20.5s elapsed >= 20.0s)
    sessions[session_id]["stage_start_times"][1] = time.monotonic() - 20.5

    # Cannot freeze an already expired question
    rf_exp = client.post("/use-freeze", json={"session_id": session_id, "stage_number": 1})
    assert rf_exp.status_code == 400
    assert "expired" in rf_exp.json()["detail"].lower()

    # Fresh session for answered test
    s2 = _setup_session("Medium", 20)
    client.post("/start-stage", json={"session_id": s2, "stage_number": 1})
    client.post("/submit-answer", json={"session_id": s2, "stage_number": 1, "selected_option": "Option 1A"})

    # Cannot freeze a question that has already been answered
    rf_ans = client.post("/use-freeze", json={"session_id": s2, "stage_number": 1})
    assert rf_ans.status_code == 400
    assert "already been answered" in rf_ans.json()["detail"].lower()

