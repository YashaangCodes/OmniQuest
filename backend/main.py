"""
OmniQuest MVP backend.

Generates a 20-question "gauntlet" for a topic using Gemini, stores the
full round (including answers) in memory, and scores player submissions.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="OmniQuest MVP")

# Allow the local Next.js frontend to call this API during development.
# Support production deployments by allowing an optional FRONTEND_ORIGIN.
allowed_origins = ["http://localhost:3000"]
frontend_origin = os.getenv("FRONTEND_ORIGIN")
if frontend_origin:
    for origin in frontend_origin.split(","):
        cleaned = origin.strip()
        if cleaned and cleaned != "*" and cleaned not in allowed_origins:
            allowed_origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_MODEL = "gemini-3.1-flash-lite"
FALLBACK_PATH = Path(__file__).with_name("fallback_gauntlet.json")
EXPECTED_GAUNTLET_LENGTH = 20
logger = logging.getLogger(__name__)

# Sessions are lost when the server restarts and are not shared across
# multiple server processes. This in-memory dict is only suitable for a
# single-process local MVP.
sessions: dict[str, dict[str, Any]] = {}


def expected_tier_for_stage(stage: int) -> int:
    """Map a stage number (1-20) to its difficulty tier (1-4)."""
    if 1 <= stage <= 5:
        return 1
    if 6 <= stage <= 10:
        return 2
    if 11 <= stage <= 15:
        return 3
    if 16 <= stage <= 20:
        return 4
    raise ValueError(f"Stage must be between 1 and 20, got {stage}.")


# ---------------------------------------------------------------------------
# Pydantic schemas (also used as Gemini structured-output schema)
# ---------------------------------------------------------------------------


class Question(BaseModel):
    """One multiple-choice question in the gauntlet."""

    stage: int = Field(description="Sequential stage number from 1 to 20.")
    tier: int = Field(description="Difficulty tier 1-4 based on the stage.")
    question: str = Field(description="The question prompt shown to the player.")
    options: list[str] = Field(
        description="Exactly four unique answer choices.",
        min_length=4,
        max_length=4,
    )
    correct_answer: str = Field(
        description="Must exactly match one of the four options."
    )
    explanation: str = Field(
        description="A concise explanation of why the correct answer is right."
    )

    @field_validator("question", "correct_answer", "explanation")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be empty.")
        return cleaned

    @field_validator("options")
    @classmethod
    def _unique_nonempty_options(cls, options: list[str]) -> list[str]:
        cleaned = [option.strip() for option in options]
        if any(not option for option in cleaned):
            raise ValueError("Each option must be a non-empty string.")
        if len(set(cleaned)) != 4:
            raise ValueError("All four options must be unique.")
        return cleaned


class GauntletPayload(BaseModel):
    """Full Gemini (or fallback) payload: topic plus 20 questions."""

    topic: str = Field(description="The subject of this gauntlet.")
    gauntlet: list[Question] = Field(
        description="Exactly 20 questions, stages 1 through 20.",
        min_length=EXPECTED_GAUNTLET_LENGTH,
        max_length=EXPECTED_GAUNTLET_LENGTH,
    )

    @field_validator("topic")
    @classmethod
    def _topic_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Topic cannot be empty.")
        return cleaned


class PublicQuestion(BaseModel):
    """Question shape returned to the player before they answer."""

    stage: int
    tier: int
    question: str
    options: list[str]


class GenerateGameRequest(BaseModel):
    topic: str


class GenerateGameResponse(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    session_id: str
    topic: str
    gauntlet: list[PublicQuestion]
    is_fallback: bool | None = None
    message: str | None = None


class SubmitAnswerRequest(BaseModel):
    session_id: str
    stage_number: int
    selected_option: str


class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_gauntlet_payload(data: Any) -> GauntletPayload:
    """
    Validate gauntlet data even when Gemini used structured output.

    Checks length, sequential stages, tier mapping, unique options, and
    that correct_answer exactly matches one option.
    """
    payload = (
        data
        if isinstance(data, GauntletPayload)
        else GauntletPayload.model_validate(data)
    )

    if len(payload.gauntlet) != EXPECTED_GAUNTLET_LENGTH:
        raise ValueError(
            f"Gauntlet must contain exactly {EXPECTED_GAUNTLET_LENGTH} questions."
        )

    for index, question in enumerate(payload.gauntlet, start=1):
        if question.stage != index:
            raise ValueError(
                f"Stages must be sequential from 1 to 20. "
                f"Expected stage {index}, got {question.stage}."
            )

        expected_tier = expected_tier_for_stage(question.stage)
        if question.tier != expected_tier:
            raise ValueError(
                f"Stage {question.stage} must be tier {expected_tier}, "
                f"got {question.tier}."
            )

        if question.correct_answer not in question.options:
            raise ValueError(
                f"Stage {question.stage}: correct_answer must exactly match "
                "one of the four options."
            )

    return payload


def to_public_questions(payload: GauntletPayload) -> list[PublicQuestion]:
    """Strip correct_answer and explanation before sending questions to the player."""
    return [
        PublicQuestion(
            stage=question.stage,
            tier=question.tier,
            question=question.question,
            options=question.options,
        )
        for question in payload.gauntlet
    ]


def store_session(payload: GauntletPayload) -> str:
    """Save the full gauntlet (including answers) and return a new session_id."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "topic": payload.topic,
        "gauntlet": [question.model_dump() for question in payload.gauntlet],
    }
    return session_id


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


