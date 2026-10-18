"""Topic catalogue — the quiz filter and the future lesson picker read here."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Flashcard, Question, Topic


def list_topics(
    db: Session, *, limit: int = 200, offset: int = 0
) -> tuple[int, list[dict]]:
    """Every syllabus topic with its bank sizes, alphabetical by English title.

    Counts are gathered with two grouped aggregates rather than per-topic
    queries, so the endpoint stays O(1) in round-trips regardless of size.
    """

    total = int(db.execute(select(func.count(Topic.id))).scalar_one())

    question_counts = dict(
        db.execute(
            select(Question.topic_id, func.count(Question.id)).group_by(Question.topic_id)
        ).all()
    )
    flashcard_counts = dict(
        db.execute(
            select(Flashcard.topic_id, func.count(Flashcard.id)).group_by(Flashcard.topic_id)
        ).all()
    )

    rows = db.execute(
        select(Topic).order_by(Topic.title_en).offset(offset).limit(limit)
    ).scalars()

    items = [
        {
            "id": topic.id,
            "title_en": topic.title_en,
            "title_ar": topic.title_ar,
            "mastery_status": topic.mastery_status,
            "questions": int(question_counts.get(topic.id, 0)),
            "flashcards": int(flashcard_counts.get(topic.id, 0)),
        }
        for topic in rows
    ]

    return total, items
