"""
OmniQuest v1.0 backend.

Generates dynamic learning gauntlets (5, 10, 15, or 20 questions) for any topic
or uploaded document (PDF, DOCX, PPTX, TXT) using Gemini. Stores rounds securely
in memory and validates player submissions server-side.
"""

from __future__ import annotations

import json
import logging
import os
import random
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from document_parser import (
    DocumentParsingError,
    FileTooLargeError,
    extract_text_from_file,
    get_max_upload_size_bytes,
)
from game_logic import (
    ALLOWED_QUESTION_COUNTS,
    BASE_IP_PER_QUESTION,
    DEFAULT_QUESTION_COUNT,
    ForfeitGameRequest,
    ForfeitGameResponse,
    GauntletPayload,
    GenerateGameRequest,
    GenerateGameResponse,
    POWER_UP_LIMITS,
    PublicQuestion,
    Question,
    STREAK_FIRE_BONUS_IP,
    STREAK_FIRE_THRESHOLD,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    UploadDocumentResponse,
    UseFiftyFiftyRequest,
    UseFiftyFiftyResponse,
    UseHintRequest,
    UseHintResponse,
    expected_tier_for_stage,
    generate_bounded_placement_sequence,
    get_tier_checkpoints,
    get_tier_target_ip,
    sanitize_document_text,
    sanitize_input_text,
    shuffle_question_options,
    slice_fallback_gauntlet,
    to_public_questions,
    validate_gauntlet_payload,
    validate_placement_sequence,
    validate_question_count,
)
from gemini_service import (
    GEMINI_MODEL,
    AmbiguousDocumentError,
    InsufficientMaterialError,
    TopicDocumentMismatchError,
    TopicRejectedError,
    build_generation_prompt,
    create_gemini_client,
    generate_gauntlet_with_gemini,
    generate_hint_with_gemini,
    identify_document_topic,
    validate_topic_document_relevance,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="OmniQuest v1.0", version="1.0.0")

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

FALLBACK_PATH = Path(__file__).with_name("fallback_gauntlet.json")
EXPECTED_GAUNTLET_LENGTH = DEFAULT_QUESTION_COUNT
logger = logging.getLogger(__name__)

# In-memory session store and per-session synchronization locks
sessions: dict[str, dict[str, Any]] = {}
session_locks: dict[str, threading.Lock] = {}
sessions_meta_lock = threading.Lock()


def get_session_lock(session_id: str) -> threading.Lock:
    """Thread-safe retrieval or initialization of a per-session lock."""
    with sessions_meta_lock:
        if session_id not in session_locks:
            session_locks[session_id] = threading.Lock()
        return session_locks[session_id]


def store_session(payload: GauntletPayload, difficulty: str = "Medium") -> str:
    """Save the full gauntlet securely and initialize streak & difficulty-based power-up tracking."""
    session_id = str(uuid.uuid4())
    norm_difficulty = difficulty.strip().capitalize() if isinstance(difficulty, str) else "Medium"
    if norm_difficulty not in POWER_UP_LIMITS:
        norm_difficulty = "Medium"
    limits = POWER_UP_LIMITS[norm_difficulty]

    # Map pre-generated and validated hints by stage number
    pregenerated_hints: dict[int, str | None] = {
        question.stage: question.hint for question in payload.gauntlet
    }

    sessions[session_id] = {
        "topic": payload.topic,
        "difficulty": norm_difficulty,
        "power_up_limits": dict(limits),
        "question_count": len(payload.gauntlet),
        "gauntlet": [question.model_dump() for question in payload.gauntlet],
        "current_streak": 0,
        "total_ip_awarded": 0,
        "is_forfeited": False,
        "answered_stages": set(),
        "pregenerated_hints": pregenerated_hints,  # stage_number -> validated hint or None
        "hints": {},                               # stage_number -> str (hints activated during gameplay)
        "pending_hints": set(),                    # defensive set
        "fifty_fifty": {},                         # stage_number -> list[str] (cached eliminated options)
        "submissions": {},                         # stage_number -> SubmitAnswerResponse
    }
    return session_id


def _ensure_session_state(session: dict[str, Any]) -> None:
    """Defensively ensure all tracking sets and dictionaries exist on a session."""
    if "difficulty" not in session or session["difficulty"] not in POWER_UP_LIMITS:
        session["difficulty"] = "Medium"
    if "power_up_limits" not in session:
        session["power_up_limits"] = dict(POWER_UP_LIMITS[session["difficulty"]])
    session.setdefault("current_streak", 0)
    session.setdefault("total_ip_awarded", 0)
    session.setdefault("is_forfeited", False)
    if "answered_stages" not in session or not isinstance(session["answered_stages"], set):
        session["answered_stages"] = set(session.get("answered_stages", []))
    if "pending_hints" not in session or not isinstance(session["pending_hints"], set):
        session["pending_hints"] = set(session.get("pending_hints", []))
    session.setdefault("pregenerated_hints", {})
    session.setdefault("hints", {})
    session.setdefault("fifty_fifty", {})
    session.setdefault("submissions", {})


