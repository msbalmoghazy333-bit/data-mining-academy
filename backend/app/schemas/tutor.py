"""Request/response schemas for the AI Tutor chat endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TutorHistoryMessage(BaseModel):
    """One earlier turn of the conversation, replayed to the model."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class TutorChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000, description="The student's question.")
    history: list[TutorHistoryMessage] = Field(
        default_factory=list,
        max_length=24,
        description="Earlier conversation turns (user/assistant only).",
    )
    difficulty_level: str | None = Field(
        default=None,
        max_length=30,
        description=(
            "Optional depth hint: simple | normal | advanced | exam_prep. "
            "Unknown values fall back to 'normal'."
        ),
    )


class TutorCitation(BaseModel):
    """A verified source — always a chunk retrieved from the vector store."""

    filename: str = Field(description="Uploaded file the answer came from.")
    page: int = Field(ge=0, description="1-based page/slide number (0 = unknown).")


class TutorChatResponse(BaseModel):
    reply: str
    citations: list[TutorCitation] = Field(default_factory=list)
    # Extras to help the UI build attribution chips and debug views.
    retrieved: int = Field(default=0, description="How many source chunks were fetched.")
    model: str = ""
    used_index: bool = Field(
        default=False, description="False when nothing is indexed (canned refusal)."
    )
