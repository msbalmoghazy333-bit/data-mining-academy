"""SQLAlchemy ORM models for Data Mining Academy.

Import every model here so that Alembic's autogenerate can discover them
and so that `Base.metadata.create_all()` registers all tables.
"""

from app.db.base import Base
from app.models.source_file import SourceFile
from app.models.document_chunk import DocumentChunk
from app.models.topic import Topic
from app.models.lesson import Lesson
from app.models.question import Question
from app.models.flashcard import Flashcard
from app.models.quiz_attempt import QuizAttempt

__all__ = [
    "Base",
    "SourceFile",
    "DocumentChunk",
    "Topic",
    "Lesson",
    "Question",
    "Flashcard",
    "QuizAttempt",
]
