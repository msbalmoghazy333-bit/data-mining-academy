"""Incremental educational content generation.

Two phases, deliberately separated so a human can review before anything is
committed::

    generate()  chunks --LLM--> GeneratedContent  (stored on the file row)
    publish()   GeneratedContent --rows--> topics / lessons / questions / cards

**Step A** asks the model to group the file's chunks into distinct Data Mining
topics, then reconciles that list against the ``topics`` table so a lecture
that repeats last week's material does not create a duplicate syllabus entry.

**Step B** asks for one fully structured payload per topic: a lesson, worked
examples, formulas, pitfalls, summary, 5 flashcards and 6 questions spanning
easy/medium/hard.

Publishing is strictly **additive**. Nothing is ever deleted: mastery status,
quiz attempts, previously published lessons and other files are all left
untouched, and re-publishing the same draft is idempotent thanks to content
deduplication.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DocumentChunk, Flashcard, Lesson, Question, SourceFile, Topic
from app.models.enums import MasteryStatus, SourceFileStatus
from app.schemas.generated import (
    GeneratedContent,
    GeneratedQuestion,
    GeneratedTopic,
)
from app.services.llm_service import LLMService, get_llm_service

logger = logging.getLogger(__name__)

# Hard ceilings so one pathological deck cannot burn the whole budget.
MAX_TOPICS_PER_FILE = 12
MAX_CHUNKS_PER_TOPIC_CALL = 12


class GenerationError(Exception):
    """Base class for content-generation failures."""


class NoChunksError(GenerationError):
    """The file has nothing extracted, so there is nothing to teach from."""


class NoDraftError(GenerationError):
    """Publish was called before a draft existed."""


# ---------------------------------------------------------------------------
# Title normalisation (used for duplicate-topic detection)
# ---------------------------------------------------------------------------

# Arabic diacritics / sign marks only. Written with explicit escapes because a
# literal character class is far too easy to get wrong -- note the ranges start
# AFTER U+064A (ي), so base Arabic letters are never matched.
_TASHKEEL = re.compile(
    "["
    "\u0610-\u061A"  # Arabic sign marks
    "\u064B-\u065F"  # harakat (fatha, damma, kasra, shadda, tanwin ...)
    "\u0670"  # superscript alef
    "\u0640"  # tatweel / kashida
    "\u06D6-\u06ED"  # Koranic annotation marks
    "\u08D3-\u08FF"  # Arabic small marks (extended)
    "]"
)
_ALEF_VARIANTS = re.compile("[\u0622\u0623\u0625\u0671]")  # آ أ إ ٱ -> ا
_WHITESPACE = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_title(text: str) -> str:
    """Fold a topic title so cosmetic differences do not count as new topics.

    Handles Arabic diacritics and the alef/ya/ta-marbuta variants, so
    «العناجمة» and «العَنَاجِمَة» collapse to the same key.
    """

    if not text:
        return ""

    folded = text.strip().casefold()
    folded = _TASHKEEL.sub("", folded)
    folded = _ALEF_VARIANTS.sub("\u0627", folded)
    folded = folded.replace("\u0649", "\u064A").replace("\u0629", "\u0647")  # ى->ي, ة->ه
    folded = _NON_WORD.sub(" ", folded)
    folded = _WHITESPACE.sub(" ", folded)

    return folded.strip()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TopicAnalysis:
    """One detected topic, reconciled against the syllabus."""

    title_en: str
    title_ar: str
    chunk_indexes: list[int]
    existing_topic_id: int | None = None

    @property
    def is_new(self) -> bool:
        return self.existing_topic_id is None


@dataclass(slots=True)
class GenerationSummary:
    source_file_id: int
    filename: str
    topic_count: int
    new_topics: int
    existing_topics: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    topics: list[TopicAnalysis] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source_file_id": self.source_file_id,
            "filename": self.filename,
            "topic_count": self.topic_count,
            "new_topics": self.new_topics,
            "existing_topics": self.existing_topics,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "topics": [
                {
                    "title_en": t.title_en,
                    "title_ar": t.title_ar,
                    "is_new": t.is_new,
                    "chunk_indexes": t.chunk_indexes,
                }
                for t in self.topics
            ],
        }


@dataclass(slots=True)
class PublishSummary:
    source_file_id: int
    filename: str
    topics_created: int = 0
    topics_matched: int = 0
    lessons_created: int = 0
    lessons_updated: int = 0
    questions_created: int = 0
    questions_skipped: int = 0
    flashcards_created: int = 0
    flashcards_skipped: int = 0

    @property
    def message(self) -> str:
        return "Published additively — nothing was deleted."

    def as_dict(self) -> dict:
        return {
            "source_file_id": self.source_file_id,
            "filename": self.filename,
            "topics_created": self.topics_created,
            "topics_matched": self.topics_matched,
            "lessons_created": self.lessons_created,
            "lessons_updated": self.lessons_updated,
            "questions_created": self.questions_created,
            "questions_skipped": self.questions_skipped,
            "flashcards_created": self.flashcards_created,
            "flashcards_skipped": self.flashcards_skipped,
            "message": "Published additively — nothing was deleted.",
        }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """\
