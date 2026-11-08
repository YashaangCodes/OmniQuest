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
import time
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
    DEADLINE_GRACE_BUFFER_SECONDS,
    DEFAULT_QUESTION_COUNT,
    ForfeitGameRequest,
    ForfeitGameResponse,
    GauntletPayload,
    GenerateGameRequest,
    GenerateGameResponse,
    POWER_UP_LIMITS,
    PublicQuestion,
    Question,
    QUESTION_TIME_LIMIT_MS,
    QUESTION_TIME_LIMIT_SECONDS,
    STREAK_FIRE_BONUS_IP,
    STREAK_FIRE_THRESHOLD,
    StartStageRequest,
    StartStageResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    TIER_PROGRESSION_THRESHOLDS,
    TIME_FREEZE_DURATION_SECONDS,
    UploadDocumentResponse,
    UseFiftyFiftyRequest,
    UseFiftyFiftyResponse,
    UseHintRequest,
    UseHintResponse,
    UseTimeFreezeRequest,
    UseTimeFreezeResponse,
    calculate_speed_bonus,
    expected_tier_for_stage,
    generate_bounded_placement_sequence,
    get_tier_checkpoints,
    get_tier_progression_threshold,
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

app = FastAPI(title="OmniQuest v0.9", version="0.9.0")

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
    norm_difficulty = (
        difficulty.strip().capitalize()
        if isinstance(difficulty, str) and difficulty.strip()
        else "Medium"
    )
    if norm_difficulty not in TIER_PROGRESSION_THRESHOLDS:
        norm_difficulty = "Medium"
    limits = POWER_UP_LIMITS.get(norm_difficulty, POWER_UP_LIMITS["Medium"])

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
        "current_tier": 1,
        "tier_local_ip": 0,
        "checkpoint_failed": False,
        "passed_checkpoints": [],
        "is_forfeited": False,
        "answered_stages": set(),
        "pregenerated_hints": pregenerated_hints,  # stage_number -> validated hint or None
        "hints": {},                               # stage_number -> str (hints activated during gameplay)
        "pending_hints": set(),                    # defensive set
        "fifty_fifty": {},                         # stage_number -> list[str] (cached eliminated options)
        "time_freezes": {},                        # stage_number -> float (freeze duration in seconds)
        "stage_start_times": {},                   # stage_number -> float (monotonic start time)
        "submissions": {},                         # stage_number -> SubmitAnswerResponse
    }
    return session_id


def _ensure_session_state(session: dict[str, Any]) -> None:
    """Defensively ensure all tracking sets and dictionaries exist on a session."""
    if "difficulty" not in session or session["difficulty"] not in TIER_PROGRESSION_THRESHOLDS:
        session["difficulty"] = "Medium"
    if "power_up_limits" not in session:
        session["power_up_limits"] = dict(POWER_UP_LIMITS.get(session["difficulty"], POWER_UP_LIMITS["Medium"]))
    session.setdefault("current_streak", 0)
    session.setdefault("total_ip_awarded", 0)
    session.setdefault("current_tier", 1)
    session.setdefault("tier_local_ip", 0)
    session.setdefault("checkpoint_failed", False)
    if "passed_checkpoints" not in session or not isinstance(session["passed_checkpoints"], list):
        session["passed_checkpoints"] = list(session.get("passed_checkpoints", []))
    session.setdefault("is_forfeited", False)
    if "answered_stages" not in session or not isinstance(session["answered_stages"], set):
        session["answered_stages"] = set(session.get("answered_stages", []))
    if "pending_hints" not in session or not isinstance(session["pending_hints"], set):
        session["pending_hints"] = set(session.get("pending_hints", []))
    session.setdefault("pregenerated_hints", {})
    session.setdefault("hints", {})
    session.setdefault("fifty_fifty", {})
    session.setdefault("time_freezes", {})
    session.setdefault("stage_start_times", {})
    session.setdefault("submissions", {})


