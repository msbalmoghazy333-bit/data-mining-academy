"""On-demand translation for assessment content.

Questions are authored in **English** (the exam language), so this service is
what produces the Arabic rendering shown by the per-question "show in Arabic"
toggle in the UI. It is the only place that calls the LLM purely to translate,
and it caches aggressively so the same string is never paid for twice inside
one process.

Design notes:

* One LLM round-trip and one cache write per *batch* of new strings; duplicate
  and already-cached inputs cost nothing.
* The model must return exactly one translation per input, in order; a
  mismatch is an ``LLMInvalidOutput`` (never silently mis-aligned).
* Failures reuse the shared ``LLMError`` family so the endpoint can map them to
  409 (no key) / 502 (provider) exactly like the rest of the app.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.services.llm_service import (
    LLMInvalidOutput,
    LLMService,
    get_llm_service,
)

logger = logging.getLogger(__name__)

SUPPORTED_TARGETS = ("ar", "en")

# Guard rails mirrored by the request schema.
MAX_TEXTS = 20
MAX_TEXT_LENGTH = 2000

#: Bounded LRU: (target, source_text) -> translated_text.
_CACHE_MAX_ENTRIES = 500
_cache: "OrderedDict[tuple[str, str], str]" = OrderedDict()


class TranslationPayload(BaseModel):
    """The strict shape we require back from the model."""

    translations: list[str] = Field(min_length=1)


@dataclass(slots=True)
class TranslationResult:
    """Translations in input order plus provenance."""

    translations: list[str]
    target: str
    model: str = ""
    cached: bool = False


_AR_SYSTEM = """\
أنت مترجم أكاديمي متخصص في تعدين البيانات. تُعطى لك نصوص إنجليزية (أسئلة امتحان \
وخياراتها)، وتُعيد ترجمتها للعربية المصرية الواضحة.

قواعد:
1. حافظ على المصطلح الأكاديمي الإنجليزي كما هو (K-Means، DBSCAN، Clustering، \
Supervised Learning ...) ولا تترجمه — اكتب العربية حوله.
2. ترجم كل عنصر كما هو، بلا شرح ولا إضافات وبلا حذف.
3. أعد JSON فقط، بدون أي نص خارجه وبدون ```json، بالشكل:
   {"translations": ["...", "..."]}
4. عدد العناصر في translations لازم يساوي عدد النصوص المُعطاة وبنفس ترتيبها.
"""

_EN_SYSTEM = """\
You are an academic translator for a data-mining course. Translate each given \
text into clear academic English.

Rules:
1. Keep established technical terms as they are.
2. Translate every item verbatim, without explanation, addition or omission.
3. Reply with JSON only, no prose and no code fences, exactly like:
   {"translations": ["...", "..."]}
4. The number of items must equal the number of inputs, in the same order.
"""


def _system_prompt(target: str) -> str:
    return _AR_SYSTEM if target == "ar" else _EN_SYSTEM


def _build_user_prompt(texts: list[str]) -> str:
    numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(texts, start=1))
    return (
        "النصوص المطلوب ترجمتها بالترتيب:\n\n"
        f"{numbered}\n\n"
        "أعد JSON فقط بنفس الترتيب وبنفس العدد."
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def clear_cache() -> None:
    """Empty the process-wide translation cache (used by tests)."""

    _cache.clear()


def _cache_get(target: str, text: str) -> str | None:
    key = (target, text)
    value = _cache.get(key)
    if value is not None:
        _cache.move_to_end(key)
    return value


def _cache_put(target: str, text: str, value: str) -> None:
    key = (target, text)
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def translate_texts(
    texts: list[str],
    *,
    target: str = "ar",
    llm: LLMService | None = None,
) -> TranslationResult:
    """Translate ``texts`` into ``target``, deduping and caching.

    Returns translations in the **same order** as the input, including repeats.
    """

    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported translation target: {target!r}")

    cleaned = [text.strip() for text in texts]
    if not cleaned or any(not text for text in cleaned):
        raise ValueError("texts must be a non-empty list of non-blank strings")

    # Unique, not-yet-cached strings in first-seen order.
    missing: list[str] = []
    seen: set[str] = set()
    for text in cleaned:
        if text in seen:
            continue
        seen.add(text)
        if _cache_get(target, text) is None:
            missing.append(text)

    model_name = ""
    if missing:
        service = llm or get_llm_service()
        payload, result = service.chat_json(
            [
                {"role": "system", "content": _system_prompt(target)},
                {"role": "user", "content": _build_user_prompt(missing)},
            ],
            schema=TranslationPayload,
            temperature=0.0,
        )
        model_name = result.model

        if len(payload.translations) != len(missing):
            raise LLMInvalidOutput(
                "The model returned "
                f"{len(payload.translations)} translations for {len(missing)} inputs."
            )

        for source, translated in zip(missing, payload.translations):
            _cache_put(target, source, translated.strip())

    return TranslationResult(
        translations=[_cache_get(target, text) or text for text in cleaned],
        target=target,
        model=model_name,
        cached=not missing,
    )
