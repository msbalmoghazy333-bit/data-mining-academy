"""Assessment engine — quiz generation, deterministic grading, mastery.

Three pieces, deliberately kept free of the LLM:

* **Quiz generation** samples the existing question bank (produced by the
  content generator) with filters; in ``exam`` mode the answer key and
  explanations are withheld from the payload.
* **Grading** is fully deterministic: exact normalized match for MCQ and
  true/false, token-overlap scoring for short answers.
* **Mastery tracking** re-computes ``Topic.mastery_status`` after every
  submission from the *most recent* attempts, so a student who slips out of
  a previously mastered topic is correctly demoted.

One :class:`QuizAttempt` row is written **per topic** involved — the table's
``topic_id`` is per-topic by design, and the API response aggregates them.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Question, QuizAttempt, Topic
from app.models.enums import Difficulty, MasteryStatus, QuestionType
from app.services.content_generator import normalize_title

logger = logging.getLogger(__name__)

# Mastery policy — documented in the README and pinned by tests.
MASTERY_MASTERED_THRESHOLD = 80  # avg of recent attempts >= 80 → mastered
MASTERY_LEARNING_THRESHOLD = 50  # 50..79 → learning ; < 50 → needs_revision
MASTERY_HISTORY_WINDOW = 3  # only the most recent attempts count

# Short-answer grading: at least this share of the model answer's keywords
# must appear in the student's text to count as correct.
SHORT_ANSWER_PASS_RATIO = 0.6

# True/false aliases — already normalised (a raw trip via ``normalize_title``
# is required: "خطأ" normalises to "خطا", hamza folded away).
TRUE_ALIASES = {"صح", "true", "1"}
FALSE_ALIASES = {"خطا", "false", "0"}
MCQ_LETTERS = ["أ", "ب", "ج", "د", "ه"]


class NoQuestionsAvailable(Exception):
    """The bank has no question matching the request."""


# ---------------------------------------------------------------------------
# Grading primitives
# ---------------------------------------------------------------------------


def _keywords(text: str) -> set[str]:
    """Meaningful tokens of a text (length >= 2, letters/digits)."""

    return {token for token in normalize_title(text).split() if len(token) >= 2}


def grade_answer(question: Question, answer: str) -> tuple[bool, int]:
    """Grade one submission deterministically.

    Returns ``(is_correct, earned_percent)`` where ``earned_percent`` is an
    integer 0-100 (binary for MCQ / true-false, token overlap for
    short answers).
    """

    student = (answer or "").strip()
    if not student:
        return False, 0

    if question.type == QuestionType.MCQ.value:
        return _grade_mcq(question, student)
    if question.type == QuestionType.TRUE_FALSE.value:
        return _grade_true_false(question, student)
    return _grade_short_answer(question, student)


def _grade_mcq(question: Question, student: str) -> tuple[bool, int]:
    """Exact match, tolerant to letter answers (أ/ب/ج/...) and casing."""

    correct = normalize_title(question.correct_answer)

    if normalize_title(student) == correct:
        return True, 100

    # The client may send the option letter instead of its text.
    letter_index = _letter_index(student)
    if letter_index is not None:
        options = question.options_json or []
        if 0 <= letter_index < len(options):
            if normalize_title(str(options[letter_index])) == correct:
                return True, 100

    return False, 0


def _letter_index(student: str) -> int | None:
    """Index of an Arabic/bare option letter, or ``None`` for full answers."""

    stripped = student.strip().rstrip(").").lstrip("(")
    if len(stripped) == 1:
        normalized = normalize_title(stripped)
        for index, letter in enumerate(MCQ_LETTERS):
            if normalize_title(letter) == normalized:
                return index
        if stripped.isdigit():
            value = int(stripped)
            if 1 <= value <= len(MCQ_LETTERS):
                return value - 1
    return None


def _grade_true_false(question: Question, student: str) -> tuple[bool, int]:
    """Compare against the true/false alias sets (Arabic + English)."""

    key = normalize_title(student)
    expected = normalize_title(question.correct_answer)

    expected_is_true = expected in TRUE_ALIASES or expected == "1"
    student_is_true = key in TRUE_ALIASES or key == "1"
    student_is_false = key in FALSE_ALIASES or key == "0"

    is_correct = (expected_is_true and student_is_true) or (
        not expected_is_true and student_is_false
    )
    return is_correct, 100 if is_correct else 0


def _grade_short_answer(question: Question, student: str) -> tuple[bool, int]:
    """Token-overlap grading against the model answer's keywords."""

    model_keys = _keywords(question.correct_answer)
    if not model_keys:
        # Degenerate key falls back to exact-text equality.
        correct = normalize_title(student) == normalize_title(question.correct_answer)
        return correct, 100 if correct else 0

    student_tokens = set(normalize_title(student).split())
    overlap = len(model_keys & student_tokens) / len(model_keys)
    earned = round(overlap * 100)

    return overlap >= SHORT_ANSWER_PASS_RATIO, earned


# ---------------------------------------------------------------------------
# Quiz generation
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class QuizDraft:
    """:class:`~app.schemas.quiz.QuizGenerateResponse` ingredients."""

    questions: list[Question]
    difficulty: str
    mode: str
    requested_count: int
    available_count: int