def load_fallback_gauntlet(
    question_count: int = DEFAULT_QUESTION_COUNT,
) -> GauntletPayload:
    """
    Load, validate, and dynamically slice fallback_gauntlet.json.
    Raises HTTPException if the file is missing or corrupt.
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
        payload = GauntletPayload.model_validate(raw)
        return slice_fallback_gauntlet(payload, question_count=question_count)
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


@app.post("/upload-document", response_model=UploadDocumentResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadDocumentResponse:
    """
    Accept an uploaded document (PDF, DOCX, PPTX, TXT), validate size and format,
    and extract clean text in document order without executing any file content.
    """
    filename = file.filename or "uploaded_document.txt"
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file '{filename}': {exc}",
        ) from exc

    try:
        extracted_text = extract_text_from_file(content, filename)
    except (DocumentParsingError, FileTooLargeError):
        raise
    except Exception as exc:
        logger.exception("Unexpected error parsing document '%s'", filename)
        raise HTTPException(
            status_code=400,
            detail=f"Unable to process file '{filename}': {exc}",
        ) from exc

    words = extracted_text.split()
    return UploadDocumentResponse(
        filename=filename,
        text=extracted_text,
        character_count=len(extracted_text),
        word_count=len(words),
    )


@app.post("/generate-game", response_model=GenerateGameResponse)
def generate_game(request: GenerateGameRequest) -> GenerateGameResponse:
    """
    Create a new game session with dynamic length (5, 10, 15, or 20 questions)
    from a topic or uploaded source material.
    """
    used_fallback = False
    is_strict_material = bool(
        request.source_text and request.generation_mode == "Strict Material Only"
    )

    has_topic = bool(request.topic and request.topic.strip())
    has_document = bool(request.source_text and request.source_text.strip())

    if not has_topic and not has_document:
        raise HTTPException(
            status_code=400,
            detail="Either a topic or an uploaded document must be provided.",
        )

    # Automatic Topic Identification (Empty Topic + Uploaded Document)
    if not has_topic and has_document:
        try:
            identified = identify_document_topic(request.source_text)
            request.topic = identified
        except (AmbiguousDocumentError, InsufficientMaterialError) as exc:
            raise HTTPException(status_code=400, detail=exc.reason) from exc
        except HTTPException:
            raise
        except Exception as exc:
            if is_strict_material:
                raise HTTPException(
                    status_code=500,
                    detail=f"Topic identification failed: {exc}",
                ) from exc
            logger.exception("Topic identification failed; using fallback")
            payload = load_fallback_gauntlet(question_count=request.question_count)
            total_questions = len(payload.gauntlet)
            session_id = store_session(payload, difficulty=request.difficulty)
            return GenerateGameResponse(
                session_id=session_id,
                topic=payload.topic,
                difficulty=request.difficulty,
                power_up_limits=sessions[session_id]["power_up_limits"],
                question_count=total_questions,
                gauntlet=to_public_questions(payload),
                tier_checkpoints=get_tier_checkpoints(total_questions),
                tier_target_ip=get_tier_target_ip(5),
                is_fallback=True,
                message="API unavailable, loading sample round.",
            )

    # Relevance Validation (Provided Topic + Uploaded Document)
    elif has_topic and has_document:
        try:
            validate_topic_document_relevance(request.topic, request.source_text)
        except (TopicDocumentMismatchError, AmbiguousDocumentError) as exc:
            raise HTTPException(status_code=400, detail=exc.reason) from exc
        except HTTPException:
            raise

    try:
        payload = generate_gauntlet_with_gemini(request)
    except (TopicRejectedError, InsufficientMaterialError, TopicDocumentMismatchError, AmbiguousDocumentError) as exc:
        # Topic is nonsensical, material is insufficient, or mismatch detected. Do not serve fallback.
        raise HTTPException(status_code=400, detail=exc.reason) from exc
    except Exception as exc:
        # If Strict Material Only failed due to unexpected API/validation error, fail gracefully without fallback.
        if is_strict_material:
            logger.exception("Strict Material Only generation failed")
            raise HTTPException(
                status_code=500,
                detail=f"Question generation failed: {exc}",
            ) from exc

        # For standard topic generation or AI Enhanced mode, fall back to sample round.
        logger.exception("Gemini generation failed; loading fallback gauntlet")
        payload = load_fallback_gauntlet(question_count=request.question_count)
        used_fallback = True

    total_questions = len(payload.gauntlet)
    session_id = store_session(payload, difficulty=request.difficulty)
    response = GenerateGameResponse(
        session_id=session_id,
        topic=payload.topic or request.topic or "OmniQuest Challenge",
        difficulty=request.difficulty,
        power_up_limits=sessions[session_id]["power_up_limits"],
        question_count=total_questions,
        gauntlet=to_public_questions(payload),
        tier_checkpoints=get_tier_checkpoints(total_questions),
        tier_target_ip=get_tier_target_ip(5),
    )

    if used_fallback:
        response.is_fallback = True
        response.message = "API unavailable, loading sample round."

    return response


@app.post("/forfeit-game", response_model=ForfeitGameResponse)
def forfeit_game(request: ForfeitGameRequest) -> ForfeitGameResponse:
    """
    Atomically mark a game session as forfeited.
    Subsequent answer submissions and power-up activations will be rejected.
    """
    session = sessions.get(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown session_id. Generate a game first, or the session may have been lost.",
        )

    _ensure_session_state(session)
    lock = get_session_lock(request.session_id)
    with lock:
        session["is_forfeited"] = True

    return ForfeitGameResponse(session_id=request.session_id)


@app.post("/use-hint", response_model=UseHintResponse)
def use_hint(request: UseHintRequest) -> UseHintResponse:
    """
    Activate AI Hint for the current stage.
    Retrieves the pre-generated hint instantly from the session without calling Gemini.
    Enforces difficulty limits: Easy: 2, Medium: 1, Hard: 0, Expert: 0.
    Preserves idempotent retries on the same question.
    If hint is unavailable, returns is_available=False without consuming a charge.
    """
    session = sessions.get(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown session_id. Generate a game first, or the session may have been lost.",
        )

    _ensure_session_state(session)
    lock = get_session_lock(request.session_id)

    gauntlet = session.get("gauntlet", [])
    total_stages = len(gauntlet)

    if request.stage_number < 1 or request.stage_number > total_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage_number. Use a value from 1 to {total_stages}.",
        )

    difficulty = session.get("difficulty", "Medium")
    limits = session.get(
        "power_up_limits",
        POWER_UP_LIMITS.get(difficulty, POWER_UP_LIMITS["Medium"]),
    )
    max_hints = limits.get("hint", 0)

    # Atomic validation and retrieval under session lock
    with lock:
        if session.get("is_forfeited"):
            raise HTTPException(
                status_code=400,
                detail="Game run has been forfeited. Cannot use power-ups on a forfeited game.",
            )

        if len(session["answered_stages"]) >= total_stages:
            raise HTTPException(
                status_code=400,
                detail="Game run has ended. All stages have been completed.",
            )

        if request.stage_number in session["answered_stages"]:
            raise HTTPException(
                status_code=400,
                detail=f"Stage {request.stage_number} has already been answered.",
            )

        # Idempotent retry: Return already activated hint for this stage without deducting an extra charge
        if request.stage_number in session["hints"]:
            remaining = max(0, max_hints - len(session["hints"]))
            return UseHintResponse(
                hint=session["hints"][request.stage_number],
                is_available=True,
                remaining_hints=remaining,
            )

        # Reject if hints are not permitted on this difficulty
        if max_hints <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"AI Hint is not available on {difficulty} difficulty.",
            )

        # Reject if quota is already exhausted
        if len(session["hints"]) >= max_hints:
            raise HTTPException(
                status_code=400,
                detail=f"AI Hint limit exhausted for this run ({max_hints} allowed on {difficulty}).",
            )

        # Retrieve pre-generated hint for this stage
        pre_hint = session.get("pregenerated_hints", {}).get(request.stage_number)

        # If hint was not pre-generated or failed validation, mark unavailable without consuming a charge
        if not pre_hint:
            remaining = max(0, max_hints - len(session["hints"]))
            return UseHintResponse(
                hint=None,
                is_available=False,
                message="AI Hint is unavailable for this question.",
                remaining_hints=remaining,
            )

        # Hint is available: activate and record usage atomically
        session["hints"][request.stage_number] = pre_hint
        remaining = max(0, max_hints - len(session["hints"]))
        return UseHintResponse(
            hint=pre_hint,
            is_available=True,
            remaining_hints=remaining,
        )


@app.post("/use-50-50", response_model=UseFiftyFiftyResponse)
def use_fifty_fifty(request: UseFiftyFiftyRequest) -> UseFiftyFiftyResponse:
    """
    Eliminate exactly two incorrect options for the given stage.
    Never eliminates the correct answer.
    Enforces difficulty-based usage limits:
    - Easy: 2 per run
    - Medium: 1 per run
    - Hard: 0 per run
    - Expert: 0 per run
    Caches the elimination so repeated requests on the same question return the identical
    options to remove without consuming extra charges.
    """
    session = sessions.get(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown session_id. Generate a game first, or the session may have been lost.",
        )

    _ensure_session_state(session)
    lock = get_session_lock(request.session_id)

    gauntlet = session.get("gauntlet", [])
    total_stages = len(gauntlet)

    if request.stage_number < 1 or request.stage_number > total_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage_number. Use a value from 1 to {total_stages}.",
        )

    difficulty = session.get("difficulty", "Medium")
    limits = session.get(
        "power_up_limits",
        POWER_UP_LIMITS.get(difficulty, POWER_UP_LIMITS["Medium"]),
    )
    max_fifty = limits.get("fifty_fifty", 0)

    with lock:
        if session.get("is_forfeited"):
            raise HTTPException(
                status_code=400,
                detail="Game run has been forfeited. Cannot use power-ups on a forfeited game.",
            )

        if len(session["answered_stages"]) >= total_stages:
            raise HTTPException(
                status_code=400,
                detail="Game run has ended. All stages have been completed.",
            )

        if request.stage_number in session["answered_stages"]:
            raise HTTPException(
                status_code=400,
                detail=f"Stage {request.stage_number} has already been answered.",
            )

        # Return cached elimination if already used for this question (does not consume extra charge)
        if request.stage_number in session["fifty_fifty"]:
            remaining = max(0, max_fifty - len(session["fifty_fifty"]))
            return UseFiftyFiftyResponse(
                options_to_remove=session["fifty_fifty"][request.stage_number],
                remaining_fifty_fifty=remaining,
            )

        # Reject if 50/50 is not permitted on this difficulty or quota is exhausted
        if max_fifty <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"50/50 is not available on {difficulty} difficulty.",
            )

        if len(session["fifty_fifty"]) >= max_fifty:
            raise HTTPException(
                status_code=400,
                detail=f"50/50 limit exhausted for this run ({max_fifty} allowed on {difficulty}).",
            )

        question = next(
            (item for item in gauntlet if item.get("stage") == request.stage_number),
            None,
        )
        if question is None:
            raise HTTPException(
                status_code=400,
                detail=f"Stage {request.stage_number} was not found in this session.",
            )

        correct_answer = question["correct_answer"]
        options = question["options"]
        incorrect_options = [opt for opt in options if opt != correct_answer]

        if len(incorrect_options) < 2:
            raise HTTPException(
                status_code=500,
                detail="Not enough incorrect options available to eliminate.",
            )

        options_to_remove = random.sample(incorrect_options, 2)
        session["fifty_fifty"][request.stage_number] = options_to_remove
        remaining = max(0, max_fifty - len(session["fifty_fifty"]))
        return UseFiftyFiftyResponse(
            options_to_remove=options_to_remove,
            remaining_fifty_fifty=remaining,
        )


@app.post("/submit-answer", response_model=SubmitAnswerResponse)
def submit_answer(request: SubmitAnswerRequest) -> SubmitAnswerResponse:
    """
    Score one answer, update streak multiplier and IP progression,
    and reveal the stored correct answer plus explanation.
    Guards against duplicate submissions by returning cached results.
    """
    session = sessions.get(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown session_id. Generate a game first, or the session may have been lost.",
        )

    _ensure_session_state(session)
    lock = get_session_lock(request.session_id)

    gauntlet = session.get("gauntlet", [])
    total_stages = len(gauntlet)

    if request.stage_number < 1 or request.stage_number > total_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage_number. Use a value from 1 to {total_stages}.",
        )

    with lock:
        if session.get("is_forfeited"):
            raise HTTPException(
                status_code=400,
                detail="Game run has been forfeited. Cannot submit answers on a forfeited game.",
            )

        # Duplicate submission protection: if already answered, return cached response
        if request.stage_number in session["answered_stages"]:
            cached = session["submissions"].get(request.stage_number)
            if cached is not None:
                return cached

        question: dict[str, Any] | None = next(
            (
                item
                for item in gauntlet
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

        session["answered_stages"].add(request.stage_number)

        if is_correct:
            session["current_streak"] += 1
            current_streak = session["current_streak"]
            streak_fire_active = current_streak >= STREAK_FIRE_THRESHOLD
            base_ip = BASE_IP_PER_QUESTION
            bonus_ip = STREAK_FIRE_BONUS_IP if streak_fire_active else 0
            session["total_ip_awarded"] += base_ip + bonus_ip
        else:
            session["current_streak"] = 0
            current_streak = 0
            streak_fire_active = False
            base_ip = 0
            bonus_ip = 0

        response = SubmitAnswerResponse(
            is_correct=is_correct,
            correct_answer=correct_answer,
            explanation=question["explanation"],
            current_streak=current_streak,
            streak_fire_active=streak_fire_active,
            base_ip_awarded=base_ip,
            bonus_ip_awarded=bonus_ip,
            total_ip_awarded=session["total_ip_awarded"],
        )

        session["submissions"][request.stage_number] = response
        return response