أنت مهندس محتوى تعليمي وخبير في تعدين البيانات (Data Mining).
تُعطى مقتطفات نصية مستخرجة من محاضرات، ومهمتك توليد قائمة المواضيع التعليمية المتميزة.

قواعد صارمة:
1. كل موضوع = وحدة تعليمية واحدة متماسكة يمكن تدريسها في محاضرة واحدة.
2. استخدم الأسماء الإنجليزية الأكاديمية القياسية للعنوان (title_en)، مثل:
   Clustering, Classification, Association Rule Mining, Data Preprocessing,
   Decision Trees, Neural Networks, Evaluation Metrics.
3. title_ar: ترجمة عربية سليمة ومباشرة.
4. chunk_indexes: فهارس المقاطع التي يستند إليها الموضوع (أرقام صحيحة كما وردت).
5. لا تخترع مواضيع غير موجودة في النص، ولا تُكرر موضوعًا بنفس المعنى.
6. أعد JSON فقط، بدون أي نص خارجه وبدون ```json.

الشكل المطلوب:
{"topics": [{"title_en": "Clustering", "title_ar": "العناجمة", "chunk_indexes": [0, 1]}]}
"""

ANALYSIS_SCHEMA_HINT = """\
شكل JSON المطلوب بالضبط:
{
  "topics": [
    {"title_en": "string", "title_ar": "string", "chunk_indexes": [0, 1]}
  ]
}
"""

LESSON_SYSTEM_PROMPT = """\
أنت أستاذ جامعي مصري متخصص في تعدين البيانات (Data Mining)، ومحترف في تصميم المحتوى التعليمي.

تُعطى مقتطفات من محاضرة حول موضوع واحد، وتكتب محتوى تعليمي كاملًا.

قواعد صارمة:
1. اللغة: عربية مصرية واضحة وسلسة، مع الحفاظ على المصطلح الأكاديمي الإنجليزي كما هو.
   عند أول ذكر لمصطلح إنجليزي ضع النسخة العربية بين قوسين، مثال: Clustering (العناجمة).
2. content_ar: درس كامل بصيغة Markdown، متسلسل ومنطقي، يشمل:
   مقدمة، شرح مفاهيم، أمثلة محلولة خطوة بخطوة، الأخطاء الشائعة (Common Pitfalls)، وخاتمة.
3. لا تخترع معادلات غير موجودة أو غير شائعة في هذا السياق.
4. اكتب المعادلات بصيغة LaTeX داخل حقل latex.
5. flashcards: بالضبط 5 بطاقات، سؤال قصير في الأمام و إجابة مركّزة في الخلف.
6. questions: بالضبط 6 أسئلة تغطي المستويات الثلاثة (easy, medium, hard)،
   بأنواع متنوعة: mcq و true_false و short_answer.
   مهم: نص السؤال (question_text) والخيارات (options) و correct_answer تكون
   **بالإنجليزية** لأن الامتحانات بالإنجليزية. أما explanation فيفضل بالعربية.
   - true_false: options بالضبط ["True", "False"]، و correct_answer إما "True" أو "False".
   - mcq: options من 3 إلى 5 وكلها بالإنجليزية، و correct_answer يطابق نص الخيار الإنجليزي حرفيًا.
   - short_answer: options فارغة، و correct_answer بالإنجليزية (الإجابة النموذجية + كلمات مفتاحية إنجليزية).
7. explanation: شرح لماذا الإجابة صحيحة، بالعربية حتى لو السؤال نفسه بالإنجليزية.
8. أعد JSON فقط، بدون أي نص خارجه وبدون ```json.
"""

LESSON_SCHEMA_HINT = """\
الشكل المطلوب بالضبط (مع تحقق صارم):
{
  "title_en": "string",
  "title_ar": "string",
  "chunk_indexes": [0],
  "lesson": {
    "content_ar": "markdown string",
    "objectives": ["objective"],
    "prerequisites": ["prerequisite"],
    "english_terminology": [{"term": "Clustering", "arabic": "العناجمة", "definition": "..."}],
    "formulas": [{"name": "...", "latex": "...", "note": "..."}],
    "comparisons": [{"topic_a": "...", "topic_b": "...", "aspect": "...", "detail": "..."}],
    "summary": "string"
  },
  "flashcards": [{"front": "string", "back": "string"}],   // exactly 5
  "questions": [
    {
      "type": "mcq | true_false | short_answer",
      "question_text": "string (English)",
      "options": ["..."],
      "correct_answer": "string (English; true_false is \\"True\\" or \\"False\\")",
      "explanation": "string (Arabic)",
      "difficulty": "easy | medium | hard"
    }
  ]                                                          // exactly 6, covering all 3 difficulties
}
"""

# The authoritative contract, injected so the prompt cannot drift from code.
LESSON_JSON_SCHEMA = json.dumps(
    GeneratedTopic.model_json_schema(), ensure_ascii=False, indent=2
)


# ---------------------------------------------------------------------------
# Step A -- topic detection
# ---------------------------------------------------------------------------


def load_chunks(db: Session, source_file: SourceFile) -> list[DocumentChunk]:
    """Chunks of a file in index order."""

    return list(
        db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.file_id == source_file.id)
            .order_by(DocumentChunk.chunk_index)
        ).scalars()
    )


def _chunk_blocks(chunks: list[DocumentChunk]) -> str:
    """Render chunks with explicit indexes so the model can cite them back."""

    parts = []
    for chunk in chunks:
        page = chunk.page_or_slide_number
        label = f"[chunk {chunk.chunk_index} | page {page}]" if page else f"[chunk {chunk.chunk_index}]"
        parts.append(f"{label}\n{chunk.content}")
    return "\n\n---\n\n".join(parts)


def analyze_topics(
    db: Session,
    source_file: SourceFile,
    chunks: list[DocumentChunk],
    llm: LLMService,
) -> tuple[list[TopicAnalysis], str, dict]:
    """Step A: group the file's chunks into topics and reconcile with the DB."""

    if len(chunks) > MAX_CHUNKS_PER_TOPIC_CALL * 2:
        logger.info(
            "File %s has %d chunks; sampling the syllabus from the first %d.",
            source_file.id,
            len(chunks),
            MAX_CHUNKS_PER_TOPIC_CALL * 2,
        )
        chunks = chunks[: MAX_CHUNKS_PER_TOPIC_CALL * 2]

    user_prompt = (
        f"ملف المحاضرة: {source_file.filename}\n\n"
        f"المقاطع المستخرجة ({len(chunks)} مقطع):\n\n"
        f"{_chunk_blocks(chunks)}\n\n"
        f"{ANALYSIS_SCHEMA_HINT}"
    )

    payload, result = llm.chat_json(
        [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    raw_topics = payload.get("topics") if isinstance(payload, dict) else None
    if not isinstance(raw_topics, list) or not raw_topics:
        raise GenerationError("The model did not return any topics.")

    # Reconcile against the existing syllabus.
    existing = _existing_topics_by_key(db)

    analyses: list[TopicAnalysis] = []
    seen_keys: set[str] = set()

    for raw in raw_topics[:MAX_TOPICS_PER_FILE]:
        if not isinstance(raw, dict):
            continue

        title_en = str(raw.get("title_en") or "").strip()
        title_ar = str(raw.get("title_ar") or "").strip()
        if not title_en:
            continue

        key = normalize_title(title_en)
        # The model may emit the same topic twice under two spellings.
        if key in seen_keys:
            continue
        seen_keys.add(key)

        indexes = [
            int(i) for i in (raw.get("chunk_indexes") or []) if isinstance(i, (int, float, str))
        ]

        analyses.append(
            TopicAnalysis(
                title_en=title_en,
                title_ar=title_ar or title_en,
                chunk_indexes=indexes,
                existing_topic_id=existing.get(key),
            )
        )

    if not analyses:
        raise GenerationError("Topic detection returned no usable topics.")

    return analyses, result.model, {
        "prompt_tokens": result.usage.prompt_tokens,
        "completion_tokens": result.usage.completion_tokens,
    }


def _existing_topics_by_key(db: Session) -> dict[str, int]:
    """Map normalised ``title_en`` -> topic id for the whole syllabus."""

    mapping: dict[str, int] = {}
    for topic in db.execute(select(Topic)).scalars():
        mapping.setdefault(normalize_title(topic.title_en), topic.id)
    return mapping


# ---------------------------------------------------------------------------
# Step B -- per-topic content
# ---------------------------------------------------------------------------


def generate_for_topic(
    source_file: SourceFile,
    analysis: TopicAnalysis,
    chunks: list[DocumentChunk],
    llm: LLMService,
) -> tuple[GeneratedTopic, dict]:
    """Ask the model for one topic's full structured payload."""

    by_index = {chunk.chunk_index: chunk for chunk in chunks}

    if analysis.chunk_indexes:
        selected = [by_index[i] for i in analysis.chunk_indexes if i in by_index]
    else:
        selected = chunks

    selected = selected[:MAX_CHUNKS_PER_TOPIC_CALL] or chunks[:MAX_CHUNKS_PER_TOPIC_CALL]

    user_prompt = (
        f"الموضوع المطلوب: {analysis.title_en} / {analysis.title_ar}\n\n"
        f"المقاطع المرتبطة ({len(selected)}):\n\n"
        f"{_chunk_blocks(selected)}\n\n"
        f"اكتب محتوى هذا الموضوع بالكامل.\n\n"
        f"{LESSON_SCHEMA_HINT}\n\n"
        f"مرجع المخطط التفصيلي (JSON Schema):\n{LESSON_JSON_SCHEMA}"
    )

    topic, result = llm.chat_json(
        [
            {"role": "system", "content": LESSON_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        schema=GeneratedTopic,
    )

    # Keep the detected Arabic title if the model drifted on this call.
    if not topic.title_ar.strip():
        topic = topic.model_copy(update={"title_ar": analysis.title_ar})

    return topic, {
        "prompt_tokens": result.usage.prompt_tokens,
        "completion_tokens": result.usage.completion_tokens,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def generate_content(
    db: Session,
    source_file: SourceFile,
    *,
    llm: LLMService | None = None,
    commit: bool = True,
) -> GenerationSummary:
    """Run Steps A + B and store the result as the file's draft.

    The draft lives on ``SourceFile.generated_content``; nothing touches the
    topic/lesson/question tables here, so a human always reviews before
    anything becomes visible to learners.
    """

    service = llm or get_llm_service()

    if not service.configured:
        from app.services.llm_service import LLMNotConfigured

        raise LLMNotConfigured(
            "OPENROUTER_API_KEY is not set. Add it to backend/.env to enable "
            "content generation."
        )

    chunks = load_chunks(db, source_file)
    if not chunks:
        raise NoChunksError(
            f"File '{source_file.filename}' has no extracted chunks to learn from."
        )

    analyses, model, usage_a = analyze_topics(db, source_file, chunks, service)

    generated_topics: list[GeneratedTopic] = []
    total_prompt = usage_a["prompt_tokens"]
    total_completion = usage_a["completion_tokens"]

    for analysis in analyses:
        try:
            topic_payload, usage_b = generate_for_topic(source_file, analysis, chunks, service)
        except Exception as exc:  # noqa: BLE001 - one bad topic must not kill the run
            logger.warning(
                "Skipping topic %r of file %s: %s", analysis.title_en, source_file.id, exc
            )
            continue

        generated_topics.append(topic_payload)
        total_prompt += usage_b["prompt_tokens"]
        total_completion += usage_b["completion_tokens"]

    if not generated_topics:
        raise GenerationError("No topic produced usable content; nothing was staged.")

    draft = GeneratedContent(
        topics=generated_topics,
        model=model,
        source_file_id=source_file.id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        notes=(
            f"Derived from {len(chunks)} chunks of '{source_file.filename}'. "
            "Publishing is additive: existing content is never deleted."
        ),
    )

    source_file.generated_content = draft.model_dump()

    if commit:
        db.commit()
        db.refresh(source_file)
    else:
        db.flush()

    return GenerationSummary(
        source_file_id=source_file.id,
        filename=source_file.filename,
        topic_count=len(generated_topics),
        new_topics=sum(1 for a in analyses if a.is_new),
        existing_topics=sum(1 for a in analyses if not a.is_new),
        model=model,
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        topics=analyses,
    )


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


def _text_fingerprint(text: str) -> str:
    """Stable hash used to skip content that is already in the database."""

    return hashlib.sha256(normalize_title(text).encode("utf-8")).hexdigest()


def _citation_for(
    source_file: SourceFile,
    chunk_indexes: list[int],
    chunks: list[DocumentChunk],
) -> str:
    """Human-readable 'slides 3-7' style citation for a generated question."""

    by_index = {chunk.chunk_index: chunk for chunk in chunks}
    pages = sorted(
        {
            by_index[i].page_or_slide_number
            for i in chunk_indexes
            if i in by_index and by_index[i].page_or_slide_number is not None
        }
    )

    if not pages:
        return source_file.filename

    if len(pages) == 1:
        return f"{source_file.filename} — page {pages[0]}"

    contiguous = pages == list(range(pages[0], pages[-1] + 1))
    span = f"{pages[0]}-{pages[-1]}" if contiguous else ", ".join(map(str, pages))
    return f"{source_file.filename} — pages {span}"


def _find_or_create_topic(db: Session, data: dict) -> tuple[Topic, bool]:
    """Locate a topic by normalised title, creating it only when absent.

    An existing topic keeps its ``mastery_status`` -- learner progress is
    never reset by new content.
    """

    key = normalize_title(data["title_en"])

    existing = {
        normalize_title(topic.title_en): topic
        for topic in db.execute(select(Topic)).scalars()
    }

    topic = existing.get(key)
    if topic is not None:
        # Refresh the Arabic title only if it was previously a placeholder.
        if not topic.title_ar.strip():
            topic.title_ar = data["title_ar"]
        return topic, False

    topic = Topic(
        title_en=data["title_en"],
        title_ar=data["title_ar"],
        mastery_status=MasteryStatus.NOT_STARTED.value,
    )
    db.add(topic)
    db.flush()
    return topic, True


def _dump(item: object) -> dict:
    """Pydantic model or already-serialised dict -> plain dict."""

    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item or {})


def _upsert_lesson(topic: Topic, data: dict) -> bool:
    """Update the topic's lesson in place, or create the first one.

    Returns ``True`` when a pre-existing lesson was updated.
    """

    lesson_data = data["lesson"]
    lesson = topic.lessons[0] if topic.lessons else None
    created = lesson is None

    if lesson is None:
        # Appending to the relationship lets SQLAlchemy insert it with the
        # correct topic_id when the parent is flushed.
        lesson = Lesson()
        topic.lessons.append(lesson)

    lesson.content_ar = lesson_data["content_ar"]
    lesson.objectives = list(lesson_data.get("objectives") or [])
    lesson.prerequisites = list(lesson_data.get("prerequisites") or [])
    lesson.english_terminology = [
        _dump(item) for item in lesson_data.get("english_terminology") or []
    ]
    lesson.formulas = [_dump(item) for item in lesson_data.get("formulas") or []]
    lesson.comparisons = [_dump(item) for item in lesson_data.get("comparisons") or []]
    lesson.summary = lesson_data.get("summary") or ""

    return not created


def publish_content(
    db: Session,
    source_file: SourceFile,
    *,
    commit: bool = True,
) -> PublishSummary:
    """Materialise the draft into rows -- additively and idempotently.

    Guarantees:

    * no ``DELETE`` is issued anywhere in this path;
    * ``Topic.mastery_status`` and ``QuizAttempt`` rows are never touched;
    * other files and their chunks are untouched;
    * re-running the same draft adds nothing the second time.
    """

    if not source_file.has_draft:
        raise NoDraftError(
            f"File '{source_file.filename}' has no generated draft. "
            "POST /api/v1/files/{id}/generate first."
        )

    draft = source_file.generated_content or {}
    topics_payload = draft.get("topics") or []

    chunks = load_chunks(db, source_file)
    summary = PublishSummary(source_file_id=source_file.id, filename=source_file.filename)

    for data in topics_payload:
        topic, created = _find_or_create_topic(db, data)
        if created:
            summary.topics_created += 1
        else:
            summary.topics_matched += 1

        if _upsert_lesson(topic, data):
            summary.lessons_updated += 1
        else:
            summary.lessons_created += 1

        citation = _citation_for(source_file, data.get("chunk_indexes") or [], chunks)

        # --- questions: append, skipping ones already in the bank ----------
        known_questions = {
            _text_fingerprint(question.question_text) for question in topic.questions
        }
        for raw in data.get("questions") or []:
            try:
                item = GeneratedQuestion.model_validate(raw)
            except Exception as exc:  # noqa: BLE001 - skip malformed rows
                logger.warning("Skipping malformed question on %r: %s", topic.title_en, exc)
                continue

            fingerprint = _text_fingerprint(item.question_text)
            if fingerprint in known_questions:
                summary.questions_skipped += 1
                continue

            known_questions.add(fingerprint)
            topic.questions.append(
                Question(
                    topic_id=topic.id,
                    type=item.type,
                    question_text=item.question_text,
                    options_json=list(item.options),
                    correct_answer=item.correct_answer,
                    explanation=item.explanation,
                    difficulty=item.difficulty,
                    source_reference=citation,
                )
            )
            summary.questions_created += 1

        # --- flashcards: append, skipping duplicates ------------------------
        known_cards = {_text_fingerprint(card.front) for card in topic.flashcards}
        for raw in data.get("flashcards") or []:
            front = str(raw.get("front") or "").strip()
            back = str(raw.get("back") or "").strip()
            if not front or not back:
                continue

            fingerprint = _text_fingerprint(front)
            if fingerprint in known_cards:
                summary.flashcards_skipped += 1
                continue

            known_cards.add(fingerprint)
            topic.flashcards.append(Flashcard(topic_id=topic.id, front=front, back=back))
            summary.flashcards_created += 1

    # The draft is retained so publishing can be re-run and audited.
    source_file.status = SourceFileStatus.PUBLISHED.value

    if commit:
        db.commit()
        db.refresh(source_file)
    else:
        db.flush()

    return summary
