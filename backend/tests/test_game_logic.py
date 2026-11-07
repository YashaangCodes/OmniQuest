"""
Unit tests for backend/game_logic.py.
"""

import pytest
from pydantic import ValidationError

from game_logic import (
    ALLOWED_QUESTION_COUNTS,
    DEFAULT_QUESTION_COUNT,
    GauntletPayload,
    GenerateGameRequest,
    Question,
    expected_tier_for_stage,
    get_bounded_randomness_limits,
    get_tier_checkpoints,
    get_tier_distribution,
    get_tier_target_ip,
    generate_bounded_placement_sequence,
    validate_placement_sequence,
    validate_question_count,
    validate_gauntlet_payload,
    shuffle_question_options,
    slice_fallback_gauntlet,
    sanitize_input_text,
)


def test_question_count_validation():
    for count in (5, 10, 15, 20):
        assert validate_question_count(count) == count

    for invalid in (-1, 0, 1, 4, 7, 12, 19, 21, 25, 100):
        with pytest.raises(ValueError, match="Invalid question_count"):
            validate_question_count(invalid)


def test_request_schema_validation():
    req = GenerateGameRequest(topic="Space Exploration", question_count=10)
    assert req.topic == "Space Exploration"
    assert req.question_count == 10
    assert req.generation_mode == "AI Enhanced"
    assert req.source_text is None

    # Invalid question count in request
    with pytest.raises(ValidationError):
        GenerateGameRequest(topic="Physics", question_count=7)

    # Blank topic rejected
    with pytest.raises(ValidationError):
        GenerateGameRequest(topic="   ", question_count=10)

    # Punctuation-only topic rejected
    with pytest.raises(ValidationError):
        GenerateGameRequest(topic=".....???", question_count=10)


def test_tier_mapping_for_all_counts():
    # 20 questions
    assert [expected_tier_for_stage(s, 20) for s in range(1, 21)] == (
        [1] * 5 + [2] * 5 + [3] * 5 + [4] * 5
    )

    # 15 questions
    assert [expected_tier_for_stage(s, 15) for s in range(1, 16)] == (
        [1] * 5 + [2] * 5 + [3] * 5
    )

    # 10 questions
    assert [expected_tier_for_stage(s, 10) for s in range(1, 11)] == (
        [1] * 5 + [2] * 5
    )

    # 5 questions
    assert [expected_tier_for_stage(s, 5) for s in range(1, 6)] == [1] * 5

    # Out of range stages raise ValueError
    with pytest.raises(ValueError):
        expected_tier_for_stage(0, 10)
    with pytest.raises(ValueError):
        expected_tier_for_stage(11, 10)


def test_tier_checkpoints_and_ip_target():
    assert get_tier_checkpoints(20) == [5, 10, 15]
    assert get_tier_checkpoints(15) == [5, 10]
    assert get_tier_checkpoints(10) == [5]
    assert get_tier_checkpoints(5) == []

    # Target IP for 5 questions per tier is 300 IP (60% of 500 base IP)
    assert get_tier_target_ip(5) == 300


def test_bounded_randomness_limits():
    assert get_bounded_randomness_limits(5) == (2, 2)
    assert get_bounded_randomness_limits(10) == (2, 4)
    assert get_bounded_randomness_limits(15) == (2, 5)
    assert get_bounded_randomness_limits(20) == (2, 7)


def test_bounded_randomness_sequence_generation():
    for count in (5, 10, 15, 20):
        max_consecutive, max_total = get_bounded_randomness_limits(count)
        # Test 40 iterations for each count to ensure statistical consistency
        for _ in range(40):
            seq = generate_bounded_placement_sequence(count)
            assert len(seq) == count
            assert validate_placement_sequence(seq, count)

            # Check consecutive limit: no position > max_consecutive consecutively
            for i in range(len(seq) - max_consecutive):
                assert not all(
                    seq[i + k] == seq[i] for k in range(1, max_consecutive + 1)
                )

            # Check total count limit: no position > max_total
            counts = [seq.count(opt) for opt in range(4)]
            assert all(c <= max_total for c in counts)


def _make_dummy_question(stage: int, total_stages: int) -> Question:
    tier = expected_tier_for_stage(stage, total_stages)
    opts = [f"Option A {stage}", f"Option B {stage}", f"Option C {stage}", f"Option D {stage}"]
    return Question(
        stage=stage,
        tier=tier,
        question=f"Question prompt for stage {stage}?",
        options=opts,
        correct_answer=opts[0],
        explanation=f"Explanation for stage {stage}.",
    )


def test_validate_gauntlet_payload_dynamic_counts():
    for count in (5, 10, 15, 20):
        questions = [_make_dummy_question(s, count) for s in range(1, count + 1)]
        payload = GauntletPayload(
            is_valid=True,
            topic="Test Topic",
            gauntlet=questions,
        )
        validated = validate_gauntlet_payload(payload, expected_length=count)
        assert len(validated.gauntlet) == count

    # Wrong count rejected
    questions_10 = [_make_dummy_question(s, 10) for s in range(1, 11)]
    payload_10 = GauntletPayload(is_valid=True, topic="Test", gauntlet=questions_10)
    with pytest.raises(ValueError, match="must contain exactly 5 questions"):
        validate_gauntlet_payload(payload_10, expected_length=5)


def test_shuffle_question_options_preserves_answers():
    for count in (5, 10, 15, 20):
        questions = [_make_dummy_question(s, count) for s in range(1, count + 1)]
        orig_answers = [q.correct_answer for q in questions]

        payload = GauntletPayload(
            is_valid=True,
            topic="Shuffling Test",
            gauntlet=questions,
        )
        shuffled = shuffle_question_options(payload, length=count)

        for q, orig_ans in zip(shuffled.gauntlet, orig_answers):
            assert q.correct_answer == orig_ans
            assert q.correct_answer in q.options
            assert len(q.options) == 4
            assert len(set(q.options)) == 4


def test_slice_fallback_gauntlet():
    questions_20 = [_make_dummy_question(s, 20) for s in range(1, 21)]
    full_payload = GauntletPayload(
        is_valid=True,
        topic="General Technology",
        gauntlet=questions_20,
    )

    for count in (5, 10, 15):
        sliced = slice_fallback_gauntlet(full_payload, count)
        assert len(sliced.gauntlet) == count
        for idx, q in enumerate(sliced.gauntlet, start=1):
            assert q.stage == idx
            assert q.tier == expected_tier_for_stage(idx, count)
            assert q.correct_answer in q.options
