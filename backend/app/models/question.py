"""Question model — an assessment item belonging to a topic."""

from typing import Any

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import Difficulty, QuestionType


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QuestionType.MCQ.value, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # MCQ: 3-5 English options | true_false: ["True", "False"] | short_answer: []
    options_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    # For MCQ this is the exact English option text; for true_false "True"/"False"
    # (the Arabic aliases "صح"/"خطأ" are still accepted by the grader);
    # for short_answer the model answer / accepted keywords.
    correct_answer: Mapped[str] = mapped_column(String(512), nullable=False)

    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(
        String(20), nullable=False, default=Difficulty.MEDIUM.value, index=True
    )
    # e.g. "section2-DM.pptx — slide 14" so answers can be traced to source.
    source_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)

    topic: Mapped["Topic"] = relationship(back_populates="questions")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Question id={self.id} type={self.type!r} topic_id={self.topic_id}>"