def select_questions(
    db: Session,
    *,
    topic_ids: Iterable[int] | None = None,
    difficulty: str = "mixed",
    count: int = 10,
) -> QuizDraft:
    """Sample ``count`` questions from the bank matching the filters.

    Selection is random so retakes differ; within one run it is
    deterministic (no LLM, no timestamps involved).
    """

    candidate_count_query = select(Question)
    if topic_ids is not None:
        candidate_count_query = candidate_count_query.where(Question.topic_id.in_(topic_ids))
    if difficulty != "mixed":
        candidate_count_query = candidate_count_query.where(Question.difficulty == difficulty)

    candidates = list(db.execute(candidate_count_query).scalars())
    available = len(candidates)

    if available == 0:
        return QuizDraft(
            questions=[], difficulty=difficulty, mode="practice",
            requested_count=count, available_count=0,
        )

    picked = random.sample(candidates, k=min(count, available))
    return QuizDraft(
        questions=picked, difficulty=difficulty,
        mode="practice", requested_count=count, available_count=available,
    )


def apply_mode(draft: QuizDraft, mode: str) -> dict[str, Any]:
    """Serialize a draft for the API, honouring the exam/practice mode.

    In ``exam`` mode the answer key and explanations stay server-side so a
    crafty student cannot diff the payload.
    """

    hide_key = mode == "exam"
    items = []
    for question in draft.questions:
        items.append(
            {
                "id": question.id,
                "topic_id": question.topic_id,
                "type": question.type,
                "question_text": question.question_text,
                "options": list(question.options_json or []),
                "difficulty": question.difficulty,
                "correct_answer": None if hide_key else question.correct_answer,
                "explanation": None if hide_key else question.explanation,
                "source_reference": question.source_reference,
            }
        )

    return {
        "mode": mode,
        "difficulty": draft.difficulty,
        "requested_count": draft.requested_count,
        "available_count": draft.available_count,
        "questions": items,
        "answer_key_hidden": hide_key,
    }


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TopicResult:
    """Aggregated result for one topic after grading."""

    topic_id: int
    title_en: str
    title_ar: str
    correct: int = 0
    total: int = 0
    attempt_id: int | None = None
    previous_mastery: str = ""
    updated_mastery: str = ""


@dataclass(slots=True)
class SubmissionResult:
    """:class:`~app.schemas.quiz.QuizSubmitResponse` ingredients."""

    score: int = 0
    correct_count: int = 0
    total_questions: int = 0
    not_found: list[int] = field(default_factory=list)
    per_question: list[dict[str, Any]] = field(default_factory=list)
    topics: list[TopicResult] = field(default_factory=list)


def submit_answers(db: Session, answers: list[dict[str, Any]]) -> SubmissionResult:
    """Grade every answer, record attempts, and refresh mastery.

    Deterministic end-to-end: grading has no randomness, attempts are
    immutable rows, and mastery is recomputed from the attempt history.
    """

    result = SubmissionResult()

    requested: dict[int, str] = {}
    for entry in answers:
        try:
            question_id = int(entry["question_id"])
        except (KeyError, TypeError, ValueError):
            continue
        requested[question_id] = str(entry.get("answer") or "")

    if not requested:
        return result

    questions = {
        question.id: question
        for question in db.execute(
            select(Question).where(Question.id.in_(requested.keys()))
        ).scalars()
    }

    result.not_found = sorted(set(requested) - set(questions))

    topics: dict[int, TopicResult] = {}
    correct_total = 0

    for question_id, student_answer in requested.items():
        question = questions.get(question_id)
        if question is None:
            continue

        is_correct, earned = grade_answer(question, student_answer)
        correct_total += 1 if is_correct else 0
        result.total_questions += 1

        result.per_question.append(
            {
                "question_id": question.id,
                "type": question.type,
                "topic_id": question.topic_id,
                "your_answer": student_answer,
                "is_correct": is_correct,
                "earned": earned,
                "expected": question.correct_answer,
                "explanation": question.explanation,
                "source_reference": question.source_reference,
            }
        )

        group = topics.setdefault(
            question.topic_id,
            TopicResult(
                topic_id=question.topic_id,
                title_en=question.topic.title_en,
                title_ar=question.topic.title_ar,
                previous_mastery=question.topic.mastery_status,
            ),
        )
        group.total += 1
        group.correct += 1 if is_correct else 0

    # One immutable attempt row per topic + mastery refresh.
    for group in topics.values():
        topic = db.get(Topic, group.topic_id)
        score = round(100 * group.correct / group.total) if group.total else 0

        attempt = QuizAttempt(
            topic_id=group.topic_id,
            score=score,
            total_questions=group.total,
            answers_json={
                str(item["question_id"]): {
                    "answer": item["your_answer"],
                    "is_correct": item["is_correct"],
                }
                for item in result.per_question
                if item["topic_id"] == group.topic_id
            },
        )
        db.add(attempt)
        db.flush()
        group.attempt_id = attempt.id

        group.updated_mastery = update_mastery(db, topic)

    if result.total_questions:
        result.score = round(100 * correct_total / result.total_questions)
    result.correct_count = correct_total
    result.topics = list(topics.values())

    db.commit()
    return result


def update_mastery(db: Session, topic: Topic) -> str:
    """Recompute ``mastery_status`` from the most recent attempts.

    Policy (window = last 3 attempts' average):

    * >= 80  → ``mastered``
    * 50..79 → ``learning``
    *  < 50  → ``needs_revision``
    * no attempts → stays ``not_started``
    """

    recent = list(
        db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.topic_id == topic.id)
            .order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
            .limit(MASTERY_HISTORY_WINDOW)
        ).scalars()
    )

    if not recent:
        return topic.mastery_status

    average = sum(attempt.score for attempt in recent) / len(recent)

    if average >= MASTERY_MASTERED_THRESHOLD:
        new_status = MasteryStatus.MASTERED.value
    elif average >= MASTERY_LEARNING_THRESHOLD:
        new_status = MasteryStatus.LEARNING.value
    else:
        new_status = MasteryStatus.NEEDS_REVISION.value

    topic.mastery_status = new_status
    db.flush()
    return new_status
