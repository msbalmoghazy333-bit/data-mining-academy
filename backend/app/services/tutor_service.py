"""The AI Tutor -- Retrieval-Augmented Generation, strictly grounded.

Pipeline on every student question::

    question --embed--> top-k chunks from ChromaDB (published files only)
             --prompt--> LLM (Egyptian Arabic + English terms + citations)
             --parse--> strictly validated citation list

Design rules enforced here:

* **Citations come from retrieval metadata**, never from the model. Every
  ``[filename — صفحة N]`` the model emits is matched against the chunks we
  actually retrieved; an invented citation simply disappears from the
  structured answer.
* The exact refusal sentence (""المعلومة دي مش مذكورة في السلايدات أو الملفات
  المرفوعة"") is required in the prompt when the material does not contain
  the answer, and is used verbatim when there is no indexed material at all.
* The system prompt forbids fabricating page numbers, formulas or facts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.core.config import get_settings
from app.schemas.tutor import TutorCitation
from app.services import vector_store as vs_module
from app.services.llm_service import LLMService, get_llm_service
from app.services.vector_store import RetrievedChunk

logger = logging.getLogger(__name__)

# The exact sentence the tutor must use when the course material does not
# contain the answer. Kept in code (not only in the prompt) so the no-index
# path produces byte-identical wording.
NOT_FOUND_MESSAGE = "المعلومة دي مش مذكورة في السلايدات أو الملفات المرفوعة"
NO_INDEX_HINT = (
    "(لسه مفيش ملف منشور اتفهرس في النظام — ارفع محاضرة واعتمدها "
    "بـ POST /api/v1/files/{id}/publish الأول، وبعدين اسألني تاني.)"
)

CITATION_EXAMPLE_FORMAT = "[02Data.pdf.pptx — صفحة 5]"

# [filename — صفحة N] with em/en-dash or hyphen as the separator.
_CITATION_RE = re.compile(
    r"\[([^\[\]]+?)\s*[-\u2013\u2014]\s*(?:صفحة\s*|page\s*)?(\d+)\s*\]",
    re.IGNORECASE,
)


class TutorError(Exception):
    """Base class for tutor failures the endpoint maps to HTTP codes."""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TutorAnswer:
    """Everything the endpoint needs, nothing fabricated."""

    reply: str
    citations: list[TutorCitation] = field(default_factory=list)
    retrieved: int = 0
    model: str = ""
    used_index: bool = False

    def as_dict(self) -> dict:
        return {
            "reply": self.reply,
            "citations": [citation.model_dump() for citation in self.citations],
            "retrieved": self.retrieved,
            "model": self.model,
            "used_index": self.used_index,
        }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_DIFFICULTY_STYLE: dict[str, str] = {
    "simple": "اشرح كأنك بتكلم طالب بيبدأ من الصفر، وبالبسيط جدًا مع أمثلة من الحياة.",
    "beginner": "اشرح كأنك بتكلم طالب بيبدأ من الصفر، وبالبسيط جدًا مع أمثلة من الحياة.",
    "normal": "اشرح بوضوح مناسب لطالب جامعة متمكن من الأساسيات.",
    "advanced": "زوّد العمق الأكاديمي: التفاصيل التقنية، حدود الأسلوبات، والمقارنات.",
    "exam_prep": (
        "ركّز على اللي بييجي في الامتحانات: التعريفات الدقيقة، الخطوات خطوة بخطوة، "
        "والأخطاء اللي الطلاب بقعوا فيها قبل كده."
    ),
}

SYSTEM_PROMPT = """\
أنت "المعلم الذكي" في أكاديمية تعدين البيانات (Data Mining Academy) — مدرّس مصري \
شاطر وصبور، بيجاوب بناءً على مصادر الكورس المرفوعة فقط.

المقاطع الموجودة لك في السياق هي مادة الكورس المسموح بها **وحدها**.

قواعد صارمة — تلتزم بيها بالحرف:
1. اشرح بالمصري المصرّك الواضح والمحبوب، مع الحفاظ على المصطلح الأكاديمي \
الإنجليزي كما هو (Clustering، K-Means، Classification ...) — أول مرّة تذكر \
المصطلح تكتب جانبه معناه العربي.
2. الاستشهاد إلزامي لكل معلومة جاية من المصدر. الشكل بالظبط: \
{CITATION_EXAMPLE_FORMAT}
   اسم الملف و رقم الصفحة لازم يكونوا من المقاطع اللي معاك، مش من ذاكرتك.
3. لو الإجابة مش موجودة فعليًا في المقاطع، اكتب الجملة دي لوحدها وسط الإجابة \
بلا أي استشهاد: {NOT_FOUND_MESSAGE}
4. ممنوع تمامًا اختراع أرقام صفحات أو معادلات أو معلومات. لو رقم صفحة مش \
واضح من المصدر، استشهد بالمصدر اللي ذكر الفكرة فرد لوسقط الاستشهاد لو \
انك مش واثق.
5. اللي تعمله لو المقاطع فيها جزء من الإجابة: اجاوب الجزء الموجود، و صرّح \
بصريح العبارة بالجزء الغايب بعدها (استخدم الجملة في الرقم 3).
6. ممنوع تطلع معلومات من برّه المقاطع حتى لو كانت "معلومات عامة".
{STYLE_LINE}

