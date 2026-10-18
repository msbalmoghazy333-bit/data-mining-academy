"""Content generation & draft/publish tests.

The LLM is replaced by a deterministic stub that emits canned JSON, so the
suite exercises *our* parsing, validation, reconciliation and persistence logic
without any network access or API key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.models import DocumentChunk, Flashcard, Lesson, Question, SourceFile, Topic
from app.models.enums import MasteryStatus, SourceFileStatus
from app.services import content_generator
from app.services.content_generator import (
    NoChunksError,
    NoDraftError,
    generate_content,
    normalize_title,
    publish_content,
)
from app.services.llm_service import (
    LLMInvalidOutput,
    LLMResult,
    LLMService,
    LLMUsage,
    extract_json_payload,
)
from tests.helpers import build_pdf

# ---------------------------------------------------------------------------
# Fixtures & fakes
# ---------------------------------------------------------------------------


def _topic_payload(
    title_en: str = "Clustering",
    title_ar: str = "العناجمة",
    chunk_indexes: list[int] | None = None,
    question_seed: str = "q",
) -> dict:
    """A payload that satisfies every constraint in ``GeneratedTopic``."""

    return {
        "title_en": title_en,
        "title_ar": title_ar,
        "chunk_indexes": chunk_indexes or [0, 1],
        "lesson": {
            "content_ar": "# درس العناجمة\n\nشرح مبسط مع مثال محلول خطوة بخطوة.",
            "objectives": ["فهم فكرة التجميع", "تطبيق K-Means"],
            "prerequisites": ["أساسيات الإحصاء"],
            "english_terminology": [
                {
                    "term": "Clustering",
                    "arabic": "العناجمة",
                    "definition": "تقسيم البيانات غير الموسومة إلى مجموعات متجانسة.",
                }
            ],
            "formulas": [
                {"name": "SSE", "latex": "\\sum (x - c)^2", "note": "قياس تقارب المراكز"}
            ],
            "comparisons": [
                {
                    "topic_a": "K-Means",
                    "topic_b": "DBSCAN",
                    "aspect": "عدد المجموعات",
                    "detail": "K-Means يتطلب تحديد K مسبقًا بينما DBSCAN يكتشفه.",
                }
            ],
            "summary": "الخلاصة: التجميع يقسم البيانات حسب التشابه.",
        },
        "flashcards": [
            {"front": f"{question_seed} بطاقة {i}", "back": f"إجابة البطاقة {i}"}
            for i in range(1, 6)
        ],
        "questions": [
            {
                "type": "mcq",
                "question_text": f"{question_seed} سؤال سهل {i}",
                "options": ["أ", "ب", "ج"],
                "correct_answer": "أ",
                "explanation": "لأن الخيار أ صحيح.",
                "difficulty": "easy",
            }
            for i in range(1, 3)
        ]
        + [
            {
                "type": "true_false",
                "question_text": f"{question_seed} سؤال متوسط {i}",
                "options": ["صح", "خطأ"],
                "correct_answer": "صح",
                "explanation": "التجميع بلا موسوم يُعد unsupervised.",
                "difficulty": "medium",
            }
            for i in range(1, 3)
        ]
        + [
            {
                "type": "short_answer",
                "question_text": f"{question_seed} سؤال صعب {i}",
                "options": [],
                "correct_answer": "K-Means يعيد توزيع النقاط على أقرب مركز.",
                "explanation": "هذه هي خطوة التخصيص في الخوارزمية.",
                "difficulty": "hard",
            }
            for i in range(1, 3)
        ],
    }


def _analysis_payload(topics: list[dict]) -> str:
    import json

    return json.dumps({"topics": topics}, ensure_ascii=False)


def _lesson_payload(topic: dict) -> str:
    import json

    return json.dumps(topic, ensure_ascii=False)


class FakeLLM(LLMService):
    """Scripted stand-in for OpenRouter.

    Overrides only :meth:`chat`, so :meth:`chat_json` (parsing + schema
    validation) is still the real implementation under test.
    """

    def __init__(self, responses: list[str]) -> None:
        self.settings = get_settings()
        self._client = None
        self._responses = list(responses)
        self.prompts: list[list[dict[str, str]]] = []

    @property
    def configured(self) -> bool:
        return True

    def chat(self, messages, **kwargs) -> LLMResult:
        self.prompts.append(messages)
        if not self._responses:
            raise AssertionError("FakeLLM ran out of scripted responses")
        return LLMResult(
            content=self._responses.pop(0),
            model="fake/test-model",
            usage=LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )


def _seed_file(db, upload_dir: Path, *, pages: int = 2, chunks: int = 2) -> SourceFile:
    """Insert a ready-for-review file with real chunks."""

    payload = build_pdf(["page one content " * 20, "page two content " * 20])
    path = upload_dir / "abc1234567890abc-lecture.pdf"
    path.write_bytes(payload)

    import hashlib

    source = SourceFile(
        filename="lecture.pdf",
        file_hash=hashlib.sha256(payload).hexdigest(),
        file_type="pdf",
        file_size=len(payload),
        status=SourceFileStatus.READY_FOR_REVIEW.value,
    )
    db.add(source)
    db.flush()

    for index in range(chunks):
        db.add(
            DocumentChunk(
                file_id=source.id,
                chunk_index=index,
                content=f"Clustering is unsupervised. Chunk number {index}. " * 30,
                page_or_slide_number=index + 1,
            )
        )
    db.commit()
    db.refresh(source)
    return source


# ===========================================================================
# JSON extraction
# ===========================================================================


class TestExtractJsonPayload:
    def test_bare_json(self):
        assert extract_json_payload('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        text = 'Sure!\n```json\n{"topics": [1, 2]}\n```\nHope that helps.'
        assert extract_json_payload(text) == {"topics": [1, 2]}

    def test_json_surrounded_by_prose(self):
        text = 'Here you go: {"ok": true} — let me know if you need more.'
        assert extract_json_payload(text) == {"ok": True}

    def test_nested_objects_and_strings_with_braces(self):
        payload = '{"a": {"b": "value with } brace"}, "c": [1, 2]}'
        assert extract_json_payload(payload) == {
            "a": {"b": "value with } brace"},
            "c": [1, 2],
        }

    def test_top_level_array(self):
        assert extract_json_payload("[1, 2, 3]") == [1, 2, 3]

    def test_arabic_text_is_preserved(self):
        import json

        raw = json.dumps({"title_ar": "العناجمة"}, ensure_ascii=False)
        assert extract_json_payload(raw)["title_ar"] == "العناجمة"

    def test_no_json_raises(self):
        with pytest.raises(LLMInvalidOutput):
            extract_json_payload("I could not answer that.")

    def test_empty_raises(self):
        with pytest.raises(LLMInvalidOutput):
            extract_json_payload("   ")


# ===========================================================================
# Title normalisation
# ===========================================================================


class TestNormalizeTitle:
    @pytest.mark.parametrize(
        ("a", "b"),
        [
            ("Clustering", "clustering"),
            ("Classification.", "classification"),
            ("Decision  Trees", "decision trees"),
            ("العناجمة", "العَنَاجِمَة"),  # diacritics folded
            ("تصنيف البيانات", "\u062a\u0635\u0646\u064a\u0641 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a"),
            ("الإشراف", "الاشراف"),  # alef hamza folded
            ("أنماط التجميع", "انماط التجميع"),
            # ta marbuta (U+0629) folds to ha (U+0647): العناجمة == العناجمه
            (
                "\u0627\u0644\u0639\u0646\u0627\u062c\u0645\u0647",
                "\u0627\u0644\u0639\u0646\u0627\u062c\u0645\u0629",
            ),
            # ...and the same folding works mid-word: التجميع == التجميع
            (
                "\u0627\u0644\u062a\u062c\u0645\u064a\u064a\u0647",
                "\u0627\u0644\u062a\u062c\u0645\u064a\u064a\u0629",
            ),
        ],
    )
    def test_cosmetic_differences_collapse(self, a: str, b: str):
        assert normalize_title(a) == normalize_title(b)

    def test_distinct_topics_stay_distinct(self):
        assert normalize_title("Clustering") != normalize_title("Classification")

    def test_empty_input(self):
        assert normalize_title("") == ""
        assert normalize_title("   ") == ""


# ===========================================================================
# Generate endpoint
# ===========================================================================


class TestGenerateEndpoint:
    URL = "/api/v1/files/{0}/generate"

    def test_generate_stages_a_draft_and_creates_no_rows(self, client, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir)

        fake = FakeLLM(
            [
                _analysis_payload([{"title_en": "Clustering", "title_ar": "العناجمة",
                                    "chunk_indexes": [0]}]),
                _lesson_payload(_topic_payload()),
            ]
        )
        _patch_fake_llm(fake)

        response = client.post(self.URL.format(source.id))

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["topic_count"] == 1
        assert body["new_topics"] == 1
        assert body["existing_topics"] == 0
        assert body["model"] == "fake/test-model"
        assert body["topics"][0]["title_en"] == "Clustering"
        assert body["topics"][0]["is_new"] is True

        # Critical: nothing was written to the syllabus.
        assert db_session.query(Topic).count() == 0
        assert db_session.query(Lesson).count() == 0
        assert db_session.query(Question).count() == 0

        db_session.refresh(source)
        assert source.has_draft is True
        assert source.status == SourceFileStatus.READY_FOR_REVIEW.value

    def test_generate_marks_existing_topics(self, client, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir)
        db_session.add(Topic(title_en="Clustering", title_ar="العناجمة"))
        db_session.commit()

        # Note the deliberate diacritics: normalisation must still match.
        fake = FakeLLM(
            [
                _analysis_payload(
                    [{"title_en": "Clustering", "title_ar": "العَنَاجِمَة", "chunk_indexes": [0]}]
                ),
                _lesson_payload(_topic_payload()),
            ]
        )
        _patch_fake_llm(fake)

        body = client.post(self.URL.format(source.id)).json()

        assert body["existing_topics"] == 1
        assert body["new_topics"] == 0
        assert body["topics"][0]["is_new"] is False
        # Still no duplicate topic created.
        assert db_session.query(Topic).count() == 1

    def test_generate_without_chunks_is_409(self, client, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir, chunks=0)

        response = client.post(self.URL.format(source.id))

        assert response.status_code == 409
        assert "no extracted chunks" in response.json()["detail"].lower()

    def test_generate_without_api_key_is_409(self, client, db_session, upload_dir, monkeypatch):
        source = _seed_file(db_session, upload_dir)
        monkeypatch.setattr(get_settings(), "openrouter_api_key", "")

        response = client.post(self.URL.format(source.id))

        assert response.status_code == 409
        assert "OPENROUTER_API_KEY" in response.json()["detail"]

    def test_generate_unknown_file_is_404(self, client):
        assert client.post(self.URL.format(9999)).status_code == 404

    def test_failed_file_cannot_be_generated(self, client, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir)
        source.status = SourceFileStatus.FAILED.value
        source.error_message = "parser crashed"
        db_session.commit()

        response = client.post(self.URL.format(source.id))

        assert response.status_code == 409
        assert "retry" in response.json()["detail"].lower()

    def test_generation_rejects_schema_violation(self, client, db_session, upload_dir):
        """Only 5 flashcards are allowed -- a model returning 3 must not stage."""

        source = _seed_file(db_session, upload_dir)

        bad = _topic_payload()
        bad["flashcards"] = bad["flashcards"][:3]

        fake = FakeLLM(
            [
                _analysis_payload([{"title_en": "Clustering", "title_ar": "العناجمة",
                                    "chunk_indexes": [0]}]),
                _lesson_payload(bad),
            ]
        )
        _patch_fake_llm(fake)

        # The per-topic failure is swallowed so one bad topic cannot kill the
        # run; with a single topic that means nothing is staged.
        response = client.post(self.URL.format(source.id))

        assert response.status_code == 422
        assert "No topic produced usable content" in response.json()["detail"]


# ===========================================================================
# Publish endpoint
# ===========================================================================


def _generate(client, db_session, upload_dir, *, topics=None, topic_seed="q"):
    """Stage a draft and return the SourceFile."""

    source = _seed_file(db_session, upload_dir)
    topics = topics or [
        {"title_en": "Clustering", "title_ar": "العناجمة", "chunk_indexes": [0, 1]}
    ]

    responses = [
        _analysis_payload(
            [{"title_en": t["title_en"], "title_ar": t["title_ar"],
              "chunk_indexes": t.get("chunk_indexes", [0])} for t in topics]
        )
    ]
    for index, topic in enumerate(topics):
        responses.append(
            _lesson_payload(
                _topic_payload(
                    title_en=topic["title_en"],
                    title_ar=topic["title_ar"],
                    chunk_indexes=topic.get("chunk_indexes", [0, 1]),
                    question_seed=f"{topic_seed}-{index}",
                )
            )
        )

    _patch_fake_llm(FakeLLM(responses))
    response = client.post(f"/api/v1/files/{source.id}/generate")
    assert response.status_code == 200, response.text
    return source


def _patch_fake_llm(fake: FakeLLM) -> None:
    """Route content_generator's LLM lookups at our stub."""

    from app.services import content_generator as cg

    cg.get_llm_service = lambda: fake


