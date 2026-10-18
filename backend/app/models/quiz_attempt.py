"""QuizAttempt model — an immutable record of one completed quiz."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class QuizAttempt(Base, TimestampMixin):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # {"question_id": {"answer": "...", "is_correct": true}, ...}
    answers_json: Mapped[dict[Any, Any]] = mapped_column(JSON, nullable=False, default=dict)

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    topic: Mapped["Topic"] = relationship(back_populates="quiz_attempts")  # noqa: F821

    def __repr__(self) -> str:
        return f"<QuizAttempt id={self.id} topic_id={self.topic_id} score={self.score}/{self.total_questions}>"
