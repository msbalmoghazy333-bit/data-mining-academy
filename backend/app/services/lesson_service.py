"""Lesson viewer — read-only access to published lessons.

A topic can own **more than one** lesson (publishing is strictly additive), so
the list endpoint returns compact summaries and only the detail endpoint
streams the Markdown body.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Lesson, Topic


class LessonNotFound(Exception):
    """No lesson with the given id."""


def _as_items(value: Any) -> list[dict]:
    """JSON columns are free-form; keep only well-formed dictionaries."""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_strings(value: Any) -> list[str]:
    """Objective / prerequisite lists are plain strings (tolerate stray types)."""

    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _summary(lesson: Lesson, topic: Topic | None) -> dict:
    return {
        "id": lesson.id,
        "topic_id": lesson.topic_id,
        "topic_title_en": getattr(topic, "title_en", "") if topic else "",
        "topic_title_ar": getattr(topic, "title_ar", "") if topic else "",
        "language": lesson.language or "ar",
        "summary": lesson.summary or "",
        "objectives": _as_strings(lesson.objectives),
        "prerequisites": _as_strings(lesson.prerequisites),
        "content_chars": len(lesson.content_ar or ""),
        "terminology_count": len(_as_items(lesson.english_terminology)),
        "formula_count": len(_as_items(lesson.formulas)),
        "comparison_count": len(_as_items(lesson.comparisons)),
        "updated_at": lesson.updated_at,
    }


def list_lessons(
    db: Session,
    *,
    topic_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    """Summaries in syllabus order (topic, then publish order)."""

    query = select(Lesson)
    count_query = select(func.count(Lesson.id))

    if topic_id is not None:
        query = query.where(Lesson.topic_id == topic_id)
        count_query = count_query.where(Lesson.topic_id == topic_id)

    total = int(db.execute(count_query).scalar_one())

    rows = db.execute(
        query.order_by(Lesson.topic_id, Lesson.id).offset(offset).limit(limit)
    ).scalars()

    return total, [_summary(lesson, db.get(Topic, lesson.topic_id)) for lesson in rows]


def get_lesson(db: Session, lesson_id: int) -> dict:
    """One lesson with its Markdown body and every structured block."""

    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise LessonNotFound(f"No lesson with id {lesson_id}.")

    data = _summary(lesson, db.get(Topic, lesson.topic_id))
    data.update(
        {
            "content_ar": lesson.content_ar or "",
            "english_terminology": _as_items(lesson.english_terminology),
            "formulas": _as_items(lesson.formulas),
            "comparisons": _as_items(lesson.comparisons),
        }
    )

    return data
