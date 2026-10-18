"""Shared ``str``-backed enums used across the ORM models and Pydantic schemas.

Using ``enum.StrEnum`` means the Python value is stored in SQLite as a plain
string (readable, greppable), while type-checkers still get real enum safety.
"""

from enum import StrEnum


class SourceFileStatus(StrEnum):
    """Lifecycle of an uploaded lecture file."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    PUBLISHED = "published"
    FAILED = "failed"


class MasteryStatus(StrEnum):
    """How well the learner currently knows a topic."""

    NOT_STARTED = "not_started"
    LEARNING = "learning"
    NEEDS_REVISION = "needs_revision"
    MASTERED = "mastered"


class QuestionType(StrEnum):
    """Supported assessment item formats."""

    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class Difficulty(StrEnum):
    """Question difficulty ladder."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ConfidenceLevel(StrEnum):
    """Learner self-assessment on a flashcard review."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
