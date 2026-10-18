"""Request/response schemas for the on-demand translation endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.translation_service import MAX_TEXTS, MAX_TEXT_LENGTH


class TranslationRequest(BaseModel):
    """A batch of strings to translate (ordered, duplicates allowed)."""

    texts: list[str] = Field(min_length=1, max_length=MAX_TEXTS)
    target: Literal["ar", "en"] = Field(
        default="ar", description="Language to translate into."
    )

    @field_validator("texts")
    @classmethod
    def _validate_texts(cls, value: list[str]) -> list[str]:
        cleaned = [text.strip() for text in value]
        if any(not text for text in cleaned):
            raise ValueError("texts must not contain blank entries")
        if any(len(text) > MAX_TEXT_LENGTH for text in cleaned):
            raise ValueError(f"each text must be at most {MAX_TEXT_LENGTH} characters")
        return cleaned


class TranslationResponse(BaseModel):
    translations: list[str] = Field(
        description="One translation per input, in the same order."
    )
    target: str
    model: str = ""
    cached: bool = Field(
        default=False, description="True when every input came from the cache."
    )