@pytest.fixture(autouse=True)
def _restore_llm_factory():
    """Undo `_patch_fake_llm` so tests cannot leak a fake into each other."""

    from app.services import content_generator as cg

    original = cg.get_llm_service
    yield
    cg.get_llm_service = original


class TestPublishEndpoint:
    URL = "/api/v1/files/{0}/publish"

    def test_publish_creates_full_syllabus(self, client, db_session, upload_dir):
        source = _generate(client, db_session, upload_dir)

        response = client.post(self.URL.format(source.id))

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["status"] == SourceFileStatus.PUBLISHED.value
        assert body["topics_created"] == 1
        assert body["lessons_created"] == 1
        assert body["questions_created"] == 6
        assert body["flashcards_created"] == 5
        assert "nothing was deleted" in body["message"]

        topic = db_session.query(Topic).one()
        assert topic.title_en == "Clustering"
        assert len(topic.questions) == 6
        assert len(topic.flashcards) == 5
        assert len(topic.lessons) == 1
        assert topic.lessons[0].summary

        db_session.refresh(source)
        assert source.status == SourceFileStatus.PUBLISHED.value

    def test_questions_span_all_difficulties(self, client, db_session, upload_dir):
        source = _generate(client, db_session, upload_dir)
        client.post(self.URL.format(source.id))

        topic = db_session.query(Topic).one()
        assert {q.difficulty for q in topic.questions} == {"easy", "medium", "hard"}
        assert {q.type for q in topic.questions} == {"mcq", "true_false", "short_answer"}

    def test_questions_carry_a_source_citation(self, client, db_session, upload_dir):
        source = _generate(client, db_session, upload_dir)
        client.post(self.URL.format(source.id))

        topic = db_session.query(Topic).one()
        # Chunks 0 and 1 sit on pages 1-2, so the citation must span them.
        assert all("lecture.pdf" in q.source_reference for q in topic.questions)
        assert all("page" in q.source_reference for q in topic.questions)

    def test_publish_without_draft_is_409(self, client, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir)

        response = client.post(self.URL.format(source.id))

        assert response.status_code == 409
        assert "generate" in response.json()["detail"].lower()

    def test_publish_unknown_file_is_404(self, client):
        assert client.post(self.URL.format(4242)).status_code == 404


