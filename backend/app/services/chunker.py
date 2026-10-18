"""Split extracted pages into embedding-sized semantic chunks.

Design decisions
----------------
* **A chunk never spans two pages.** Every chunk carries exactly one
  ``page_or_slide_number``, so citations ("PDF p. 7" / "slide 12") stay exact
  instead of approximate.
* **Balanced sizing.** Rather than greedily filling until a page runs out
  (which leaves one tiny tail chunk), the page's total word count is used to
  pick a target budget up front, so *every* chunk lands inside the required
  500-800 word band whenever the page is big enough to allow it.
* A page smaller than the band is emitted as one short chunk -- merging it
  with the next page would silently break the citation.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.services.extractor import ExtractedPage

DEFAULT_TARGET_WORDS = 650  # midpoint of the required 500-800 band
DEFAULT_MAX_WORDS = 800
DEFAULT_MIN_WORDS = 100
# Slides average ~25 words, so reaching the 500-word target can take ~20 of
# them. 32 leaves headroom while still bounding how fuzzy a citation gets.
DEFAULT_MAX_PAGE_SPAN = 32

# Split after an Arabic or Latin sentence terminator.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!؟?:؛!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


@dataclass(frozen=True, slots=True)
class ChunkData:
    """A chunk ready to be persisted as a :class:`DocumentChunk` row."""

    chunk_index: int  # 0-based, unique per file
    content: str
    page_or_slide_number: int | None
    word_count: int


def count_words(text: str) -> int:
    return len(text.split())


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, dropping empty fragments."""

    return [part.strip() for part in _PARAGRAPH_SPLIT.split(text) if part.strip()]


def split_sentences(text: str) -> list[str]:
    """Heuristic sentence split that also understands Arabic punctuation."""

    return [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]


def _split_words(text: str, budget: int) -> list[str]:
    """Last-resort split: hard-cut a fragment into ``budget``-sized pieces."""

    words = text.split()
    return [" ".join(words[i : i + budget]) for i in range(0, len(words), budget)]


def _to_fragments(paragraphs: list[str], budget: int) -> list[str]:
    """Break paragraphs into sentence-level fragments of at most ``budget``.

    Sentence boundaries are preferred because they keep meaning intact; a
    fragment with no terminator at all (common in slide bullet dumps) falls
    back to a balanced word cut.
    """

    fragments: list[str] = []

    for paragraph in paragraphs:
        if count_words(paragraph) <= budget:
            fragments.append(paragraph)
            continue

        for sentence in split_sentences(paragraph):
            if count_words(sentence) <= budget:
                fragments.append(sentence)
            else:
                pieces = _split_words(sentence, budget)
                fragments.extend(pieces)

    return fragments


def _pack(fragments: list[str], budget: int, maximum: int) -> list[str]:
    """Greedily group fragments, preferring ``budget`` and capped at ``maximum``."""

    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for fragment in fragments:
        words = count_words(fragment)

        # Hard cap: a single fragment must never push us past the ceiling.
        if current and current_words + words > maximum:
            chunks.append("\n\n".join(current))
            current, current_words = [], 0

        current.append(fragment)
        current_words += words

        # Preferred stopping point -- keeps chunks balanced rather than ragged.
        if current_words >= budget:
            chunks.append("\n\n".join(current))
            current, current_words = [], 0

    if current:
        # Absorb a small tail into the previous chunk when it still fits;
        # otherwise emit it on its own (it cannot span pages).
        if chunks and count_words(chunks[-1]) + current_words <= maximum:
            chunks[-1] = f"{chunks[-1]}\n\n" + "\n\n".join(current)
        else:
            chunks.append("\n\n".join(current))

    return chunks


