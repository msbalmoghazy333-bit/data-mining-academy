"""Flashcard model — a spaced-repetition card for a topic."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ConfidenceLevel


class Flashcard(Base, TimestampMixin):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    front: Mapped[str] = mapped_column(String(512), nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)

    confidence_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ConfidenceLevel.LOW.value, index=True
    )

    topic: Mapped["Topic"] = relationship(back_populates="flashcards")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Flashcard id={self.id} topic_id={self.topic_id}>"
