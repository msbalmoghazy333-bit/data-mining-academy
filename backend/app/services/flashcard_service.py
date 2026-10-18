"""Flashcard review — listing and spaced-repetition confidence updates."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Flashcard, Topic
from app.models.enums import ConfidenceLevel

# Spaced-repetition mapping from the 4 standard review ratings to the 3-level
# persistence field. ``hard`` and ``good`` both keep the card at ``medium``:
# the enum cannot express "recalled with difficulty" more precisely, and the
# important signal (fail -> low, smooth recall -> high) is preserved.
RATING_TO_CONFIDENCE = {
    "again": ConfidenceLevel.LOW.value,
    "hard": ConfidenceLevel.MEDIUM.value,
    "good": ConfidenceLevel.MEDIUM.value,
    "easy": ConfidenceLevel.HIGH.value,
}


class FlashcardNotFound(Exception):
    """No flashcard with the given id."""


def list_flashcards(
    db: Session,
    *,
    topic_id: int | None = None,
    confidence: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[dict]]:
    """Filtered flashcards with their topic titles, oldest deck first."""

    query = select(Flashcard)
    count_query = select(func.count(Flashcard.id))

    if topic_id is not None:
        query = query.where(Flashcard.topic_id == topic_id)
        count_query = count_query.where(Flashcard.topic_id == topic_id)
    if confidence is not None:
        query = query.where(Flashcard.confidence_level == confidence)
        count_query = count_query.where(Flashcard.confidence_level == confidence)

    total = int(db.execute(count_query).scalar_one())

    rows = db.execute(
        query.join(Topic, Flashcard.topic_id == Topic.id).order_by(Flashcard.id).offset(offset).limit(limit)
    ).scalars()

    items = []
    for card in rows:
        topic = db.get(Topic, card.topic_id)
        items.append(
            {
                "id": card.id,
                "topic_id": card.topic_id,
                "topic_title_en": getattr(topic, "title_en", "") if topic else "",
                "topic_title_ar": getattr(topic, "title_ar", "") if topic else "",
                "front": card.front,
                "back": card.back,
                "confidence_level": card.confidence_level,
            }
        )

    return total, items


def update_confidence(db: Session, flashcard_id: int, rating: str) -> tuple[Flashcard, str, str]:
    """Apply a review rating, returning ``(card, previous, new)``."""

    card = db.get(Flashcard, flashcard_id)
    if card is None:
        raise FlashcardNotFound(f"No flashcard with id {flashcard_id}.")

    previous = card.confidence_level
    card.confidence_level = RATING_TO_CONFIDENCE[rating]
    db.commit()
    db.refresh(card)

    return card, previous, card.confidence_level