# ===========================================================================
# The "never destroy anything" guarantees
# ===========================================================================


class TestPublishIsAdditive:
    URL = "/api/v1/files/{0}/publish"

    def test_republishing_is_idempotent(self, client, db_session, upload_dir):
        source = _generate(client, db_session, upload_dir)

        first = client.post(self.URL.format(source.id)).json()
        second = client.post(self.URL.format(source.id)).json()

        assert first["questions_created"] == 6
        assert second["questions_created"] == 0
        assert second["questions_skipped"] == 6
        assert second["flashcards_created"] == 0
        assert second["flashcards_skipped"] == 5
        assert second["topics_created"] == 0
        assert second["topics_matched"] == 1

        topic = db_session.query(Topic).one()
        assert len(topic.questions) == 6
        assert len(topic.flashcards) == 5

    def test_learner_progress_is_never_reset(self, client, db_session, upload_dir):
        """A mastered topic with quiz history must survive re-publishing."""

        source = _generate(client, db_session, upload_dir)
        client.post(self.URL.format(source.id))

        topic = db_session.query(Topic).one()
        topic.mastery_status = MasteryStatus.MASTERED.value

        from app.models import QuizAttempt

        db_session.add(
            QuizAttempt(topic_id=topic.id, score=5, total_questions=6, answers_json={})
        )
        db_session.commit()

        client.post(self.URL.format(source.id))
        db_session.refresh(topic)

        assert topic.mastery_status == MasteryStatus.MASTERED.value
        assert len(topic.quiz_attempts) == 1

    def test_existing_lesson_is_updated_not_duplicated(self, client, db_session, upload_dir):
        source = _generate(client, db_session, upload_dir)
        client.post(self.URL.format(source.id))

        # Re-generate needs its own scripted responses (the first were consumed).
        _patch_fake_llm(
            FakeLLM(
                [
                    _analysis_payload(
                        [{"title_en": "Clustering", "title_ar": "العناجمة", "chunk_indexes": [0]}]
                    ),
                    _lesson_payload(_topic_payload()),
                ]
            )
        )
        client.post(f"/api/v1/files/{source.id}/generate")
        body = client.post(self.URL.format(source.id)).json()

        assert body["lessons_updated"] == 1
        assert body["lessons_created"] == 0

        # Fresh SQL count, immune to any identity-map staleness.
        assert db_session.query(Lesson).count() == 1, "a second lesson row was created"

    def test_publishing_a_second_file_extends_the_bank(self, client, db_session, upload_dir):
        """A new lecture on the same topic must add, never replace."""

        first = _generate(client, db_session, upload_dir, topic_seed="a")
        client.post(self.URL.format(first.id))

        questions_before = db_session.query(Question).count()
        cards_before = db_session.query(Flashcard).count()

        # Second file, same topic, different question/flashcard text.
        import hashlib

        payload = build_pdf(["another lecture page"])
        (upload_dir / "def1234567890abc-second.pdf").write_bytes(payload)
        second = SourceFile(
            filename="second.pdf",
            file_hash=hashlib.sha256(payload).hexdigest(),
            file_type="pdf",
            file_size=len(payload),
            status=SourceFileStatus.READY_FOR_REVIEW.value,
        )
        db_session.add(second)
        db_session.flush()
        db_session.add(
            DocumentChunk(
                file_id=second.id, chunk_index=0, content="Clustering again.", page_or_slide_number=1
            )
        )
        db_session.commit()

        fake = FakeLLM(
            [
                _analysis_payload(
                    [{"title_en": "Clustering", "title_ar": "العناجمة", "chunk_indexes": [0]}]
                ),
                _lesson_payload(_topic_payload(question_seed="second")),
            ]
        )
        _patch_fake_llm(fake)
        assert client.post(f"/api/v1/files/{second.id}/generate").status_code == 200

        body = client.post(self.URL.format(second.id)).json()

        assert body["topics_created"] == 0
        assert body["topics_matched"] == 1
        assert body["lessons_updated"] == 1
        assert body["questions_created"] == 6
        assert body["flashcards_created"] == 5

        topic_after = db_session.query(Topic).one()
        assert db_session.query(Question).count() == questions_before + 6
        assert db_session.query(Flashcard).count() == cards_before + 5
        assert len(db_session.query(Topic).all()) == 1, "duplicate topic created"

    def test_other_files_are_untouched(self, client, db_session, upload_dir):
        first = _generate(client, db_session, upload_dir, topic_seed="a")
        client.post(self.URL.format(first.id))

        import hashlib

        payload = build_pdf(["unrelated"])
        (upload_dir / "xyz1234567890abc-other.pdf").write_bytes(payload)
        other = SourceFile(
            filename="other.pdf",
            file_hash=hashlib.sha256(payload).hexdigest(),
            file_type="pdf",
            file_size=len(payload),
            status=SourceFileStatus.READY_FOR_REVIEW.value,
        )
        db_session.add(other)
        db_session.commit()

        client.post(self.URL.format(first.id))

        db_session.refresh(other)
        assert other.status == SourceFileStatus.READY_FOR_REVIEW.value
        assert db_session.query(Topic).count() == 1


# ===========================================================================
# Service-level behaviour
# ===========================================================================


class TestGenerationService:
    def test_no_chunks_raises(self, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir, chunks=0)

        with pytest.raises(NoChunksError):
            generate_content(db_session, source, llm=FakeLLM([]))

    def test_publish_without_draft_raises(self, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir)

        with pytest.raises(NoDraftError):
            publish_content(db_session, source)

    def test_draft_is_retained_after_publish(self, db_session, upload_dir):
        source = _seed_file(db_session, upload_dir)

        _patch_fake_llm(
            FakeLLM(
                [
                    _analysis_payload(
                        [{"title_en": "Clustering", "title_ar": "العناجمة", "chunk_indexes": [0]}]
                    ),
                    _lesson_payload(_topic_payload()),
                ]
            )
        )
        generate_content(db_session, source)
        publish_content(db_session, source)

        # The draft stays so publishing can be audited / re-run.
        assert source.has_draft is True
