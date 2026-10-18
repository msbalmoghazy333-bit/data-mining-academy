"""Extraction, chunking and file-management tests.

Run from ``backend/``::

    python -m pytest tests/ -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models import DocumentChunk, SourceFile
from app.models.enums import SourceFileStatus
from app.services import chunker, extractor, storage
from app.services.extractor import ExtractedPage, clean_text, extract_pages
from tests.helpers import build_pdf, write_docx, write_pptx, write_txt

# Markers are unique per page so a mis-numbered page is unambiguous.
PAGE_MARKERS = [
    "INTRODUCTION_MARKER clustering is unsupervised learning",
    "CLASSIFICATION_MARKER supervised learning needs labels",
    "ASSOCIATION_MARKER support and confidence measure rules",
    "EVALUATION_MARKER cross validation estimates generalisation",
]


# ===========================================================================
# Text cleaning
# ===========================================================================


class TestCleanText:
    def test_collapses_runs_of_spaces_and_tabs(self):
        assert clean_text("a   b\t\tc") == "a b c"

    def test_normalises_windows_and_unix_newlines(self):
        assert clean_text("one\r\ntwo\rthree") == "one\ntwo\nthree"

    def test_strips_trailing_whitespace_per_line(self):
        assert clean_text("line one   \nline two\t") == "line one\nline two"

    def test_collapses_three_or_more_newlines_to_one_blank_line(self):
        assert clean_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_preserves_arabic_text_and_isolates_ltr(self):
        arabic = "العناجمة Clustering تقسيم البيانات"
        assert clean_text(f"  {arabic}  ") == arabic

    def test_empty_input(self):
        assert clean_text("") == ""


# ===========================================================================
# PDF extraction
# ===========================================================================


class TestPdfExtraction:
    def test_page_numbers_are_accurate(self, tmp_path: Path):
        """The headline requirement: page numbers must be exactly right."""

        path = tmp_path / "sample.pdf"
        path.write_bytes(build_pdf(PAGE_MARKERS))

        pages = extract_pages(path)

        assert len(pages) == len(PAGE_MARKERS)
        assert [p.page_number for p in pages] == [1, 2, 3, 4]

        for page, marker in zip(pages, PAGE_MARKERS):
            assert marker in page.text, f"page {page.page_number} lost its marker"

    def test_marker_does_not_leak_to_the_wrong_page(self, tmp_path: Path):
        path = tmp_path / "sample.pdf"
        path.write_bytes(build_pdf(PAGE_MARKERS))

        pages = extract_pages(path)

        for page in pages:
            others = [m for m in PAGE_MARKERS if m not in page.text]
            leaked = [m for m in others if m.split()[0] in page.text]
            assert leaked == [], f"page {page.page_number} contains {leaked}"

    def test_word_counts_are_reported(self, tmp_path: Path):
        path = tmp_path / "sample.pdf"
        path.write_bytes(build_pdf(["alpha beta gamma"]))

        pages = extract_pages(path)
        assert pages[0].word_count == 3

    def test_blank_pages_are_skipped_but_numbering_is_kept(self, tmp_path: Path):
        path = tmp_path / "sample.pdf"
        path.write_bytes(build_pdf(["first page", "", "third page"]))

        pages = extract_pages(path)
        # Empty middle page is dropped, but page 3 stays page 3.
        assert [p.page_number for p in pages] == [1, 3]

    def test_unsupported_extension_raises(self, tmp_path: Path):
        path = tmp_path / "evil.exe"
        path.write_bytes(b"MZ")

        with pytest.raises(extractor.ExtractionError, match="Unsupported file type"):
            extract_pages(path)

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(extractor.ExtractionError, match="File not found"):
            extract_pages(tmp_path / "nope.pdf")


# ===========================================================================
# PPTX extraction
# ===========================================================================


class TestPptxExtraction:
    def test_slide_numbers_are_accurate(self, tmp_path: Path):
        slides = [
            ["Slide one title", "first bullet"],
            ["Slide two title", "second bullet"],
            ["Slide three title", "third bullet"],
        ]
        path = write_pptx(tmp_path / "deck.pptx", slides)

        pages = extract_pages(path)

        assert [p.page_number for p in pages] == [1, 2, 3]
        assert "Slide one title" in pages[0].text
        assert "second bullet" in pages[1].text
        assert "third bullet" in pages[2].text

    def test_arabic_content_survives(self, tmp_path: Path):
        path = write_pptx(tmp_path / "ar.pptx", [["العناجمة هي تقسيم البيانات"]])
        pages = extract_pages(path)
        assert "العناجمة" in pages[0].text


# ===========================================================================
# DOCX extraction
# ===========================================================================


class TestDocxExtraction:
    def test_paragraphs_are_extracted(self, tmp_path: Path):
        path = write_docx(tmp_path / "doc.docx", ["First para", "Second para"])

        pages = extract_pages(path)
        assert pages[0].page_number == 1
        assert "First para" in pages[0].text
        assert "Second para" in pages[0].text

    def test_explicit_page_break_increments_page_number(self, tmp_path: Path):
        path = write_docx(
            tmp_path / "doc.docx",
            ["Before the break", "After the break"],
            page_break_before=1,
        )

        pages = extract_pages(path)

        assert [p.page_number for p in pages] == [1, 2]
        assert "Before the break" in pages[0].text
        assert "After the break" in pages[1].text


# ===========================================================================
# Plain text extraction
# ===========================================================================


class TestPlainTextExtraction:
    def test_form_feed_splits_pages(self, tmp_path: Path):
        path = write_txt(tmp_path / "notes.txt", ["page one text", "page two text"])

        pages = extract_pages(path)
        assert [p.page_number for p in pages] == [1, 2]
        assert pages[0].text == "page one text"
        assert pages[1].text == "page two text"

    def test_file_without_form_feed_is_one_page(self, tmp_path: Path):
        path = tmp_path / "single.txt"
        path.write_text("just one page", encoding="utf-8")

        pages = extract_pages(path)
        assert len(pages) == 1
        assert pages[0].page_number == 1


# ===========================================================================
# Chunking
# ===========================================================================


def _wordy_page(page_number: int, words: int) -> ExtractedPage:
    """A deterministic page containing ``words`` words."""

    vocabulary = "clustering classification association rules mining data " "evaluation clusters labels"
    tokens = vocabulary.split()
    body = " ".join(tokens[i % len(tokens)] for i in range(words))
    return ExtractedPage(page_number=page_number, text=f"Paragraph one.\n\n{body}")


class TestChunker:
    def test_chunk_stays_within_the_500_800_band(self):
        chunks = chunker.chunk_pages([_wordy_page(1, 2000)])

        assert len(chunks) > 1
        for chunk in chunks:
            assert 500 <= chunk.word_count <= 800, chunk.word_count

    def test_chunk_never_spans_two_pages(self):
        pages = [_wordy_page(1, 1200), _wordy_page(2, 1200)]
        chunks = chunker.chunk_pages(pages)

        # Each chunk cites exactly one page, and both pages appear.
        assert {c.page_or_slide_number for c in chunks} == {1, 2}

    def test_chunk_indexes_are_sequential_and_unique(self):
        pages = [_wordy_page(1, 1500), _wordy_page(2, 900)]
        chunks = chunker.chunk_pages(pages)

        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_small_page_produces_a_single_small_chunk(self):
        chunks = chunker.chunk_pages([ExtractedPage(page_number=1, text="A short slide.")])

        assert len(chunks) == 1
        assert chunks[0].page_or_slide_number == 1

    def test_empty_page_produces_no_chunks(self):
        assert chunker.chunk_pages([ExtractedPage(page_number=1, text="   ")]) == []

    def test_arabic_text_is_chunked_without_corruption(self):
        sentence = "تُعدّ العناجمة من أساسيّات تحليل البيانات غير الموسومة. "
        text = " ".join(sentence * 40 for _ in range(1))

        chunks = chunker.chunk_pages([ExtractedPage(page_number=1, text=text)])

        assert chunks, "Arabic text produced no chunks"
        assert all("العناجمة" in c.content for c in chunks)
        assert all(c.page_or_slide_number == 1 for c in chunks)

    def test_overlong_paragraph_is_split_by_sentence(self):
        sentence = "Data mining discovers hidden patterns in large datasets. "
        chunks = chunker.chunk_pages([ExtractedPage(page_number=1, text=sentence * 200)])

        assert len(chunks) > 1
        assert all(c.word_count <= 800 for c in chunks)

    def test_page_number_metadata_is_preserved_end_to_end(self):
        pages = [ExtractedPage(page_number=n, text="clustering " * 400) for n in (1, 2, 3)]
        chunks = chunker.chunk_pages(pages)

        assert chunks[0].page_or_slide_number == 1
        assert chunks[-1].page_or_slide_number == 3


class TestChunkerPageMerging:
    """The slide-merging mode used by the pipeline by default."""

    @staticmethod
    def _slides(count: int, words_per_slide: int) -> list[ExtractedPage]:
        body = " ".join(["clustering"] * words_per_slide)
        return [
            ExtractedPage(page_number=n, text=f"Slide {n} title.\n\n{body}")
            for n in range(1, count + 1)
        ]

    def test_merging_combines_short_slides(self):
        pages = self._slides(20, 25)

        strict = chunker.chunk_pages(pages)
        merged = chunker.chunk_pages(pages, merge_short_pages=True)

        assert len(merged) < len(strict)
        # Merged chunks land in the 500-800 word band the slides could not hit.
        assert all(c.word_count <= 800 for c in merged)
        assert max(c.word_count for c in merged) >= 500

    def test_merged_chunk_cites_its_first_slide(self):
        merged = chunker.chunk_pages(self._slides(20, 25), merge_short_pages=True)

        cited = [c.page_or_slide_number for c in merged]
        assert cited == sorted(cited)
        assert cited[0] == 1

    def test_max_page_span_caps_how_many_slides_are_combined(self):
        pages = self._slides(20, 25)

        merged = chunker.chunk_pages(
            pages, merge_short_pages=True, max_page_span=3, target_words=10_000
        )

        # 20 slides at 3 per chunk -> at least 7 chunks.
        assert len(merged) >= 7

    def test_a_huge_page_is_never_merged_away(self):
        pages = [
            ExtractedPage(page_number=1, text="clustering " * 900),  # over the ceiling
            ExtractedPage(page_number=2, text="short slide"),
        ]

        merged = chunker.chunk_pages(pages, merge_short_pages=True)

        first = next(c for c in merged if c.page_or_slide_number == 1)
        assert first.word_count <= 800

    def test_strict_mode_remains_the_default(self):
        pages = self._slides(20, 25)

        assert len(chunker.chunk_pages(pages)) == 20


# ===========================================================================
# Storage
# ===========================================================================


class TestStorage:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("../../etc/passwd", "passwd"),
            ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
            ("a<b>:c\".pdf", "a_b__c_.pdf"),
            ("   spaced   name.pdf", "spaced name.pdf"),
            ("", "unnamed"),
        ],
    )
    def test_sanitize_filename_blocks_traversal(self, raw: str, expected: str):
        assert storage.sanitize_filename(raw) == expected

    def test_sha256_bytes_matches_hashlib(self):
        import hashlib

        payload = b"data mining academy"
        assert storage.sha256_bytes(payload) == hashlib.sha256(payload).hexdigest()

    def test_stored_name_is_hash_addressed(self):
        name = storage.build_stored_name("a" * 64, "lecture.pdf")
        assert name == f"{'a' * 16}-lecture.pdf"


# ===========================================================================
# API: upload / list / preview / retry / delete
# ===========================================================================


def _upload(client, filename: str, payload: bytes, content_type: str = "application/pdf"):
    return client.post(
        "/api/v1/files/upload",
        files={"file": (filename, payload, content_type)},
    )


class TestUploadEndpoint:
    def test_upload_pdf_returns_201_and_ready_status(self, client, tmp_path: Path):
        payload = build_pdf(PAGE_MARKERS)

        response = _upload(client, "lecture.pdf", payload)

        assert response.status_code == 201, response.text
        body = response.json()

        assert body["filename"] == "lecture.pdf"
        assert body["file_type"] == "pdf"
        assert body["status"] == SourceFileStatus.READY_FOR_REVIEW.value
        assert body["chunk_count"] > 0
        assert body["page_count"] == 4
        assert body["error_message"] is None

    def test_upload_persists_chunks_with_page_numbers(self, client, db_session):
        _upload(client, "lecture.pdf", build_pdf(PAGE_MARKERS))

        chunks = db_session.query(DocumentChunk).order_by(DocumentChunk.chunk_index).all()

        assert chunks, "no chunks were persisted"
        assert {c.page_or_slide_number for c in chunks} == {1, 2, 3, 4}
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_upload_stores_file_on_disk(self, client, upload_dir: Path):
        _upload(client, "lecture.pdf", build_pdf(PAGE_MARKERS))

        stored = [p for p in upload_dir.iterdir() if not p.name.startswith(".")]
        assert len(stored) == 1
        # Hash-addressed name guards against traversal and collisions.
        assert stored[0].name.endswith("-lecture.pdf")

    def test_duplicate_upload_is_rejected_with_409(self, client):
        payload = build_pdf(PAGE_MARKERS)

        first = _upload(client, "lecture.pdf", payload)
        second = _upload(client, "renamed-lecture.pdf", payload)

        assert first.status_code == 201
        assert second.status_code == 409

        detail = second.json()["detail"]
        assert detail["existing_file_id"] == first.json()["id"]

    def test_duplicate_upload_does_not_write_a_second_file(self, client, upload_dir: Path):
        payload = build_pdf(PAGE_MARKERS)
        _upload(client, "lecture.pdf", payload)
        _upload(client, "copy.pdf", payload)

        stored = [p for p in upload_dir.iterdir() if not p.name.startswith(".")]
        assert len(stored) == 1

    def test_unsupported_type_is_rejected_with_415(self, client):
        response = _upload(client, "malware.exe", b"MZ\x90", "application/octet-stream")
        assert response.status_code == 415
        assert "Unsupported file type" in response.json()["detail"]

    def test_empty_file_is_rejected_with_400(self, client):
        response = _upload(client, "empty.pdf", b"")
        assert response.status_code == 400

    def test_upload_pptx(self, client):
        from io import BytesIO

        from pptx import Presentation

        deck = Presentation()
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        slide.shapes.add_textbox(0, 0, 100, 100).text = "Deck slide one"
        buffer = BytesIO()
        deck.save(buffer)

        response = _upload(
            client,
            "deck.pptx",
            buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

        assert response.status_code == 201, response.text
        assert response.json()["status"] == SourceFileStatus.READY_FOR_REVIEW.value
        assert response.json()["page_count"] == 1

    def test_oversized_file_is_rejected_with_413(self, client, monkeypatch):
        from app.api.v1.endpoints import files as files_endpoint

        # The endpoint reads the limit per request, so patching the settings
        # accessor it calls is enough to force the guard.
        monkeypatch.setattr(
            files_endpoint,
            "get_settings",
            lambda: _TinyLimitSettings(),
        )

        response = _upload(client, "big.pdf", build_pdf(["a page"]))

        assert response.status_code == 413
        assert "limit" in response.json()["detail"]


class _TinyLimitSettings:
    """Stand-in settings object advertising a 0 MB upload cap."""

    max_upload_size_mb = 0


class TestListEndpoint:
    def test_list_returns_all_uploads(self, client):
        _upload(client, "a.pdf", build_pdf(["page one"]))
        _upload(client, "b.pdf", build_pdf(["page two"]))

        response = client.get("/api/v1/files")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_list_filters_by_status(self, client, db_session):
        _upload(client, "good.pdf", build_pdf(["page one"]))
        _upload(client, "broken.pdf", b"not a real pdf at all")

        response = client.get("/api/v1/files", params={"status": "failed"})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["filename"] == "broken.pdf"

    def test_list_includes_chunk_counts(self, client):
        _upload(client, "a.pdf", build_pdf(PAGE_MARKERS))

        items = client.get("/api/v1/files").json()["items"]
        assert items[0]["chunk_count"] > 0


class TestPreviewEndpoint:
    def test_preview_returns_pages_and_chunks(self, client):
        upload_id = _upload(client, "lecture.pdf", build_pdf(PAGE_MARKERS)).json()["id"]

        response = client.get(f"/api/v1/files/{upload_id}/preview")

        assert response.status_code == 200
        body = response.json()

        assert body["total_pages"] == 4
        assert [p["page_number"] for p in body["pages"]] == [1, 2, 3, 4]
        assert body["total_chunks"] == len(body["chunks"])
        assert body["chunks"][0]["page_or_slide_number"] is not None
        assert "INTRODUCTION_MARKER" in body["pages"][0]["full_text"]

    def test_preview_truncates_the_short_field(self, client):
        long_text = "word " * 200
        upload_id = _upload(client, "long.pdf", build_pdf([long_text])).json()["id"]

        preview = client.get(f"/api/v1/files/{upload_id}/preview").json()["pages"][0]

        assert len(preview["preview"]) == 300
        assert len(preview["full_text"]) > 300

    def test_preview_unknown_id_is_404(self, client):
        assert client.get("/api/v1/files/9999/preview").status_code == 404


class TestRetryEndpoint:
    def test_retry_recovers_a_previously_failed_file(self, client, db_session, monkeypatch):
        # 1. Upload something that cannot be parsed.
        # `pipeline` binds `extract_pages` at import time, so patch it there.
        from app.services import pipeline as pipeline_module

        def boom(_path):
            raise extractor.ExtractionError("simulated parser crash")

        monkeypatch.setattr(pipeline_module, "extract_pages", boom)
        upload_id = _upload(client, "broken.pdf", build_pdf(["x"])).json()["id"]

        failed = db_session.get(SourceFile, upload_id)
        assert failed.status == SourceFileStatus.FAILED.value
        assert "simulated parser crash" in failed.error_message

        # 2. Fix the parser and retry the same file.
        monkeypatch.undo()
        response = client.post(f"/api/v1/files/{upload_id}/retry")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == SourceFileStatus.READY_FOR_REVIEW.value
        assert body["error_message"] is None
        assert body["chunk_count"] > 0

    def test_retry_unknown_id_is_404(self, client):
        assert client.post("/api/v1/files/4242/retry").status_code == 404


class TestDeleteEndpoint:
    def test_delete_removes_row_chunks_and_bytes(self, client, db_session, upload_dir: Path):
        upload_id = _upload(client, "lecture.pdf", build_pdf(PAGE_MARKERS)).json()["id"]

        stored_before = [p for p in upload_dir.iterdir() if not p.name.startswith(".")]
        assert len(stored_before) == 1

        response = client.delete(f"/api/v1/files/{upload_id}")

        assert response.status_code == 200
        assert response.json()["deleted"] is True
        assert response.json()["deleted_chunks"] > 0

        assert db_session.get(SourceFile, upload_id) is None
        assert db_session.query(DocumentChunk).filter_by(file_id=upload_id).count() == 0
        assert list(upload_dir.glob("*-lecture.pdf")) == []

    def test_delete_unknown_id_is_404(self, client):
        assert client.delete("/api/v1/files/777").status_code == 404

    def test_delete_then_reupload_is_allowed(self, client):
        payload = build_pdf(PAGE_MARKERS)
        first_id = _upload(client, "lecture.pdf", payload).json()["id"]
        assert client.delete(f"/api/v1/files/{first_id}").status_code == 200

        # The row is gone, so the same bytes may be uploaded again.
        response = _upload(client, "lecture.pdf", payload)
        assert response.status_code == 201

        # SQLite may reuse the freed rowid, so assert on state, not identity.
        body = response.json()
        assert body["id"] == first_id
        assert body["status"] == SourceFileStatus.READY_FOR_REVIEW.value
        assert body["chunk_count"] > 0


# ===========================================================================
# Pipeline (service level)
# ===========================================================================


class TestPipeline:
    def test_processing_marks_file_ready_for_review(self, db_session, upload_dir: Path):
        from app.services import pipeline

        stored = storage.save_bytes(build_pdf(PAGE_MARKERS), "lecture.pdf")
        source = SourceFile(
            filename=stored.original_name,
            file_hash=stored.file_hash,
            file_type=stored.file_type,
            file_size=stored.size,
            status=SourceFileStatus.UPLOADED.value,
        )
        db_session.add(source)
        db_session.flush()

        result = pipeline.process_source_file(db_session, source)

        assert source.status == SourceFileStatus.READY_FOR_REVIEW.value
        assert source.error_message is None
        assert result.page_count == 4
        assert result.chunk_count > 0

    def test_rerunning_the_pipeline_does_not_duplicate_chunks(self, db_session, upload_dir: Path):
        from app.services import pipeline

        stored = storage.save_bytes(build_pdf(PAGE_MARKERS), "lecture.pdf")
        source = SourceFile(
            filename=stored.original_name,
            file_hash=stored.file_hash,
            file_type=stored.file_type,
            file_size=stored.size,
            status=SourceFileStatus.UPLOADED.value,
        )
        db_session.add(source)
        db_session.flush()

        pipeline.process_source_file(db_session, source)
        first_count = db_session.query(DocumentChunk).filter_by(file_id=source.id).count()

        pipeline.process_source_file(db_session, source)
        second_count = db_session.query(DocumentChunk).filter_by(file_id=source.id).count()

        assert first_count == second_count
        indexes = [
            c.chunk_index
            for c in db_session.query(DocumentChunk).filter_by(file_id=source.id)
        ]
        assert indexes == sorted(set(indexes))

    def test_unparseable_file_marks_failed_with_message(self, db_session, upload_dir: Path):
        from app.services import pipeline

        stored = storage.save_bytes(b"%PDF-1.4\nthis is truncated", "bad.pdf")
        source = SourceFile(
            filename=stored.original_name,
            file_hash=stored.file_hash,
            file_type=stored.file_type,
            file_size=stored.size,
            status=SourceFileStatus.UPLOADED.value,
        )
        db_session.add(source)
        db_session.flush()

        result = pipeline.process_source_file(db_session, source)

        assert source.status == SourceFileStatus.FAILED.value
        assert source.error_message
        assert result.chunk_count == 0
