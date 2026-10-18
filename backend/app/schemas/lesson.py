"""Schemas for the lesson viewer endpoints.

The lesson body is Arabic Markdown (``content_ar``); the pedagogical
scaffolding — objectives, terminology, formulas, comparisons — lives in JSON
columns, so the front-end can render rich blocks without re-parsing Markdown.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LessonSummary(BaseModel):
    """One published lesson **without** its potentially long Markdown body."""

    id: int
    topic_id: int
    topic_title_en: str = ""
    topic_title_ar: str = ""
    language: str = "ar"
    summary: str = ""
    objectives: list[str] = []
    prerequisites: list[str] = []
    content_chars: int = Field(description="Size of the Markdown body, in characters.")
    terminology_count: int = 0
    formula_count: int = 0
    comparison_count: int = 0
    updated_at: datetime


class LessonList(BaseModel):
    total: int
    items: list[LessonSummary]


class TerminologyEntry(BaseModel):
    """One English term with its Arabic equivalent and a short definition."""

    term: str = ""
    arabic: str = ""
    definition: str = ""


class FormulaEntry(BaseModel):
    name: str = ""
    latex: str = ""
    note: str = ""


class ComparisonEntry(BaseModel):
    topic_a: str = ""
    topic_b: str = ""
    aspect: str = ""
    detail: str = ""


class LessonRead(LessonSummary):
    """The full lesson: Markdown body plus every structured block."""

    content_ar: str = ""
    english_terminology: list[TerminologyEntry] = []
    formulas: list[FormulaEntry] = []
    comparisons: list[ComparisonEntry] = []
