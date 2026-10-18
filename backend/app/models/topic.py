"""Topic model — a syllabus unit (e.g. 'Clustering', 'Classification')."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import MasteryStatus


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    title_en: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title_ar: Mapped[str] = mapped_column(String(255), nullable=False)

    mastery_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=MasteryStatus.NOT_STARTED.value,
        index=True,
    )

    # A topic owns its lesson, questions and flashcards.
    lessons: Mapped[list["Lesson"]] = relationship(  # noqa: F821
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    questions: Mapped[list["Question"]] = relationship(  # noqa: F821
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    flashcards: Mapped[list["Flashcard"]] = relationship(  # noqa: F821
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(  # noqa: F821
        back_populates="topic", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id} title_en={self.title_en!r}>"
