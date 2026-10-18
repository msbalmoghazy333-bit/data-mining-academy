"""Request/response schemas for the quiz engine."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

QuizMode = Literal["practice", "exam"]
QuizDifficulty = Literal["easy", "medium", "hard", "mixed"]


class QuizGenerateRequest(BaseModel):
    topic_ids: list[int] | None = Field(
        default=None,
        description="Restrict the draw to these topics; omit the bank-wide full topic set.",
    )
    difficulty: QuizDifficulty = "mixed"
    count: int = Field(default=10, ge=1, le=50)
    mode: QuizMode = "practice"


class QuizQuestionOut(BaseModel):
    """One assessment item.

    ``correct_answer`` / ``explanation`` are ``null`` in exam mode -- the key
    stays only on the server and after all cases returns fully with
    submission.
    """

    id: int
    topic_id: int
    type: str
    question_text: str
    options: list[str] = []
    difficulty: str
    correct_answer: str | None = None
    explanation: str | None = None
    source_reference: str | None = None


class QuizGenerateResponse(BaseModel):
    mode: str
    difficulty: str
    requested_count: int
    available_count: int = Field(
        description="Questions in the bank matching the filters, before the draw."
    )
    answer_key_hidden: bool = False
    questions: list[QuizQuestionOut]


class QuizAnswerIn(BaseModel):
    """One submission line."""

    question_id: int = Field(ge=1)
    answer: str = Field(default="", max_length=8000)


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswerIn] = Field(min_length=1, max_length=100)


class QuestionResult(BaseModel):
    """Detailed feedback for one question (answer key + attribution)."""

    question_id: int
    type: str
    topic_id: int
    your_answer: str
    is_correct: bool
    earned: int = Field(description="0-100 (token overlap for short answers).")
    expected: str = Field(description="The full answer key.")
    explanation: str | None = None
    source_reference: str | None = None


class TopicBreakdown(BaseModel):
    topic_id: int
    title_en: str
    title_ar: str
    correct: int
    total: int
    score: int = Field(ge=0, le=100)
    previous_mastery: str = ""
    updated_mastery: str = ""
    attempt_id: int | None = None


class QuizSubmitResponse(BaseModel):
    score: int = Field(ge=0, le=100, description="Overall percentage across all topics.")
    correct_count: int
    total_questions: int
    not_found: list[int] = Field(
        default_factory=list, description="Question ids that were not in the bank."
    )
    questions: list[QuestionResult]
    topics: list[TopicBreakdown]