def chunk_text(
    text: str,
    page_number: int | None = None,
    *,
    target_words: int = DEFAULT_TARGET_WORDS,
    max_words: int = DEFAULT_MAX_WORDS,
    min_words: int = DEFAULT_MIN_WORDS,
) -> list[ChunkData]:
    """Chunk one page's text into :class:`ChunkData` records."""

    text = text.strip()
    if not text:
        return []

    total_words = count_words(text)

    if total_words <= max_words:
        pieces = [text]
    else:
        # Choose a budget that divides the page evenly, then pack to it.
        piece_count = max(1, round(total_words / target_words))
        budget = min(math.ceil(total_words / piece_count), max_words)
        budget = max(budget, min_words)

        fragments = _to_fragments(split_paragraphs(text), budget)
        pieces = _pack(fragments, budget, max_words)

    return [
        ChunkData(
            chunk_index=index,
            content=content,
            page_or_slide_number=page_number,
            word_count=count_words(content),
        )
        for index, content in enumerate(pieces)
        if content.strip()
    ]


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    target_words: int = DEFAULT_TARGET_WORDS,
    max_words: int = DEFAULT_MAX_WORDS,
    min_words: int = DEFAULT_MIN_WORDS,
    merge_short_pages: bool = False,
    max_page_span: int = DEFAULT_MAX_PAGE_SPAN,
) -> list[ChunkData]:
    """Chunk every page, re-numbering chunks sequentially across the file.

    Parameters
    ----------
    merge_short_pages:
        Presentation slides carry only ~25 words each, so strict per-page
        chunking yields tiny chunks. When enabled, consecutive short pages are
        merged into a single chunk capped at ``max_words``. Citations then
        point at the **first** slide of the merged run, so the default
        (``False``) is preferred when exact per-slide attribution matters.
    max_page_span:
        Upper bound on how many pages a merged chunk may cover. Sized so a
        run of short slides can still reach ``target_words``.
    """

    chunks: list[ChunkData] = []

    if merge_short_pages:
        return _merge_pages(
            pages,
            target_words=target_words,
            max_words=max_words,
            max_page_span=max_page_span,
        )

    for page in pages:
        for chunk in chunk_text(
            page.text,
            page.page_number,
            target_words=target_words,
            max_words=max_words,
            min_words=min_words,
        ):
            chunks.append(
                ChunkData(
                    chunk_index=len(chunks),
                    content=chunk.content,
                    page_or_slide_number=chunk.page_or_slide_number,
                    word_count=chunk.word_count,
                )
            )

    return chunks


def _merge_pages(
    pages: list[ExtractedPage],
    *,
    target_words: int,
    max_words: int,
    max_page_span: int,
) -> list[ChunkData]:
    """Bundle consecutive short pages while the bundle stays under ``max_words``.

    A page that alone exceeds the ceiling is flushed out and split with the
    normal sentence-aware chunker, so no chunk ever breaches the hard cap.
    """

    chunks: list[ChunkData] = []
    current: list[ExtractedPage] = []
    current_words = 0

    def flush() -> None:
        nonlocal current, current_words
        if not current:
            return
        content = "\n\n".join(item.text for item in current)
        chunks.append(
            ChunkData(
                chunk_index=len(chunks),
                content=content,
                page_or_slide_number=current[0].page_number,
                word_count=count_words(content),
            )
        )
        current, current_words = [], 0

    for page in pages:
        page_words = page.word_count

        if page_words > max_words:
            # Oversized page: seal the pending bundle, then split this page on
            # its own using the sentence-aware path.
            flush()
            for piece in chunk_text(
                page.text,
                page.page_number,
                target_words=target_words,
                max_words=max_words,
            ):
                chunks.append(
                    ChunkData(
                        chunk_index=len(chunks),
                        content=piece.content,
                        page_or_slide_number=piece.page_or_slide_number,
                        word_count=piece.word_count,
                    )
                )
            continue

        over_weight = current and current_words + page_words > max_words
        over_span = current and len(current) >= max_page_span

        if over_weight or over_span:
            flush()

        current.append(page)
        current_words += page_words

        # Stop once the bundle is comfortably sized.
        if current_words >= target_words:
            flush()

    flush()

    return chunks
