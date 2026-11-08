"""
OmniQuest game logic, validation, scoring calculations, and bounded randomness.

Supports dynamic gauntlet lengths (5, 10, 15, 20 questions) while preserving
v0.5 game mechanics, scoring proportions, and fairness guarantees.
"""

from __future__ import annotations

import logging
import os
import random
import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
    ValidationInfo,
)

logger = logging.getLogger(__name__)

# Allowed dynamic question counts
ALLOWED_QUESTION_COUNTS: tuple[int, ...] = (5, 10, 15, 20)
DEFAULT_QUESTION_COUNT: int = 20
MAX_INPUT_LENGTH: int = 50
DEFAULT_MAX_DOCUMENT_LENGTH: int = 100_000

# Power-up allocation rules per difficulty (applies to all gauntlet lengths)
POWER_UP_LIMITS: dict[str, dict[str, int]] = {
    "Easy": {"hint": 2, "fifty_fifty": 2, "time_freeze": 2},
    "Medium": {"hint": 1, "fifty_fifty": 1, "time_freeze": 2},
    "Hard": {"hint": 0, "fifty_fifty": 0, "time_freeze": 2},
    "Expert": {"hint": 0, "fifty_fifty": 0, "time_freeze": 0},
}

# Base scoring constants
BASE_IP_PER_QUESTION: int = 100
MAX_BONUS_IP_PER_QUESTION: int = 100  # Up to 200 total per question
TARGET_IP_PERCENTAGE: float = 0.60  # 60% of base points required to pass tier gate
STREAK_FIRE_THRESHOLD: int = 3
STREAK_FIRE_BONUS_IP: int = 50


def get_max_document_length() -> int:
    """Retrieve maximum document character length from environment or use default (100,000)."""
    env_val = os.getenv("MAX_DOCUMENT_CHARS")
    if env_val:
        try:
            parsed = int(env_val.strip())
            if parsed > 0:
                return parsed
        except ValueError:
            pass
    return DEFAULT_MAX_DOCUMENT_LENGTH


def validate_question_count(count: int) -> int:
    """Validate that question_count is one of the allowed values (5, 10, 15, 20)."""
    if count not in ALLOWED_QUESTION_COUNTS:
        allowed_str = ", ".join(str(c) for c in ALLOWED_QUESTION_COUNTS)
        raise ValueError(
            f"Invalid question_count {count}. Allowed values are: {allowed_str}."
        )
    return count


def expected_tier_for_stage(stage: int, total_stages: int = 20) -> int:
    """
    Map a stage number (1 to total_stages) to its difficulty tier (1-4).
    Each tier spans 5 stages:
    - Stages 1-5: Tier 1
    - Stages 6-10: Tier 2
    - Stages 11-15: Tier 3
    - Stages 16-20: Tier 4
    """
    if stage < 1 or stage > total_stages:
        raise ValueError(f"Stage must be between 1 and {total_stages}, got {stage}.")

    if 1 <= stage <= 5:
        return 1
    elif 6 <= stage <= 10:
        return 2
    elif 11 <= stage <= 15:
        return 3
    elif 16 <= stage <= 20:
        return 4
    raise ValueError(f"Unsupported stage {stage} for gauntlet length {total_stages}.")


def get_tier_distribution(total_stages: int) -> dict[int, list[int]]:
    """Return a mapping of tier number to the list of stage numbers belonging to that tier."""
    validate_question_count(total_stages)
    distribution: dict[int, list[int]] = {}
    for stage in range(1, total_stages + 1):
        tier = expected_tier_for_stage(stage, total_stages)
        distribution.setdefault(tier, []).append(stage)
    return distribution


def get_tier_checkpoints(total_stages: int) -> list[int]:
    """
    Return the stage numbers that act as tier checkpoints (gates).
    A checkpoint occurs at the end of a tier only if there is a subsequent tier
    in the gauntlet. The final stage of the gauntlet is a victory completion,
    not an elimination gate.
    """
    validate_question_count(total_stages)
    # Checkpoints can occur at stages 5, 10, 15 when strictly less than total_stages
    return [stage for stage in (5, 10, 15) if stage < total_stages]


def get_tier_target_ip(tier_question_count: int = 5) -> int:
    """
    Calculate the required IP to pass a tier checkpoint.
    Preserves the v0.5 intended scoring proportions:
    5 questions * 100 base IP = 500 base IP -> 60% = 300 IP.
    """
    return round(tier_question_count * BASE_IP_PER_QUESTION * TARGET_IP_PERCENTAGE)


