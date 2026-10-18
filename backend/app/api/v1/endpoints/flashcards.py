"""Flashcard review endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enums import ConfidenceLevel
from app.schemas.flashcard import (
    ConfidenceUpdateIn,
    ConfidenceUpdateOut,
    FlashcardList,
    FlashcardRead,
)
from app.services import flashcard_service
from app.services.flashcard_service import FlashcardNotFound

router = APIRouter(prefix="/v1/flashcards", tags=["flashcards"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=FlashcardList,
    summary="Review flashcards (filter by topic or confidence)",
)
def list_flashcards(
    db: DbSession,
    topic_id: Annotated[int | None, Query(ge=1)] = None,
    confidence: Annotated[ConfidenceLevel | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FlashcardList:
    """Browse the deck for a study session."""

    total, items = flashcard_service.list_flashcards(
        db, topic_id=topic_id, confidence=confidence.value if confidence else None,
        limit=limit, offset=offset,
    )

    return FlashcardList(
        total=total,
        items=[FlashcardRead.model_validate(item) for item in items],
    )


@router.post(
    "/{flashcard_id}/confidence",
    response_model=ConfidenceUpdateOut,
    summary="Record a review rating (again / hard / good / easy)",
)
def update_confidence(flashcard_id: int, payload: ConfidenceUpdateIn, db: DbSession) -> ConfidenceUpdateOut:
    """Spaced-repetition feedback — maps the rating to a confidence level."""

    try:
        card, previous, new = flashcard_service.update_confidence(
            db, flashcard_id, payload.rating
        )
    except FlashcardNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return ConfidenceUpdateOut(
        id=card.id,
        rating=payload.rating,
        previous_confidence=previous,
        confidence_level=new,
    )