الإجابة تيجي مختصرة و منظمة و بدون رموز JSON — نص للمتعلم مباشرة، بلا أسطر \
التحية الوهمية.
"""


def _style_line(difficulty_level: str | None) -> str:
    """Pick the optional depth instruction for this question."""

    level = (difficulty_level or "").strip().lower()
    style = _DIFFICULTY_STYLE.get(level, _DIFFICULTY_STYLE["normal"])
    return f"7. مستوى العمق المطلوب عشان همه يعمق: {style}" if level else _DIFFICULTY_STYLE["normal"]


def _format_system_message(difficulty_level: str | None) -> str:
    """Fill in the exact strings the model needs to echo back."""

    return "\n".join(
        line
        .replace("{CITATION_EXAMPLE_FORMAT}", CITATION_EXAMPLE_FORMAT)
        .replace("{NOT_FOUND_MESSAGE}", NOT_FOUND_MESSAGE)
        .replace("{STYLE_LINE}", _style_line(difficulty_level))
        for line in SYSTEM_PROMPT.splitlines()
    )


def _clean_history(history: Iterable[dict[str, str]] | None) -> list[dict[str, str]]:
    """Validate and cap the conversation history sent back to the model."""

    settings = get_settings()
    cleaned: list[dict[str, str]] = []

    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        cleaned.append({"role": role, "content": content[:8000]})
        if len(cleaned) >= settings.rag_max_history_messages:
            break

    return cleaned


def _context_block(matches: list[RetrievedChunk]) -> str:
    """Render retrieved chunks with the exact citation labels to use."""

    blocks = []
    for index, match in enumerate(matches, start=1):
        page = match.page or 1
        blocks.append(
            f"[المصدر {index}: {match.filename} — صفحة {page}]\n{match.text}"
        )
    return "\n\n---\n\n".join(blocks)


def _build_user_prompt(message: str, matches: list[RetrievedChunk]) -> str:
    return (
        "عندي الأجزاء دي من ملفات الكورس (ده كل اللي مسموح بيها):\n\n"
        f"{_context_block(matches)}\n\n"
        "---\n\n"
        f"سؤال الطالب: {message}\n\n"
        "جاوب بناءً على المقاطع دي فقط، وطبّق القواعد بالحرف."
    )


# ---------------------------------------------------------------------------
# Citation validation
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Loose filename matching so small derivations don't kill citations."""

    return text.strip().casefold()


def extract_citations(
    reply: str,
    matches: list[RetrievedChunk],
) -> list[TutorCitation]:
    """Parse ``[filename — صفحة N]`` markers *and* verify them against matches.

    This is the anti-fabrication guard: the structured citations the API
    returns can only point at chunks which were retrieved, so a hallucinated
    page or filename cannot reach the client (even if the model emitted one).
    """

    if not matches:
        return []

    exact = {
        (*_normalise(chunk.filename), chunk.page or 0): chunk for chunk in matches
    }
    seen: set[tuple[str, int]] = set()

    citations: list[TutorCitation] = []
    for raw_filename, raw_page in _CITATION_RE.findall(reply or ""):
        key = (_normalise(raw_filename), int(raw_page))

        if key in seen:
            continue
        seen.add(key)

        chunk = exact.get(key)
        if chunk is None:
            # The model may slightly mangle the filename; the SPAN however is
            # authoritative -- a citation whose page was never retrieved is
            # dropped, so fabricated page numbers cannot slip through.
            chunk = next(
                (
                    match
                    for match in matches
                    if (match.page or 0) == key[1]
                    and (
                        key[0] in _normalise(match.filename)
                        or _normalise(match.filename) in key[0]
                    )
                ),
                None,
            )
        if chunk is None:
            logger.info("Dropping unverified citation %r:%s", raw_filename, raw_page)
            continue

        citations.append(TutorCitation(filename=chunk.filename, page=chunk.page or 0))

    return citations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def ask(
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    difficulty_level: str | None = None,
    llm: LLMService | None = None,
    store: Any | None = None,
) -> TutorAnswer:
    """Answer one student question, strictly grounded in published material."""

    store = store or vs_module.get_vector_store()

    # Nothing indexed yet -> answer from the same refusal string, without
    # bothering the LLM (there is literally nothing to ground on).
    if store.count() == 0:
        return TutorAnswer(
            reply=f"{NOT_FOUND_MESSAGE}\n{NO_INDEX_HINT}",
            citations=[],
            retrieved=0,
            model="",
            used_index=False,
        )

    matches = store.search(message)

    service = llm or get_llm_service()
    messages = [
        {"role": "system", "content": _format_system_message(difficulty_level)},
        *_clean_history(history),
        {"role": "user", "content": _build_user_prompt(message, matches)},
    ]

    result = service.chat(messages, temperature=get_settings().rag_temperature)

    reply = result.content
    citations = extract_citations(reply, matches)

    return TutorAnswer(
        reply=reply,
        citations=citations,
        retrieved=len(matches),
        model=result.model,
        used_index=True,
    )
