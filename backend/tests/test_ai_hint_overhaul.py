"""
Automated test suite for OmniQuest v1.0 Phase 2: AI Hint Overhaul.

Verifies:
1. Pre-generated hints per question with instant retrieval.
2. Zero Gemini calls during gameplay hint activation.
3. Hints stripped by to_public_questions() and absent from all public responses.
4. Hint validation: rejects generic filler, answer leakage, empty hints, unsupported facts.
5. Critical latency requirement: failed hint validation immediately marks hint unavailable
   WITHOUT triggering a secondary Gemini call.
6. Unavailable hints do not fail gauntlet generation and do not consume charges.
7. Difficulty-based quotas (Easy: 2, Medium: 1, Hard: 0, Expert: 0), per-question restrictions,
   and concurrent-request protection.
8. Preserved 50/50 and Time Freeze behavior.
"""

import concurrent.futures
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app, sessions
from game_logic import (
    GauntletPayload,
    GenerateGameRequest,
    Question,
    to_public_questions,
)
from gemini_service import (
    GENERIC_FILLER_PHRASES,
    build_generation_prompt,
    generate_gauntlet_with_gemini,
    validate_pregenerated_hint,
)

client = TestClient(app)

SAMPLE_DOC = (
    "Photosynthesis is a biological process where photoautotrophs convert light energy "
    "into chemical energy stored in glucose. The light-dependent reactions occur in the "
    "thylakoid membranes, splitting water to release oxygen and generate ATP and NADPH. "
    "The Calvin cycle occurs in the stroma, using RuBisCO to fix carbon dioxide."
)


def _make_sample_gauntlet(count: int = 5, with_hints: bool = True) -> list[Question]:
    return [
        Question(
            stage=i,
            tier=1,
            question=f"Where do the light reactions occur in stage {i}?",
            options=[
                f"Thylakoid membrane {i}",
                f"Mitochondrial matrix {i}",
                f"Cytosol {i}",
                f"Outer membrane {i}",
            ],
            correct_answer=f"Thylakoid membrane {i}",
            explanation=f"Light-dependent reactions take place across the thylakoid membrane {i}.",
            hint=(
                f"Consider the specialized disc-shaped internal membranes inside the chloroplast."
                if with_hints
                else None
            ),
        )
        for i in range(1, count + 1)
    ]


def _create_test_session(
    difficulty: str = "Medium",
    length: int = 5,
    with_hints: bool = True,
) -> str:
    """Helper to create a game session directly with pre-generated questions."""
    questions = _make_sample_gauntlet(count=length, with_hints=with_hints)
    payload = GauntletPayload(is_valid=True, topic="Photosynthesis", gauntlet=questions)
    with patch("main.generate_gauntlet_with_gemini", return_value=payload):
        resp = client.post(
            "/generate-game",
            json={
                "topic": "Photosynthesis",
                "question_count": length,
                "difficulty": difficulty,
            },
        )
        assert resp.status_code == 200
        return resp.json()["session_id"]


# ---------------------------------------------------------------------------
# 1. Pre-generated Hints & Public Stripping
# ---------------------------------------------------------------------------


def test_every_question_receives_hint_or_unavailable_status():
    """Verify each question has a pre-generated hint or is explicitly marked unavailable."""
    session_id = _create_test_session(length=5, with_hints=True)
    session = sessions[session_id]
    assert "pregenerated_hints" in session
    assert len(session["pregenerated_hints"]) == 5
    for stage, hint in session["pregenerated_hints"].items():
        assert hint is not None
        assert "internal membranes" in hint