def check_stage_progression_eligibility(
    session: dict[str, Any],
    stage_number: int,
    is_submission: bool = False,
) -> None:
    """
    Shared progression and checkpoint eligibility check for /submit-answer, /use-hint, and /use-50-50.
    Must be called under the session lock.
    Raises HTTPException (400) if:
    - Stage number is invalid.
    - Session is forfeited.
    - Session has ended (all stages answered).
    - Session failed a previous checkpoint gate.
    - Requested stage is locked because a preceding checkpoint was not passed.
    For power-ups (!is_submission):
    - Stage cannot already have been answered.
    """
    total_stages = session.get("question_count", len(session.get("gauntlet", [])))
    if stage_number < 1 or stage_number > total_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage_number. Use a value from 1 to {total_stages}.",
        )

    if session.get("is_forfeited"):
        action = "submit answers" if is_submission else "use power-ups"
        raise HTTPException(
            status_code=400,
            detail=f"Game run has been forfeited. Cannot {action} on a forfeited game.",
        )

    answered_stages: set[int] = session.get("answered_stages", set())
    if len(answered_stages) >= total_stages and not (is_submission and stage_number in answered_stages):
        raise HTTPException(
            status_code=400,
            detail="Game run has ended. All stages have been completed.",
        )

    if session.get("checkpoint_failed"):
        raise HTTPException(
            status_code=400,
            detail="Game run has ended due to failed checkpoint.",
        )

    # Checkpoint gate verification: stage is locked if any preceding checkpoint was not passed
    passed_checkpoints = set(session.get("passed_checkpoints", []))
    required_checkpoints = [cp for cp in (5, 10, 15) if cp < stage_number]
    for cp in required_checkpoints:
        if cp not in passed_checkpoints:
            raise HTTPException(
                status_code=400,
                detail=f"Stage {stage_number} is locked. You must complete preceding checkpoint at stage {cp} first.",
            )

    if not is_submission and stage_number in answered_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Stage {stage_number} has already been answered.",
        )


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
                tier_progression_thresholds=TIER_PROGRESSION_THRESHOLDS.get(
                    request.difficulty, TIER_PROGRESSION_THRESHOLDS["Medium"]
                ),
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
        tier_progression_thresholds=TIER_PROGRESSION_THRESHOLDS.get(
            request.difficulty, TIER_PROGRESSION_THRESHOLDS["Medium"]
        ),
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
        check_stage_progression_eligibility(session, request.stage_number, is_submission=False)

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
        check_stage_progression_eligibility(session, request.stage_number, is_submission=False)

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


