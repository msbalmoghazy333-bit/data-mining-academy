"""Pydantic schemas for DocumentChunk and the pre-publish preview."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.source_file import SourceFileRead


class DocumentChunkRead(BaseModel):
    id: int
    chunk_index: int
    content: str
    page_or_slide_number: int | None = None
    topic_tag: str | None = None
    word_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class PagePreview(BaseModel):
    """One extracted page/slide as it will be cited downstream."""

    page_number: int
    word_count: int = Field(ge=0)
    preview: str = Field(description="First ~300 characters of the page text.")
    full_text: str


class FilePreview(BaseModel):
    """Everything needed to review an upload before publishing it."""

    file: SourceFileRead
    pages: list[PagePreview]
    chunks: list[DocumentChunkRead]
    total_pages: int
    total_words: int
    total_chunks: int
