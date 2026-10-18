"""Schemas describing the structured JSON the LLM must return.

These double as:

* the contract spelled out inside the prompt (via ``model_json_schema``), and
* the validator applied to the model's reply, so malformed output surfaces as
  a clean ``LLMInvalidOutput`` instead of corrupting the database.

The shapes mirror the ORM models in ``app/models`` one-to-one so that
publishing is a straight field copy with no translation layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

QuestionTypeLiteral = Literal["mcq", "true_false", "short_answer"]
DifficultyLiteral = Literal["easy", "medium", "hard"]


class GeneratedTerminology(BaseModel):
    term: str = Field(description="English academic term, e.g. 'Clustering'")
    arabic: str = Field(description="Arabic equivalent, e.g. 'العناجمة'")
    definition: str = Field(description="One-sentence definition in Egyptian Arabic")


class GeneratedFormula(BaseModel):
    name: str = Field(description="Short human-readable name of the formula")
    latex: str = Field(description="LaTeX representation, plain text is acceptable")
    note: str = Field(description="When/why to use it, in Arabic")


class GeneratedComparison(BaseModel):
    topic_a: str
    topic_b: str
    aspect: str = Field(description="Dimension being compared, e.g. 'التكلفة الحسابية'")
    detail: str = Field(description="Explanation in Arabic")


class GeneratedLesson(BaseModel):
    """The teaching body for one topic."""

    content_ar: str = Field(
        description="Full lesson in Markdown, Egyptian Arabic, English terms preserved"
    )
    objectives: list[str] = Field(min_length=1, max_length=10)
    prerequisites: list[str] = Field(default_factory=list, max_length=10)
    english_terminology: list[GeneratedTerminology] = Field(default_factory=list, max_length=20)
    formulas: list[GeneratedFormula] = Field(default_factory=list, max_length=15)
    comparisons: list[GeneratedComparison] = Field(default_factory=list, max_length=10)
    summary: str = Field(description="Short wrap-up plus key takeaways, in Arabic")

    @field_validator("content_ar", "summary")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class GeneratedFlashcard(BaseModel):
    front: str = Field(max_length=500)
    back: str = Field(max_length=2000)


class GeneratedQuestion(BaseModel):
    type: QuestionTypeLiteral
    question_text: str = Field(
        description="The question stem, in English (the exam language)."
    )
    # MCQ -> 3-5 English options; true_false -> exactly ["True", "False"]; short_answer -> []
    options: list[str] = Field(default_factory=list, max_length=6)
    correct_answer: str = Field(
        description=(
            "MCQ: the exact English option text. true_false: 'True' or 'False'. "
            "short_answer: the model answer plus accepted English keywords."
        )
    )
    explanation: str = Field(description="Why the answer is right, in Arabic")
    difficulty: DifficultyLiteral

    @field_validator("options")
    @classmethod
    def _options_match_type(cls, value: list[str], info) -> list[str]:
        """Cross-field check: option count must fit the question type."""

        kind = info.data.get("type")  # `type` is declared before `options`

        if kind == "mcq" and not 2 <= len(value) <= 6:
            raise ValueError("MCQ questions need between 2 and 6 options")
        if kind == "true_false" and len(value) != 2:
            raise ValueError("true/false questions need exactly two options")
        if kind == "short_answer" and value:
            raise ValueError("short-answer questions must not carry options")

        return value

    @field_validator("question_text", "correct_answer", "explanation")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class GeneratedTopic(BaseModel):
    """One Data Mining topic extracted from the source chunks."""

    title_en: str = Field(max_length=255)
    title_ar: str = Field(max_length=255)
    # Which input chunk indexes this topic came from (for traceability).
    chunk_indexes: list[int] = Field(default_factory=list)
    lesson: GeneratedLesson
    flashcards: list[GeneratedFlashcard] = Field(min_length=5, max_length=5)
    questions: list[GeneratedQuestion] = Field(min_length=6, max_length=6)

    @field_validator("title_en", "title_ar")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("questions")
    @classmethod
    def _cover_the_ladder(cls, value: list[GeneratedQuestion]) -> list[GeneratedQuestion]:
        """Six questions must span easy/medium/hard so a quiz can be sampled."""

        difficulties = {question.difficulty for question in value}
        missing = {"easy", "medium", "hard"} - difficulties
        if missing:
            raise ValueError(f"questions must cover all difficulties, missing {sorted(missing)}")
        return value


class GeneratedContent(BaseModel):
    """Root payload written to ``SourceFile.generated_content`` (the draft)."""

    topics: list[GeneratedTopic] = Field(min_length=1)
    model: str = ""
    notes: str = ""

    # Denormalised provenance so the UI can show where a draft came from.
    source_file_id: int = 0
    generated_at: str = ""


# ---------------------------------------------------------------------------
# API responses
# ---------------------------------------------------------------------------


class DetectedTopic(BaseModel):
    title_en: str
    title_ar: str
    is_new: bool
    chunk_indexes: list[int] = []


class GenerateResponse(BaseModel):
    """Reply of ``POST /api/v1/files/{id}/generate``."""

    source_file_id: int
    filename: str
    topic_count: int
    new_topics: int
    existing_topics: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    topics: list[DetectedTopic]
    message: str


class PublishResponse(BaseModel):
    """Reply of ``POST /api/v1/files/{id}/publish``."""

    source_file_id: int
    filename: str
    status: str
    topics_created: int
    topics_matched: int
    lessons_created: int
    lessons_updated: int
    questions_created: int
    questions_skipped: int
    flashcards_created: int
    flashcards_skipped: int
    # Null when the embedding backend was unavailable at publish time; the
    # startup sweep will index the file later.
    vectors_indexed: int | None = None
    message: str


class DraftTopicSummary(BaseModel):
    title_en: str
    title_ar: str
    question_count: int
    flashcard_count: int
    lesson_chars: int
    objectives: list[str] = []
    summary: str = ""


class DraftPreview(BaseModel):
    """Compact view of a staged draft (no full lesson body)."""

    source_file_id: int
    filename: str
    has_draft: bool
    model: str = ""
    generated_at: str = ""
    topic_count: int = 0
    topics: list[DraftTopicSummary] = []