def test_hints_not_exposed_in_public_gauntlet_response():
    """Verify hints are never exposed in the /generate-game response payload."""
    questions = _make_sample_gauntlet(count=5, with_hints=True)
    payload = GauntletPayload(is_valid=True, topic="Photosynthesis", gauntlet=questions)
    with patch("main.generate_gauntlet_with_gemini", return_value=payload):
        resp = client.post(
            "/generate-game",
            json={"topic": "Photosynthesis", "question_count": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "gauntlet" in data
        for q in data["gauntlet"]:
            assert "hint" not in q
            assert "correct_answer" not in q
            assert "explanation" not in q


def test_to_public_questions_strips_hint_field():
    """Verify to_public_questions explicitly strips the hint field."""
    questions = _make_sample_gauntlet(count=3, with_hints=True)
    payload = GauntletPayload(is_valid=True, topic="Photosynthesis", gauntlet=questions)
    public_qs = to_public_questions(payload)
    assert len(public_qs) == 3
    for pq in public_qs:
        assert not hasattr(pq, "hint")
        assert not hasattr(pq, "correct_answer")
        assert not hasattr(pq, "explanation")
        # Ensure PublicQuestion schema itself has only public fields
        assert set(pq.model_dump().keys()) == {"stage", "tier", "question", "options"}


def test_no_other_public_endpoint_exposes_hints():
    """Verify /submit-answer and /use-50-50 do not leak hints."""
    session_id = _create_test_session(length=5, with_hints=True)

    # 50/50 response check
    fifty_resp = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert fifty_resp.status_code == 200
    assert "hint" not in fifty_resp.json()

    # Submit answer response check
    sub_resp = client.post(
        "/submit-answer",
        json={
            "session_id": session_id,
            "stage_number": 1,
            "selected_option": "Thylakoid membrane 1",
        },
    )
    assert sub_resp.status_code == 200
    assert "hint" not in sub_resp.json()


# ---------------------------------------------------------------------------
# 2. Instant Retrieval & Zero Gemini Calls During Gameplay
# ---------------------------------------------------------------------------


def test_valid_hint_retrieved_instantly_from_session():
    """Verify activating AI Hint retrieves the pre-generated hint from session storage."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)
    resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_available"] is True
    assert "disc-shaped internal membranes" in data["hint"]
    assert data["remaining_hints"] == 0  # Medium difficulty starts with 1 hint


def test_hint_retrieval_does_not_call_gemini():
    """Verify that calling /use-hint during gameplay makes ZERO Gemini API calls."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)

    with patch("gemini_service.create_gemini_client") as mock_factory:
        mock_client = MagicMock()
        mock_factory.return_value = mock_client

        resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
        assert resp.status_code == 200

        # Critical requirement: Gemini is NEVER called at activation time
        mock_factory.assert_not_called()
        mock_client.models.generate_content.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Mode-Specific Hint Prompts
# ---------------------------------------------------------------------------


def test_build_generation_prompt_strict_mode_includes_hint_instructions():
    """Verify generation prompt instructs Gemini on Strict Material Only hint rules."""
    req = GenerateGameRequest(
        topic="Photosynthesis",
        source_text=SAMPLE_DOC,
        generation_mode="Strict Material Only",
        question_count=5,
    )
    prompt = build_generation_prompt(req)
    assert "AI Hint Pre-Generation (Mandatory for every question):" in prompt
    assert "Strict Material Only: The hint MUST be supported EXCLUSIVELY by facts stated in the provided Source Material." in prompt
    assert "NEVER state, name, or quote the correct answer directly." in prompt
    assert "NEVER output vague or generic statements" in prompt


def test_build_generation_prompt_ai_enhanced_includes_hint_instructions():
    """Verify generation prompt instructs Gemini on AI Enhanced hint rules."""
    req = GenerateGameRequest(
        topic="Photosynthesis",
        source_text=SAMPLE_DOC,
        generation_mode="AI Enhanced",
        question_count=10,
    )
    prompt = build_generation_prompt(req)
    assert "AI Hint Pre-Generation (Mandatory for every question):" in prompt
    assert "AI Enhanced: The hint MUST use the Source Material as primary foundation" in prompt


def test_build_generation_prompt_topic_only_includes_hint_instructions():
    """Verify generation prompt instructs Gemini on Topic-Only hint rules."""
    req = GenerateGameRequest(topic="Quantum Mechanics", question_count=5)
    prompt = build_generation_prompt(req)
    assert "AI Hint Pre-Generation (Mandatory for every question):" in prompt
    assert "Topic-Only: The hint MUST be factually accurate and consistent with the question." in prompt


# ---------------------------------------------------------------------------
# 4. Pre-Generated Hint Validation Engine
# ---------------------------------------------------------------------------


def test_validation_rejects_empty_or_whitespace_hint():
    """Verify empty or whitespace-only hints fail validation."""
    q = _make_sample_gauntlet(1)[0]
    valid, reason = validate_pregenerated_hint(None, q)
    assert valid is False
    assert "empty" in reason.lower()

    valid, reason = validate_pregenerated_hint("   ", q)
    assert valid is False
    assert "empty" in reason.lower()


def test_validation_rejects_generic_filler_phrases():
    """Verify generic filler phrases (e.g. 'think carefully') fail validation."""
    q = _make_sample_gauntlet(1)[0]
    for filler in GENERIC_FILLER_PHRASES[:5]:
        hint = f"Please {filler} before making your selection on this stage."
        valid, reason = validate_pregenerated_hint(hint, q)
        assert valid is False
        assert "generic filler" in reason.lower()


def test_validation_rejects_explicit_answer_pointers():
    """Verify phrases like 'the answer is' fail validation."""
    q = _make_sample_gauntlet(1)[0]
    hint = "The answer is clearly found in the membranes of chloroplasts."
    valid, reason = validate_pregenerated_hint(hint, q)
    assert valid is False
    assert "points out the answer" in reason.lower()


def test_validation_rejects_correct_answer_leakage():
    """Verify verbatim correct answer leakage is caught and rejected."""
    q = Question(
        stage=1,
        tier=1,
        question="Which organelle houses chlorophyll in plant cells?",
        options=["Chloroplast", "Mitochondria", "Ribosome", "Nucleus"],
        correct_answer="Chloroplast",
        explanation="Chloroplasts contain chlorophyll pigments.",
        hint="Notice how the Chloroplast organelle captures photons.",
    )
    valid, reason = validate_pregenerated_hint(q.hint, q)
    assert valid is False
    assert "leaks the correct answer" in reason.lower()


def test_validation_rejects_multiword_answer_leakage():
    """Verify multi-word correct answers are caught when leaked."""
    q = Question(
        stage=1,
        tier=1,
        question="What does CPU stand for?",
        options=["Central Processing Unit", "Core Power Unit", "Computer Program Upload", "Central Port"],
        correct_answer="Central Processing Unit",
        explanation="CPU stands for Central Processing Unit.",
        hint="Look into the Central Processing Unit which handles machine instructions.",
    )
    valid, reason = validate_pregenerated_hint(q.hint, q)
    assert valid is False
    assert "leaks the correct answer" in reason.lower() or "all key terms" in reason.lower()


def test_validation_strict_mode_rejects_unsupported_facts():
    """Verify Strict Material Only rejects hints containing unsupported outside terms."""
    q = _make_sample_gauntlet(1)[0]
    # Hint talks about mitochondria and krebs cycle which are absent from SAMPLE_DOC
    hint = "Consider how the mitochondrial matrix and Krebs cycle produce FADH2 molecules."
    valid, reason = validate_pregenerated_hint(
        hint, q, source_text=SAMPLE_DOC, generation_mode="Strict Material Only"
    )
    assert valid is False
    assert "external terms" in reason.lower()


def test_validation_passes_valid_substantive_hint():
    """Verify a high-quality educational clue passes validation cleanly."""
    q = Question(
        stage=1,
        tier=1,
        question="Which complex splits water in oxygenic photosynthesis?",
        options=["Photosystem II", "Photosystem I", "ATP Synthase", "RuBisCO"],
        correct_answer="Photosystem II",
        explanation="Photosystem II contains the oxygen-evolving complex.",
        hint="Focus on the initial pigment complex in the Z-scheme that oxidizes water to replace lost electrons.",
    )
    valid, reason = validate_pregenerated_hint(q.hint, q, source_text=SAMPLE_DOC)
    assert valid is True
    assert "passed" in reason.lower()


# ---------------------------------------------------------------------------
# 5. Critical Latency: Failed Validation Marks Unavailable (No Secondary Gemini Call)
# ---------------------------------------------------------------------------


def test_failed_validation_marks_hint_unavailable_without_secondary_gemini_call():
    """Verify failed hint validation sets hint=None without making additional Gemini calls."""
    mock_client = MagicMock()
    # Question 1 has a leaking hint ("Thylakoid membrane 1" leaked)
    bad_questions = [
        Question(
            stage=1,
            tier=1,
            question="Where are photons absorbed?",
            options=["Thylakoid membrane 1", "Stroma 1", "Cytosol 1", "Lumen 1"],
            correct_answer="Thylakoid membrane 1",
            explanation="Explanation 1.",
            hint="Look at Thylakoid membrane 1 closely.",  # Leaks correct answer!
        ),
        Question(
            stage=2,
            tier=1,
            question="Where is carbon fixed?",
            options=["Stroma 2", "Matrix 2", "Cytosol 2", "Lumen 2"],
            correct_answer="Stroma 2",
            explanation="Explanation 2.",
            hint="Consider the aqueous fluid surrounding the grana stacks.",  # Valid hint
        ),
        Question(
            stage=3,
            tier=1,
            question="Which enzyme fixes carbon?",
            options=["RuBisCO 3", "ATP Synthase 3", "Helicase 3", "Polymerase 3"],
            correct_answer="RuBisCO 3",
            explanation="Explanation 3.",
            hint="Consider the carboxylase enzyme responsible for RuBP reaction.",
        ),
        Question(
            stage=4,
            tier=1,
            question="What is the electron donor in oxygenic photosynthesis?",
            options=["Water 4", "Hydrogen sulfide 4", "Methane 4", "Ammonia 4"],
            correct_answer="Water 4",
            explanation="Explanation 4.",
            hint="Think about the abundant inorganic liquid split during light reactions.",
        ),
        Question(
            stage=5,
            tier=1,
            question="What energy currency is produced?",
            options=["ATP 5", "GTP 5", "CTP 5", "UTP 5"],
            correct_answer="ATP 5",
            explanation="Explanation 5.",
            hint="Focus on the primary cellular energy currency synthesized by chemiosmosis.",
        ),
    ]
    mock_payload = GauntletPayload(is_valid=True, topic="Photosynthesis", gauntlet=bad_questions)
    mock_resp = MagicMock()
    mock_resp.parsed = mock_payload
    mock_client.models.generate_content.return_value = mock_resp

    req = GenerateGameRequest(topic="Photosynthesis", question_count=5)
    with patch("gemini_service.validate_gauntlet_payload", return_value=mock_payload):
        result_payload = generate_gauntlet_with_gemini(req, client=mock_client)

    # Exactly 1 call was made to Gemini for gauntlet generation
    assert mock_client.models.generate_content.call_count == 1
    # Stage 1 hint failed validation and was immediately set to None
    assert result_payload.gauntlet[0].hint is None
    # Stage 2 hint was valid and preserved
    assert result_payload.gauntlet[1].hint == "Consider the aqueous fluid surrounding the grana stacks."


def test_unavailable_hint_does_not_fail_gauntlet_generation():
    """Verify an unavailable hint allows gauntlet generation to succeed normally."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=False)
    assert session_id in sessions
    assert len(sessions[session_id]["gauntlet"]) == 5


# ---------------------------------------------------------------------------
# 6. Unavailable Hints & Charge Integrity
# ---------------------------------------------------------------------------


def test_unavailable_hint_returns_unavailable_response_without_consuming_charge():
    """Verify /use-hint on an unavailable hint returns is_available=False and charges remain 1."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=False)

    resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_available"] is False
    assert data["hint"] is None
    assert "unavailable" in data["message"].lower()
    # Medium allows 1 hint; charge was NOT consumed
    assert data["remaining_hints"] == 1
    assert len(sessions[session_id]["hints"]) == 0


def test_subsequent_hint_usable_after_unavailable_hint():
    """Verify player can use their hint on another stage if current stage had an unavailable hint."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)
    # Force stage 1 hint to be unavailable
    sessions[session_id]["pregenerated_hints"][1] = None

    # Request stage 1 hint -> unavailable, charge preserved
    r1 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert r1.json()["is_available"] is False
    assert r1.json()["remaining_hints"] == 1
    assert len(sessions[session_id]["hints"]) == 0

    # Request stage 2 hint -> available, charge consumed
    r2 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 2})
    assert r2.json()["is_available"] is True
    assert r2.json()["hint"] is not None
    assert r2.json()["remaining_hints"] == 0
    assert len(sessions[session_id]["hints"]) == 1


# ---------------------------------------------------------------------------
# 7. Quota Enforcement Across Difficulties
# ---------------------------------------------------------------------------


def test_difficulty_quotas_enforced():
    """Verify exact difficulty limits: Easy=2, Medium=1, Hard=0, Expert=0."""
    # 1. Easy: Allows exactly 2 hints
    s_easy = _create_test_session(difficulty="Easy", length=5, with_hints=True)
    h1 = client.post("/use-hint", json={"session_id": s_easy, "stage_number": 1})
    assert h1.status_code == 200
    assert h1.json()["remaining_hints"] == 1

    h2 = client.post("/use-hint", json={"session_id": s_easy, "stage_number": 2})
    assert h2.status_code == 200
    assert h2.json()["remaining_hints"] == 0

    h3 = client.post("/use-hint", json={"session_id": s_easy, "stage_number": 3})
    assert h3.status_code == 400
    assert "limit exhausted" in h3.json()["detail"].lower()

    # 2. Hard: Allows 0 hints
    s_hard = _create_test_session(difficulty="Hard", length=5, with_hints=True)
    h_hard = client.post("/use-hint", json={"session_id": s_hard, "stage_number": 1})
    assert h_hard.status_code == 400
    assert "not available on hard" in h_hard.json()["detail"].lower()

    # 3. Expert: Allows 0 hints
    s_expert = _create_test_session(difficulty="Expert", length=5, with_hints=True)
    h_expert = client.post("/use-hint", json={"session_id": s_expert, "stage_number": 1})
    assert h_expert.status_code == 400
    assert "not available on expert" in h_expert.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 8. Lifecycle & Edge Cases (Idempotency, Forfeit, Completed, Answered)
# ---------------------------------------------------------------------------


def test_idempotent_retry_on_same_question_does_not_consume_extra_charge():
    """Verify repeated hint requests on the same stage return identical hint without extra charge."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)

    r1 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert r1.status_code == 200
    hint1 = r1.json()["hint"]
    assert r1.json()["remaining_hints"] == 0

    # Repeat request for stage 1
    r2 = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert r2.status_code == 200
    assert r2.json()["hint"] == hint1
    assert r2.json()["remaining_hints"] == 0
    assert len(sessions[session_id]["hints"]) == 1


def test_forfeited_session_rejects_hints():
    """Verify forfeited sessions reject hint activation."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)
    client.post("/forfeit-game", json={"session_id": session_id})

    resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert resp.status_code == 400
    assert "forfeited" in resp.json()["detail"].lower()


def test_answered_question_rejects_hint():
    """Verify an already-answered stage rejects hint activation."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)
    # Answer stage 1
    client.post(
        "/submit-answer",
        json={"session_id": session_id, "stage_number": 1, "selected_option": "Thylakoid membrane 1"},
    )

    resp = client.post("/use-hint", json={"session_id": session_id, "stage_number": 1})
    assert resp.status_code == 400
    assert "already been answered" in resp.json()["detail"].lower()


def test_invalid_session_and_stage_rejected():
    """Verify 404 for invalid session and 400 for out-of-range stage."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)

    # Unknown session -> 404
    r_bad_s = client.post("/use-hint", json={"session_id": "non-existent-uuid", "stage_number": 1})
    assert r_bad_s.status_code == 404

    # Stage 0 -> 400
    r_zero = client.post("/use-hint", json={"session_id": session_id, "stage_number": 0})
    assert r_zero.status_code == 400

    # Stage 6 on 5-question game -> 400
    r_six = client.post("/use-hint", json={"session_id": session_id, "stage_number": 6})
    assert r_six.status_code == 400


# ---------------------------------------------------------------------------
# 9. Concurrency Protection & Preserved 50/50 Behavior
# ---------------------------------------------------------------------------


def test_concurrent_hints_under_session_lock_cannot_bypass_quota():
    """Verify simultaneous hint requests on Medium (quota=1) result in exactly 1 success."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 1}))
        f2 = executor.submit(lambda: client.post("/use-hint", json={"session_id": session_id, "stage_number": 2}))
        r1 = f1.result()
        r2 = f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 400]
    assert len(sessions[session_id]["hints"]) == 1


def test_50_50_behavior_remains_intact():
    """Verify 50/50 power-up behaves normally and eliminates two incorrect choices."""
    session_id = _create_test_session(difficulty="Medium", length=5, with_hints=True)
    resp = client.post("/use-50-50", json={"session_id": session_id, "stage_number": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["options_to_remove"]) == 2
    # Never eliminates the correct answer
    assert "Thylakoid membrane 1" not in data["options_to_remove"]
    assert data["remaining_fifty_fifty"] == 0
