"""Schemas for flashcard review endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReviewRating = Literal["again", "hard", "good", "easy"]


class FlashcardRead(BaseModel):
    id: int
    topic_id: int
    topic_title_en: str = ""
    topic_title_ar: str = ""
    front: str
    back: str
    confidence_level: str


class FlashcardList(BaseModel):
    total: int
    items: list[FlashcardRead]


class ConfidenceUpdateIn(BaseModel):
    rating: ReviewRating


class ConfidenceUpdateOut(BaseModel):
    id: int
    rating: ReviewRating
    previous_confidence: str
    confidence_level: str = Field(description="After applying the rating.")