def build_generation_prompt(topic: str) -> str:
    """Ask Gemini for a 20-question gauntlet. Do not include a JSON example."""
    return f"""
Create a 20-question multiple-choice learning gauntlet about this topic: {topic}

Difficulty by stage:
- Stages 1-5: easy recall and definitions.
- Stages 6-10: medium difficulty; connections and conceptual understanding.
- Stages 11-15: high difficulty; applications and scenarios.
- Stages 16-19: very high difficulty; multi-step reasoning.
- Stage 20: a Golden Challenge that applies two distinct concepts and has one clearly defensible answer.

Rules:
- Stages must be 1 through 20 in order.
- Tiers: stages 1-5 are tier 1, 6-10 tier 2, 11-15 tier 3, 16-20 tier 4.
- Each question has exactly four unique options.
- correct_answer must exactly match one of those options.
- Keep explanations concise.
""".strip()


def create_gemini_client() -> genai.Client | None:
    """Build a Gemini client from GEMINI_API_KEY, or None if the key is missing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    # 120s timeout: generating 20 questions can take a while.
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=120_000),
    )


def generate_gauntlet_with_gemini(topic: str) -> GauntletPayload:
    """Call Gemini with structured output and validate the result."""
    client = create_gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_generation_prompt(topic),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GauntletPayload,
        ),
    )

    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        return validate_gauntlet_payload(parsed)

    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise ValueError("Gemini returned empty content.")

    return validate_gauntlet_payload(json.loads(text))


def load_fallback_gauntlet() -> GauntletPayload:
    """
    Load and validate fallback_gauntlet.json from this file's directory.

    Raises HTTPException instead of crashing if the file is missing or invalid.
    """
    if not FALLBACK_PATH.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                "Gemini is unavailable and fallback_gauntlet.json was not found "
                f"next to main.py ({FALLBACK_PATH})."
            ),
        )

    try:
        raw = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
        return validate_gauntlet_payload(raw)
    except HTTPException:
        raise
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Gemini is unavailable and fallback_gauntlet.json is invalid "
                f"or unreadable: {exc}"
            ),
        ) from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/generate-game", response_model=GenerateGameResponse)
def generate_game(request: GenerateGameRequest) -> GenerateGameResponse:
    """Create a new game session from a topic (or a validated fallback round)."""
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(
            status_code=400,
            detail="Topic cannot be empty. Please provide a non-empty topic string.",
        )

    used_fallback = False
    try:
        payload = generate_gauntlet_with_gemini(topic)
    except Exception:
        # Timeouts, rate limits, unusable data, missing key, and validation
        # failures all fall back to the sample round.
        logger.exception("Gemini generation failed; loading fallback")
        payload = load_fallback_gauntlet()
        used_fallback = True

    session_id = store_session(payload)
    response = GenerateGameResponse(
        session_id=session_id,
        topic=payload.topic,
        gauntlet=to_public_questions(payload),
    )

    if used_fallback:
        # Use the fallback file's topic (already on payload). Do not claim the
        # sample round is about the player's topic unless those topics match.
        response.is_fallback = True
        response.message = "API unavailable, loading sample round."

    return response


@app.post("/submit-answer", response_model=SubmitAnswerResponse)
def submit_answer(request: SubmitAnswerRequest) -> SubmitAnswerResponse:
    """Score one answer and reveal the stored correct answer plus explanation."""
    session = sessions.get(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown session_id. Generate a game first, or the session may have been lost.",
        )

    if request.stage_number < 1 or request.stage_number > EXPECTED_GAUNTLET_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage_number. Use a value from 1 to {EXPECTED_GAUNTLET_LENGTH}.",
        )

    question: dict[str, Any] | None = next(
        (
            item
            for item in session["gauntlet"]
            if item.get("stage") == request.stage_number
        ),
        None,
    )
    if question is None:
        raise HTTPException(
            status_code=400,
            detail=f"Stage {request.stage_number} was not found in this session.",
        )

    correct_answer = question["correct_answer"]
    is_correct = request.selected_option == correct_answer
    return SubmitAnswerResponse(
        is_correct=is_correct,
        correct_answer=correct_answer,
        explanation=question["explanation"],
    )
