"""Lesson model — the Arabic Markdown teaching content for one topic.

The JSON columns keep the pedagogical scaffolding (objectives, terminology,
formulas, comparisons) as structured data so the React front-end can render
rich cards without re-parsing Markdown.
"""

from typing import Any

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Full lesson body — Markdown, written in Arabic.
    content_ar: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Lists / structured blocks.
    prerequisites: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    objectives: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    # [{"term": "Clustering", "ar": "العناجمة", "definition": "..."}]
    english_terminology: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    # [{"name": "K-Means formula", "latex": "argmin ...", "note": "..."}]
    formulas: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    # [{"topic_a": "K-Means", "topic_b": "DBSCAN", "aspect": "...", "detail": "..."}]
    comparisons: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional single-lesson language hint for the UI.
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="ar")

    topic: Mapped["Topic"] = relationship(back_populates="lessons")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Lesson id={self.id} topic_id={self.topic_id}>"
