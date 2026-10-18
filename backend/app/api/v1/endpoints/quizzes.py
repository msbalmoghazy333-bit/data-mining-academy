"""Quiz endpoints — stateless generation + deterministic submission grading."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.quiz import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizQuestionOut,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services import assessment
from app.services.assessment import QuizDraft, apply_mode, select_questions, submit_answers

router = APIRouter(prefix="/v1/quizzes", tags=["quizzes"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/generate",
    response_model=QuizGenerateResponse,
    response_model_exclude_none=True,
    summary="Draw a quiz from the question bank (exam mode hides the answer key)",
)
def generate_quiz(payload: QuizGenerateRequest, db: DbSession) -> QuizGenerateResponse:
    """Sample questions matching the criteria -- no LLM, fully deterministic."""

    draft: QuizDraft = select_questions(
        db,
        topic_ids=payload.topic_ids,
        difficulty=payload.difficulty,
        count=payload.count,
    )
    data = apply_mode(draft, payload.mode)

    return QuizGenerateResponse(
        mode=data["mode"],
        difficulty=data["difficulty"],
        requested_count=data["requested_count"],
        available_count=data["available_count"],
        answer_key_hidden=data["answer_key_hidden"],
        questions=[QuizQuestionOut.model_validate(item) for item in data["questions"]],
    )


@router.post(
    "/submit",
    response_model=QuizSubmitResponse,
    summary="Grade a submission, record attempts, and refresh topic mastery",
)
def submit_quiz(payload: QuizSubmitRequest, db: DbSession) -> QuizSubmitResponse:
    """Deterministic grading + per-topic attempts + dynamic mastery update."""

    result = submit_answers(
        db,
        answers=[entry.model_dump() for entry in payload.answers],
    )

    return QuizSubmitResponse(
        score=result.score,
        correct_count=result.correct_count,
        total_questions=result.total_questions,
        not_found=result.not_found,
        questions=[
            {
                "question_id": item["question_id"],
                "type": item["type"],
                "topic_id": item["topic_id"],
                "your_answer": item["your_answer"],
                "is_correct": item["is_correct"],
                "earned": item["earned"],
                "expected": item["expected"],
                "explanation": item["explanation"],
                "source_reference": item["source_reference"],
            }
            for item in result.per_question
        ],
        topics=[
            {
                "topic_id": group.topic_id,
                "title_en": group.title_en,
                "title_ar": group.title_ar,
                "correct": group.correct,
                "total": group.total,
                "score": round(100 * group.correct / group.total) if group.total else 0,
                "previous_mastery": group.previous_mastery,
                "updated_mastery": group.updated_mastery,
                "attempt_id": group.attempt_id,
            }
            for group in result.topics
        ],
    )
