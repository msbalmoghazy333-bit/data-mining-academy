"""Pydantic schemas for SourceFile."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SourceFileStatus


class SourceFileBase(BaseModel):
    filename: str
    file_type: str
    file_size: int = Field(ge=0)
    status: SourceFileStatus


class SourceFileRead(SourceFileBase):
    """Public representation of an uploaded file."""

    id: int
    file_hash: str
    upload_date: datetime
    error_message: str | None = None

    # Derived, populated by the service layer.
    chunk_count: int = 0
    page_count: int = 0
    has_draft: bool = False

    model_config = ConfigDict(from_attributes=True)


class SourceFileList(BaseModel):
    total: int
    items: list[SourceFileRead]


class DuplicateFile(BaseModel):
    """Returned with HTTP 409 when the exact same bytes are re-uploaded."""

    detail: str
    existing_file: SourceFileRead