# ---------------------------------------------------------------------------
# Bounded Randomness Configuration
# ---------------------------------------------------------------------------


def get_bounded_randomness_limits(
    length: int, num_options: int = 4
) -> tuple[int, int]:
    """
    Calculate adaptive (max_consecutive, max_total) limits for a given question count.
    Guarantees fairness and unpredictability across 5, 10, 15, and 20 questions:
    - length=20: max_consecutive=2, max_total=7 (35% of total)
    - length=15: max_consecutive=2, max_total=5 (33% of total)
    - length=10: max_consecutive=2, max_total=4 (40% of total)
    - length=5:  max_consecutive=2, max_total=2 (40% of total)
    """
    if length <= 0:
        return (0, 0)

    max_consecutive = 2
    if length <= 5:
        max_total = 2
    elif length <= 10:
        max_total = 4
    elif length <= 15:
        max_total = 5
    else:
        max_total = 7

    return (max_consecutive, max_total)


def validate_placement_sequence(
    sequence: list[int],
    length: int,
    num_options: int = 4,
    max_consecutive: int | None = None,
    max_total: int | None = None,
) -> bool:
    """
    Validate that an option placement sequence satisfies bounded randomness constraints:
    1. Exactly `length` positions exist.
    2. Every position is an integer between 0 and `num_options - 1`.
    3. No position appears more than `max_consecutive` times consecutively.
    4. No position appears more than `max_total` times across the entire sequence.
    """
    if not isinstance(sequence, list) or len(sequence) != length:
        return False

    if any(not isinstance(p, int) or p < 0 or p >= num_options for p in sequence):
        return False

    default_consecutive, default_total = get_bounded_randomness_limits(
        length, num_options
    )
    consecutive_limit = (
        max_consecutive if max_consecutive is not None else default_consecutive
    )
    total_limit = max_total if max_total is not None else default_total

    # Check consecutive limit
    for i in range(len(sequence) - consecutive_limit):
        if all(
            sequence[i + k] == sequence[i] for k in range(1, consecutive_limit + 1)
        ):
            return False

    # Check total limit
    counts = [sequence.count(p) for p in range(num_options)]
    if any(c > total_limit for c in counts):
        return False

    return True


def generate_bounded_placement_sequence(
    length: int,
    num_options: int = 4,
    max_generate_validate_attempts: int = 150,
) -> list[int]:
    """
    Generate a randomized sequence of target option indices (0=A, 1=B, 2=C, 3=D)
    under adaptive bounded randomness constraints.
    Uses rejection sampling with a backtracking solver and deterministic fallback.
    """
    if length <= 0:
        return []

    max_consecutive, max_total = get_bounded_randomness_limits(length, num_options)

    # 1. Rejection sampling for true uniform distribution
    for _ in range(max_generate_validate_attempts):
        candidate = [random.randrange(num_options) for _ in range(length)]
        if validate_placement_sequence(
            candidate, length, num_options, max_consecutive, max_total
        ):
            return candidate

    # 2. Backtracking approach
    def _backtrack(seq: list[int], counts: list[int]) -> list[int] | None:
        if len(seq) == length:
            return seq

        candidates = list(range(num_options))
        random.shuffle(candidates)
        for c in candidates:
            if counts[c] >= max_total:
                continue
            if len(seq) >= max_consecutive and all(
                seq[-k] == c for k in range(1, max_consecutive + 1)
            ):
                continue

            rem = length - (len(seq) + 1)
            other_capacity = sum(
                max_total - counts[i] for i in range(num_options) if i != c
            )
            if rem > other_capacity + (max_total - (counts[c] + 1)):
                continue

            seq.append(c)
            counts[c] += 1
            result = _backtrack(seq, counts)
            if result is not None:
                return result
            seq.pop()
            counts[c] -= 1

        return None

    backtracked = _backtrack([], [0] * num_options)
    if backtracked is not None and validate_placement_sequence(
        backtracked, length, num_options, max_consecutive, max_total
    ):
        return backtracked

    # 3. Deterministic safe fallback (round-robin: 0, 1, 2, 3, 0, 1, ...)
    fallback = [i % num_options for i in range(length)]
    if validate_placement_sequence(
        fallback, length, num_options, max_consecutive, max_total
    ):
        logger.warning("generate_bounded_placement_sequence used deterministic fallback.")
        return fallback

    raise RuntimeError(
        f"Failed to generate a valid bounded placement sequence of length {length}."
    )


# ---------------------------------------------------------------------------
# Pydantic Models & Validation
# ---------------------------------------------------------------------------


