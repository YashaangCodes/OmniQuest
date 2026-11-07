"""
Unit tests for backend/gemini_service.py.
"""

from unittest.mock import MagicMock
import pytest

from game_logic import (
    GauntletPayload,
    GenerateGameRequest,
    Question,
    expected_tier_for_stage,
)
from gemini_service import (
    InsufficientMaterialError,
    TopicRejectedError,
    build_generation_prompt,
    build_tier_description,
    generate_gauntlet_with_gemini,
)


def test_build_tier_description():
    desc_5 = build_tier_description(5)
    assert "Stages 1-5" in desc_5
    assert "Tier 1" in desc_5
    assert "Tier 2" not in desc_5

    desc_10 = build_tier_description(10)
    assert "Stages 1-5" in desc_10
    assert "Stages 6-10" in desc_10
    assert "Tier 2" in desc_10
    assert "Tier 3" not in desc_10

    desc_20 = build_tier_description(20)
    assert "Stages 1-5" in desc_20
    assert "Stages 16-20" in desc_20
    assert "Golden Challenge" in desc_20


def test_build_generation_prompt_modes():
    # 1. Topic only
    req_topic = GenerateGameRequest(topic="Quantum Mechanics", question_count=10)
    prompt_topic = build_generation_prompt(req_topic)
    assert "Quantum Mechanics" in prompt_topic
    assert "Generate exactly 10" in prompt_topic
    assert "TOPIC-BASED RULES:" in prompt_topic

    # 2. Strict Material Only
    req_strict = GenerateGameRequest(
        topic="Photosynthesis",
        question_count=5,
        source_text="Light energy is converted to chemical energy.",
        generation_mode="Strict Material Only",
    )
    prompt_strict = build_generation_prompt(req_strict)
    assert "STRICT MATERIAL ONLY RULES:" in prompt_strict
    assert "EXCLUSIVELY from the provided Source Material" in prompt_strict
    assert "Light energy is converted to chemical energy." in prompt_strict

    # 3. AI Enhanced
    req_enhanced = GenerateGameRequest(
        topic="Photosynthesis",
        question_count=15,
        source_text="Light energy is converted to chemical energy.",
        generation_mode="AI Enhanced",
    )
    prompt_enhanced = build_generation_prompt(req_enhanced)
    assert "AI ENHANCED RULES:" in prompt_enhanced
    assert "primary foundation" in prompt_enhanced


def _make_dummy_payload(topic: str, count: int) -> GauntletPayload:
    questions = []
    for s in range(1, count + 1):
        tier = expected_tier_for_stage(s, count)
        opts = [f"Opt A {s}", f"Opt B {s}", f"Opt C {s}", f"Opt D {s}"]
        questions.append(
            Question(
                stage=s,
                tier=tier,
                question=f"Question {s}?",
                options=opts,
                correct_answer=opts[0],
                explanation=f"Explanation {s}.",
            )
        )
    return GauntletPayload(is_valid=True, topic=topic, gauntlet=questions)


def test_generate_gauntlet_with_gemini_success():
    mock_client = MagicMock()
    dummy_payload = _make_dummy_payload("Biology", 5)

    mock_response = MagicMock()
    mock_response.parsed = dummy_payload
    mock_client.models.generate_content.return_value = mock_response

    req = GenerateGameRequest(topic="Biology", question_count=5)
    result = generate_gauntlet_with_gemini(req, client=mock_client)
    assert len(result.gauntlet) == 5
    assert result.topic == "Biology"


def test_generate_gauntlet_topic_rejected():
    mock_client = MagicMock()
    rejected_payload = GauntletPayload(
        is_valid=False,
        rejection_reason="Topic is uninterpretable gibberish.",
        topic="asdf123",
        gauntlet=[],
    )

    mock_response = MagicMock()
    mock_response.parsed = rejected_payload
    mock_client.models.generate_content.return_value = mock_response

    req = GenerateGameRequest(topic="asdf123", question_count=5)
    with pytest.raises(TopicRejectedError, match="uninterpretable gibberish"):
        generate_gauntlet_with_gemini(req, client=mock_client)


def test_generate_gauntlet_strict_mode_insufficient_material():
    mock_client = MagicMock()
    rejected_payload = GauntletPayload(
        is_valid=False,
        rejection_reason="Source material does not contain enough facts for 20 questions.",
        topic="Short Doc",
        gauntlet=[],
    )

    mock_response = MagicMock()
    mock_response.parsed = rejected_payload
    mock_client.models.generate_content.return_value = mock_response

    req = GenerateGameRequest(
        topic="Short Doc",
        question_count=20,
        source_text="Only one sentence.",
        generation_mode="Strict Material Only",
    )
    with pytest.raises(InsufficientMaterialError, match="not contain enough facts"):
        generate_gauntlet_with_gemini(req, client=mock_client)