@app.post("/start-stage", response_model=StartStageResponse)
def start_stage(request: StartStageRequest) -> StartStageResponse:
    """
    Record the server-authoritative monotonic start timestamp for a question stage.
    Preserves manual stage progression: each stage's timer begins strictly when started.
    Enforces sequential progression: only the currently active stage can be started.
    Idempotent: calling this again on an active stage preserves the original start time.
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
        check_stage_progression_eligibility(session, request.stage_number, is_submission=False)

        if request.stage_number in session["answered_stages"]:
            raise HTTPException(
                status_code=400,
                detail=f"Stage {request.stage_number} has already been answered.",
            )

        active_stage = len(session["answered_stages"]) + 1
        if request.stage_number != active_stage:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot start stage {request.stage_number}. Current active stage is {active_stage}.",
            )

        if request.stage_number not in session["stage_start_times"]:
            session["stage_start_times"][request.stage_number] = time.monotonic()

        now = time.monotonic()
        start_time = session["stage_start_times"][request.stage_number]
        freeze_duration = session.get("time_freezes", {}).get(request.stage_number, 0.0)
        elapsed = max(0.0, now - start_time)
        remaining_seconds = max(0.0, QUESTION_TIME_LIMIT_SECONDS + freeze_duration - elapsed)

    return StartStageResponse(
        session_id=request.session_id,
        stage_number=request.stage_number,
        time_limit_seconds=int(QUESTION_TIME_LIMIT_SECONDS),
        remaining_seconds=round(remaining_seconds, 2),
        is_active=True,
    )


@app.post("/use-freeze", response_model=UseTimeFreezeResponse)
@app.post("/use-time-freeze", response_model=UseTimeFreezeResponse)
def use_time_freeze(request: UseTimeFreezeRequest) -> UseTimeFreezeResponse:
    """
    Activate Time Freeze for the current stage, extending authoritative deadline by exactly 5.0 seconds.
    Enforces difficulty quotas: Easy: 2, Medium: 2, Hard: 2, Expert: 0.
    Idempotent: repeated calls on the same question return cached state without granting additional time or deducting charges.
    Does not carry over to subsequent stages.
    """
    session = sessions.get(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Unknown session_id. Generate a game first, or the session may have been lost.",
        )

    _ensure_session_state(session)
    lock = get_session_lock(request.session_id)

    difficulty = session.get("difficulty", "Medium")
    limits = session.get(
        "power_up_limits",
        POWER_UP_LIMITS.get(difficulty, POWER_UP_LIMITS["Medium"]),
    )
    max_freezes = limits.get("time_freeze", 0)

    with lock:
        check_stage_progression_eligibility(session, request.stage_number, is_submission=False)

        # Idempotent retry: if already frozen for this stage, return cached state without extra extension
        if request.stage_number in session["time_freezes"]:
            remaining = max(0, max_freezes - len(session["time_freezes"]))
            return UseTimeFreezeResponse(
                is_frozen=True,
                freeze_duration_seconds=TIME_FREEZE_DURATION_SECONDS,
                remaining_time_freezes=remaining,
            )

        # Enforce that Time Freeze can only be activated on the active stage
        active_stage = len(session["answered_stages"]) + 1
        if request.stage_number != active_stage:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot use Time Freeze on stage {request.stage_number}. Current active stage is {active_stage}.",
            )

        # Reject if Time Freeze is not permitted on this difficulty
        if max_freezes <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Time Freeze is not available on {difficulty} difficulty.",
            )

        # Reject if quota is already exhausted
        if len(session["time_freezes"]) >= max_freezes:
            raise HTTPException(
                status_code=400,
                detail=f"Time Freeze limit exhausted for this run ({max_freezes} allowed on {difficulty}).",
            )

        # Check if active gameplay time has expired before freeze activation (must be active question)
        now = time.monotonic()
        start_time = session["stage_start_times"].get(request.stage_number)
        if start_time is not None:
            elapsed = now - start_time
            if elapsed >= QUESTION_TIME_LIMIT_SECONDS:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot use Time Freeze on an expired question.",
                )
        else:
            session["stage_start_times"][request.stage_number] = now

        # Record Time Freeze
        session["time_freezes"][request.stage_number] = TIME_FREEZE_DURATION_SECONDS
        remaining = max(0, max_freezes - len(session["time_freezes"]))
        return UseTimeFreezeResponse(
            is_frozen=True,
            freeze_duration_seconds=TIME_FREEZE_DURATION_SECONDS,
            remaining_time_freezes=remaining,
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
        # Duplicate submission protection: if already answered, return cached response
        if request.stage_number in session["answered_stages"]:
            cached = session["submissions"].get(request.stage_number)
            if cached is not None:
                return cached

        # Shared eligibility check enforces forfeited, checkpoint_failed, locked stages, etc.
        check_stage_progression_eligibility(session, request.stage_number, is_submission=True)

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

        # Server-authoritative timing and deadline enforcement
        now = time.monotonic()
        start_time = session["stage_start_times"].get(request.stage_number)

        if start_time is None:
            # Untimed test or unstarted stage: award 0 speed bonus, no deadline rejection
            speed_ip = 0
        else:
            freeze_duration = session.get("time_freezes", {}).get(request.stage_number, 0.0)
            elapsed = max(0.0, now - start_time)
            total_allowed = QUESTION_TIME_LIMIT_SECONDS + freeze_duration
            if elapsed > (total_allowed + DEADLINE_GRACE_BUFFER_SECONDS):
                raise HTTPException(
                    status_code=400,
                    detail=f"Submission deadline for stage {request.stage_number} has expired.",
                )
            active_elapsed = max(0.0, elapsed - freeze_duration)
            remaining_seconds = max(0.0, QUESTION_TIME_LIMIT_SECONDS - active_elapsed)
            speed_ip = calculate_speed_bonus(remaining_seconds * 1000.0, is_correct)

        if is_correct:
            session["current_streak"] += 1
            current_streak = session["current_streak"]
            streak_fire_active = current_streak >= STREAK_FIRE_THRESHOLD
            base_ip = BASE_IP_PER_QUESTION
            streak_ip = STREAK_FIRE_BONUS_IP if streak_fire_active else 0
        else:
            session["current_streak"] = 0
            current_streak = 0
            streak_fire_active = False
            base_ip = 0
            streak_ip = 0

        bonus_ip = streak_ip
        awarded_ip = base_ip + speed_ip + streak_ip
        session["total_ip_awarded"] += awarded_ip
        session["tier_local_ip"] += awarded_ip

        # Progression & Checkpoint Evaluation
        stage_tier = expected_tier_for_stage(request.stage_number, total_stages)
        checkpoints = get_tier_checkpoints(total_stages)
        is_checkpoint = request.stage_number in checkpoints

        difficulty = session.get("difficulty", "Medium")
        threshold = (
            get_tier_progression_threshold(difficulty, stage_tier)
            if stage_tier in (1, 2, 3)
            else None
        )

        tier_local_ip_this_round = session["tier_local_ip"]
        checkpoint_passed: bool | None = None
        is_game_over = False

        if is_checkpoint:
            if threshold is None or tier_local_ip_this_round >= threshold:
                checkpoint_passed = True
                is_game_over = False
                session["passed_checkpoints"].append(request.stage_number)
                # Advance tier and reset tier-local meter to 0
                session["current_tier"] = stage_tier + 1
                session["tier_local_ip"] = 0
            else:
                checkpoint_passed = False
                is_game_over = True
                session["checkpoint_failed"] = True
        else:
            if request.stage_number == total_stages:
                is_game_over = False

        if threshold is None:
            progress_pct = 100
        else:
            progress_pct = min(100, round((tier_local_ip_this_round / threshold) * 100))

        response = SubmitAnswerResponse(
            is_correct=is_correct,
            correct_answer=correct_answer,
            explanation=question["explanation"],
            current_streak=current_streak,
            streak_fire_active=streak_fire_active,
            base_ip_awarded=base_ip,
            speed_ip_awarded=speed_ip,
            streak_ip_awarded=streak_ip,
            bonus_ip_awarded=bonus_ip,
            points_awarded=awarded_ip,
            total_ip_awarded=session["total_ip_awarded"],
            tier_local_ip=tier_local_ip_this_round,
            tier_required_ip=threshold,
            tier_progress_percent=progress_pct,
            checkpoint_passed=checkpoint_passed,
            is_checkpoint_stage=is_checkpoint,
            is_game_over=is_game_over,
        )

        session["submissions"][request.stage_number] = response
        return response