class Question(BaseModel):
    """One multiple-choice question in the gauntlet."""

    stage: int = Field(description="Sequential stage number.")
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
    """Full Gemini (or fallback) payload."""

    is_valid: bool = Field(
        default=True,
        description=(
            "True if topic/material is suitable for generating questions. "
            "False if nonsensical, insufficient, or unsuitable."
        ),
    )
    rejection_reason: str | None = Field(
        default=None,
        description="Concise reason if is_valid is False.",
    )
    topic: str = Field(
        default="",
        description="The subject of this gauntlet.",
    )
    gauntlet: list[Question] = Field(
        default_factory=list,
        description="List of questions if is_valid is True.",
    )


class PublicQuestion(BaseModel):
    """Question shape returned to the player without answers or explanations."""

    stage: int
    tier: int
    question: str
    options: list[str]


def sanitize_input_text(value: str, field_name: str) -> str:
    """Validate, normalize, and sanitize user-supplied topic or target level."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be blank.")

    if len(value) > MAX_INPUT_LENGTH:
        raise ValueError(f"{field_name} must not exceed {MAX_INPUT_LENGTH} characters.")

    normalized = re.sub(r"\s+", " ", value).strip()
    if len(normalized) > MAX_INPUT_LENGTH:
        raise ValueError(f"{field_name} must not exceed {MAX_INPUT_LENGTH} characters.")

    sanitized = re.sub(r"[^\w\s.,!?:;'\-–—\"‘’“”()\[\]/&+#%]", "", normalized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    if not sanitized:
        raise ValueError(f"{field_name} cannot be empty after sanitization.")

    if not any(char.isalnum() for char in sanitized):
        raise ValueError(
            f"{field_name} must contain at least one alphanumeric character (letter or number)."
        )

    if len(sanitized) > MAX_INPUT_LENGTH:
        raise ValueError(f"{field_name} must not exceed {MAX_INPUT_LENGTH} characters.")

    return sanitized


def sanitize_document_text(
    text: str,
    max_length: int | None = None,
) -> str:
    """
    Sanitize and validate document source text for RAG generation.

    Requirements:
    1. Do not apply the 50-character limit used for short metadata fields.
    2. Support documents up to a configurable maximum of 100,000 characters.
    3. Preserve meaningful newline characters and paragraph breaks.
    4. Preserve tabs where appropriate.
    5. Normalize Windows-style CRLF and old Mac CR line endings to LF.
    6. Remove null bytes and unwanted control characters without removing meaningful whitespace.
    7. Avoid collapsing the document into one continuous paragraph.
    8. Trim unnecessary whitespace at the beginning and end.
    9. Reject empty or whitespace-only documents.
    """
    if not isinstance(text, str):
        raise ValueError("Document text must be a string.")

    if not text or not text.strip():
        raise ValueError("Document text cannot be empty or whitespace-only.")

    # 1. Normalize line endings: CRLF (\r\n) and CR (\r) -> LF (\n)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip null bytes, BOM, and unwanted ASCII control characters
    # Preserve tabs (\t, 0x09) and newlines (\n, 0x0A)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufeff]", "", normalized)

    # 3. Strip trailing whitespace per line while preserving indentation and newlines
    lines = [re.sub(r"[^\S\n\t]+$", "", line) for line in cleaned.split("\n")]
    cleaned = "\n".join(lines)

    # 4. Collapse excessive consecutive blank lines (3+ newlines -> 2 newlines),
    # preserving paragraph separation without unbounded empty space
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # 5. Trim leading and trailing whitespace of the whole document
    trimmed = cleaned.strip()

    if not trimmed:
        raise ValueError("Document text cannot be empty or whitespace-only after sanitization.")

    # 6. Ensure the document contains substantive alphanumeric content
    if not any(char.isalnum() for char in trimmed):
        raise ValueError(
            "Document text must contain at least one alphanumeric character (letter or number)."
        )

    # 7. Enforce maximum document length ceiling
    effective_max = (
        max_length if max_length is not None else get_max_document_length()
    )
    if len(trimmed) > effective_max:
        raise ValueError(
            f"Document text exceeds maximum allowed size of {effective_max:,} characters "
            f"(received {len(trimmed):,} characters)."
        )

    return trimmed


class GenerateGameRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=MAX_INPUT_LENGTH)
    target_level: str = Field(default="General", max_length=MAX_INPUT_LENGTH)
    question_count: int = Field(default=DEFAULT_QUESTION_COUNT)
    difficulty: Literal["Easy", "Medium", "Hard", "Expert"] = "Medium"
    source_text: str | None = Field(default=None, max_length=DEFAULT_MAX_DOCUMENT_LENGTH)
    generation_mode: Literal["Strict Material Only", "AI Enhanced"] = "AI Enhanced"

    @field_validator("topic", mode="before")
    @classmethod
    def _validate_topic(cls, value: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Topic must be a string.")
        trimmed = value.strip()
        if not trimmed:
            return None
        return sanitize_input_text(trimmed, "Topic")

    @field_validator("target_level")
    @classmethod
    def _validate_target_level(cls, value: str) -> str:
        return sanitize_input_text(value, "target_level")

    @field_validator("difficulty", mode="before")
    @classmethod
    def _validate_difficulty(cls, value: Any) -> str:
        if not value or not isinstance(value, str):
            return "Medium"
        normalized = value.strip().capitalize()
        if normalized not in POWER_UP_LIMITS:
            raise ValueError(
                f"Invalid difficulty '{value}'. Allowed: {', '.join(POWER_UP_LIMITS.keys())}."
            )
        return normalized

    @model_validator(mode="after")
    def _infer_difficulty_from_target_level(self) -> GenerateGameRequest:
        # If difficulty is default Medium but target_level explicitly specifies a difficulty, infer it
        if self.difficulty == "Medium" and self.target_level:
            match = re.search(r"-\s*(Easy|Medium|Hard|Expert)\s*Level", self.target_level, re.IGNORECASE)
            if match:
                self.difficulty = match.group(1).capitalize()  # type: ignore[assignment]
        return self

    @model_validator(mode="after")
    def _validate_topic_and_document_combination(self) -> GenerateGameRequest:
        has_topic = bool(self.topic and self.topic.strip())
        has_document = bool(self.source_text and self.source_text.strip())

        if not has_topic and not has_document:
            raise ValueError("Either a topic or an uploaded document must be provided.")
        return self

    @field_validator("question_count")
    @classmethod
    def _validate_count(cls, value: int) -> int:
        return validate_question_count(value)

    @field_validator("source_text")
    @classmethod
    def _validate_source_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return sanitize_document_text(value)


class GenerateGameResponse(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    session_id: str
    topic: str
    difficulty: str = "Medium"
    power_up_limits: dict[str, int] | None = None
    question_count: int
    gauntlet: list[PublicQuestion]
    tier_checkpoints: list[int]
    tier_target_ip: int
    is_fallback: bool | None = None
    message: str | None = None


class UseHintRequest(BaseModel):
    session_id: str
    stage_number: int


class UseHintResponse(BaseModel):
    hint: str
    remaining_hints: int | None = None


class UseFiftyFiftyRequest(BaseModel):
    session_id: str
    stage_number: int


class UseFiftyFiftyResponse(BaseModel):
    options_to_remove: list[str]
    remaining_fifty_fifty: int | None = None


class ForfeitGameRequest(BaseModel):
    session_id: str


class ForfeitGameResponse(BaseModel):
    session_id: str
    status: str = "forfeited"
    message: str = "Game run forfeited."


class SubmitAnswerRequest(BaseModel):
    session_id: str
    stage_number: int
    selected_option: str


class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str
    current_streak: int = 0
    streak_fire_active: bool = False
    base_ip_awarded: int = 0
    bonus_ip_awarded: int = 0
    total_ip_awarded: int = 0


class UploadDocumentResponse(BaseModel):
    filename: str
    text: str
    character_count: int
    word_count: int


def has_reasonable_option_length_balance(
    options: list[str], correct_answer: str | None = None
) -> bool:
    """
    Validate that options have a reasonable character-length balance.
    Guards against obvious giveaway answers without rejecting legitimate
    scientific formulas (e.g., 'O2', 'H2O', 'CO2', 'ATP') or technical terms.
    """
    cleaned = [opt.strip() for opt in options]
    lengths = [len(opt) for opt in cleaned]
    min_len = min(lengths)
    max_len = max(lengths)

    if min_len == 0:
        return False

    # Options within a 60-character spread are always well-balanced
    if max_len - min_len <= 60:
        return True

    # Check for an obvious giveaway if correct answer is excessively longer than all distractors
    if correct_answer:
        c_len = len(correct_answer.strip())
        distractor_lengths = [len(opt) for opt in cleaned if opt != correct_answer.strip()]
        if distractor_lengths:
            avg_dist = sum(distractor_lengths) / len(distractor_lengths)
            if avg_dist > 0 and (c_len / avg_dist) > 3.5 and (c_len - max(distractor_lengths)) > 60:
                return False

    other_lengths = sorted(lengths)[:-1]
    avg_other = sum(other_lengths) / len(other_lengths)
    if avg_other > 0 and (max_len / avg_other) > 4.0 and (max_len - min_len) > 75:
        return False

    return True


def shuffle_question_options(
    payload: GauntletPayload, length: int | None = None
) -> GauntletPayload:
    """Randomize option order using bounded randomness for the payload questions."""
    if not payload.gauntlet:
        return payload

    actual_length = length or len(payload.gauntlet)
    sequence = generate_bounded_placement_sequence(
        length=actual_length,
        num_options=4,
    )

    for question, target_index in zip(payload.gauntlet, sequence):
        correct_text = question.correct_answer
        distractors = [opt for opt in question.options if opt != correct_text]
        random.shuffle(distractors)

        new_options = (
            distractors[:target_index] + [correct_text] + distractors[target_index:]
        )
        question.options = new_options
        question.correct_answer = correct_text

    return payload


def validate_gauntlet_payload(
    data: Any, expected_length: int = DEFAULT_QUESTION_COUNT
) -> GauntletPayload:
    """
    Validate gauntlet data against expected structure and dynamic question count.
    Normalizes minor discrepancies (whitespace, stage numbers, tiers) while strictly
    enforcing structure (4 unique options, correct answer presence, non-empty questions).
    """
    validate_question_count(expected_length)
    payload = (
        data
        if isinstance(data, GauntletPayload)
        else GauntletPayload.model_validate(data)
    )

    if not payload.is_valid:
        if not payload.rejection_reason or not payload.rejection_reason.strip():
            payload.rejection_reason = (
                f"The topic or material for '{payload.topic or 'provided input'}' "
                "cannot be used to generate educational questions."
            )
        return payload

    if not payload.topic or not payload.topic.strip():
        payload.topic = "Educational Gauntlet"

    if len(payload.gauntlet) != expected_length:
        raise ValueError(
            f"Gauntlet must contain exactly {expected_length} questions, got {len(payload.gauntlet)}."
        )

    for index, question in enumerate(payload.gauntlet, start=1):
        # Auto-normalize sequential stage numbering
        question.stage = index

        # Auto-normalize expected difficulty tier based on stage and gauntlet length
        expected_tier = expected_tier_for_stage(question.stage, expected_length)
        if question.tier != expected_tier:
            question.tier = expected_tier

        if not question.question.strip():
            raise ValueError(f"Stage {question.stage}: question cannot be empty.")

        if len(question.options) != 4:
            raise ValueError(
                f"Stage {question.stage}: must have exactly 4 options, got {len(question.options)}."
            )

        cleaned_options = [opt.strip() for opt in question.options]
        if any(not opt for opt in cleaned_options):
            raise ValueError(f"Stage {question.stage}: options cannot be empty.")

        if len(set(cleaned_options)) != 4:
            raise ValueError(f"Stage {question.stage}: all 4 options must be unique.")

        # Match correct answer with options (supporting whitespace or case normalization)
        if question.correct_answer not in question.options:
            matched = next(
                (opt for opt in question.options if opt.strip().lower() == question.correct_answer.strip().lower()),
                None,
            )
            if matched:
                question.correct_answer = matched
            else:
                raise ValueError(
                    f"Stage {question.stage}: correct_answer '{question.correct_answer}' "
                    f"must match one of the four options: {question.options}."
                )

        if not question.explanation or not question.explanation.strip():
            question.explanation = f"The correct answer is {question.correct_answer}."

        if not has_reasonable_option_length_balance(question.options, question.correct_answer):
            logger.warning(
                "Stage %d options have notable character-length disparity: %s",
                question.stage, question.options,
            )

    return payload


def slice_fallback_gauntlet(
    fallback_payload: GauntletPayload, question_count: int
) -> GauntletPayload:
    """
    Slice a 20-question fallback gauntlet to the requested dynamic question_count.
    Re-maps stages and tiers to ensure valid sequential ordering.
    """
    validate_question_count(question_count)
    sliced_questions: list[Question] = []
    for idx, orig_q in enumerate(fallback_payload.gauntlet[:question_count], start=1):
        q_copy = orig_q.model_copy()
        q_copy.stage = idx
        q_copy.tier = expected_tier_for_stage(idx, question_count)
        sliced_questions.append(q_copy)

    sliced_payload = GauntletPayload(
        is_valid=True,
        topic=fallback_payload.topic,
        gauntlet=sliced_questions,
    )
    return shuffle_question_options(sliced_payload, length=question_count)


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
