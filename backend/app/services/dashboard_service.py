"""Dashboard analytics — one read-only summary endpoint's brain."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import QuizAttempt, SourceFile, Topic
from app.models.enums import MasteryStatus, SourceFileStatus
from app.services.assessment import MASTERY_HISTORY_WINDOW

RECENT_ATTEMPTS_LIMIT = 10
RECOMMENDED_LIMIT = 5


def build_summary(db: Session) -> dict:
    """Everything the dashboard needs in one pass of small queries."""

    return {
        "files": _file_stats(db),
        "topics": _topic_stats(db),
        "recent_attempts": _recent_attempts(db),
        "recommended": _recommended_topics(db),
    }


def _file_stats(db: Session) -> dict:
    total = int(db.execute(select(func.count(SourceFile.id))).scalar_one())

    by_status: dict[str, int] = {
        status.value: 0 for status in SourceFileStatus
    }
    for status_value, count in db.execute(
        select(SourceFile.status, func.count(SourceFile.id)).group_by(SourceFile.status)
    ):
        by_status[str(status_value)] = int(count)

    return {"total": total, "by_status": by_status}


def _topic_stats(db: Session) -> dict:
    total = int(db.execute(select(func.count(Topic.id))).scalar_one())

    mastery: dict[str, int] = {status.value: 0 for status in MasteryStatus}
    for status_value, count in db.execute(
        select(Topic.mastery_status, func.count(Topic.id)).group_by(Topic.mastery_status)
    ):
        mastery[str(status_value)] = int(count)

    studied = sum(
        count for status, count in mastery.items() if status != MasteryStatus.NOT_STARTED.value
    )
    return {"total": total, "studied": studied, "mastery": mastery}


def _recent_attempts(db: Session) -> list[dict]:
    rows = db.execute(
        select(QuizAttempt)
        .order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
        .limit(RECENT_ATTEMPTS_LIMIT)
    ).scalars()

    recent = []
    for attempt in rows:
        topic = db.get(Topic, attempt.topic_id)
        recent.append(
            {
                "attempt_id": attempt.id,
                "topic_id": attempt.topic_id,
                "topic_title_en": getattr(topic, "title_en", "") if topic else "",
                "topic_title_ar": getattr(topic, "title_ar", "") if topic else "",
                "score": int(attempt.score),
                "total_questions": int(attempt.total_questions),
                "completed_at": attempt.completed_at,
            }
        )
    return recent


def _recommended_topics(db: Session) -> list[dict]:
    """Weakest topics first: needs_revision, then learning, then low scores.

    A ``mastered`` topic only re-enters the list after falling below the
    threshold in ``assessment.update_mastery`` — correct by construction.
    """

    topics = list(db.execute(select(Topic)).scalars())

    priorities = {
        MasteryStatus.NEEDS_REVISION.value: 0,
        MasteryStatus.LEARNING.value: 1,
    }

    candidates: list[dict] = []
    for topic in topics:
        priority = priorities.get(topic.mastery_status)
        if priority is None:
            continue

        attempts = list(
            db.execute(
                select(QuizAttempt)
                .where(QuizAttempt.topic_id == topic.id)
                .order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
                .limit(MASTERY_HISTORY_WINDOW)
            ).scalars()
        )

        last_score = int(attempts[0].score) if attempts else None
        candidates.append(
            {
                "topic_id": topic.id,
                "title_en": topic.title_en,
                "title_ar": topic.title_ar,
                "mastery_status": topic.mastery_status,
                "attempts": _attempt_count(db, topic.id),
                "last_score": last_score,
                # Sort key: revision urgently, then struggling, then weakest score.
                "_sort": (
                    priority,
                    last_score if last_score is not None else 999,
                ),
            }
        )

    candidates.sort(key=lambda entry: entry["_sort"])
    recommended = candidates[:RECOMMENDED_LIMIT]

    for entry in recommended:
        entry.pop("_sort", None)

    return recommended


def _attempt_count(db: Session, topic_id: int) -> int:
    return int(
        db.execute(
            select(func.count(QuizAttempt.id)).where(QuizAttempt.topic_id == topic_id)
        ).scalar_one()
    )
