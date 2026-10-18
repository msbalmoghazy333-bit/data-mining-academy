"""Manual smoke check against the real course slides in the repo root.

Not part of the automated suite (the files are not committed fixtures), but
useful to confirm the pipeline handles real-world decks.

    python scripts_check_real_files.py
"""

from __future__ import annotations

from pathlib import Path

from app.services.chunker import chunk_pages
from app.services.extractor import extract_pages

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    slides = sorted(ROOT.glob("*.pptx"))
    print(f"Found {len(slides)} PowerPoint file(s) in {ROOT}\n")

    for path in slides:
        try:
            pages = extract_pages(path)
            strict = chunk_pages(pages)
            merged = chunk_pages(pages, merge_short_pages=True, max_page_span=32)
        except Exception as exc:
            print(f"  !! {path.name}: FAILED -> {exc}")
            continue

        words = sum(p.word_count for p in pages)

        print(f"  {path.name}")
        print(f"     slides={len(pages)}  words={words}")

        for label, chunks in (("strict ", strict), ("merged ", merged)):
            sizes = [c.word_count for c in chunks]
            if not sizes:
                continue
            print(
                f"     {label} chunks={len(chunks):3d}  "
                f"min={min(sizes):4d} max={max(sizes):4d} "
                f"avg={sum(sizes) // len(sizes):4d}"
            )

        if pages:
            snippet = pages[0].text[:80].replace("\n", " / ")
            print(f"     first slide:  {snippet}...")
        print()


if __name__ == "__main__":
    main()
