"""Lesson viewer endpoint tests.

Read-only and offline: the endpoints only read published lessons, so these
tests seed the ORM directly and assert the JSON contract.
"""

from __future__ import annotations

from app.models import Lesson, Topic

LESSONS_URL = "/api/v1/lessons"


def _topic(db, title_en: str, title_ar: str) -> Topic:
    topic = Topic(title_en=title_en, title_ar=title_ar)
    db.add(topic)
    db.commit()
    return topic


def _lesson(
    db,
    topic_id: int,
    *,
    content: str = "## مقدمة\nنص الدرس",
    summary: str = "خلاصة سريعة",
    objectives: list | None = None,
    prerequisites: list | None = None,
    terminology: list | None = None,
    formulas: list | None = None,
    comparisons: list | None = None,
    language: str = "ar",
) -> Lesson:
    lesson = Lesson(
        topic_id=topic_id,
        content_ar=content,
        summary=summary,
        objectives=objectives if objectives is not None else ["هدف أول"],
        prerequisites=prerequisites if prerequisites is not None else [],
        english_terminology=terminology or [],
        formulas=formulas or [],
        comparisons=comparisons or [],
        language=language,
    )
    db.add(lesson)
    db.commit()
    return lesson


class TestLessonCatalogue:
    def test_empty_catalogue(self, client):
        response = client.get(LESSONS_URL)

        assert response.status_code == 200, response.text
        assert response.json() == {"total": 0, "items": []}

    def test_summaries_carry_titles_counts_and_no_body(self, client, db_session):
        clustering = _topic(db_session, "Clustering", "التجميع")
        classification = _topic(db_session, "Classification", "التصنيف")
        _lesson(
            db_session,
            clustering.id,
            content="## مقدمة\nنص",
            terminology=[{"term": "Centroid", "arabic": "المركز", "definition": "متوسط"}],
            formulas=[{"name": "K-Means", "latex": "argmin", "note": "للعناقيد"}],
            comparisons=[
                {"topic_a": "K-Means", "topic_b": "DBSCAN", "aspect": "K", "detail": "ثابت"}
            ],
        )
        _lesson(db_session, classification.id, content="", summary="")

        body = client.get(LESSONS_URL).json()

        assert body["total"] == 2
        # Syllabus order: topic id, then publish order.
        assert [item["topic_id"] for item in body["items"]] == [
            clustering.id,
            classification.id,
        ]

        first = body["items"][0]
        assert first["topic_title_en"] == "Clustering"
        assert first["topic_title_ar"] == "التجميع"
        assert first["language"] == "ar"
        assert first["content_chars"] == len("## مقدمة\nنص")
        assert first["terminology_count"] == 1
        assert first["formula_count"] == 1
        assert first["comparison_count"] == 1
        assert first["updated_at"]
        # The Markdown body is deliberately absent from the catalogue.
        assert "content_ar" not in first
        assert "english_terminology" not in first

    def test_topic_filter(self, client, db_session):
        clustering = _topic(db_session, "Clustering", "التجميع")
        classification = _topic(db_session, "Classification", "التصنيف")
        _lesson(db_session, clustering.id)
        _lesson(db_session, classification.id)
        _lesson(db_session, classification.id)

        body = client.get(LESSONS_URL, params={"topic_id": classification.id}).json()

        assert body["total"] == 2
        assert {item["topic_id"] for item in body["items"]} == {classification.id}

    def test_pagination(self, client, db_session):
        topic = _topic(db_session, "Clustering", "التجميع")
        for _ in range(3):
            _lesson(db_session, topic.id)

        body = client.get(LESSONS_URL, params={"limit": 2, "offset": 1}).json()

        assert body["total"] == 3
        assert len(body["items"]) == 2

    def test_query_validation(self, client):
        assert client.get(LESSONS_URL, params={"limit": 0}).status_code == 422
        assert client.get(LESSONS_URL, params={"limit": 999}).status_code == 422
        assert client.get(LESSONS_URL, params={"offset": -1}).status_code == 422
        assert client.get(LESSONS_URL, params={"topic_id": 0}).status_code == 422


class TestLessonDetail:
    def test_returns_body_and_every_structured_block(self, client, db_session):
        topic = _topic(db_session, "Association Rules", "قواعد الارتباط")
        lesson = _lesson(
            db_session,
            topic.id,
            content="# قواعد الارتباط\n\n- Support\n- Confidence",
            summary="الخلاصة",
            objectives=["تفهم Support", "تفهم Confidence"],
            prerequisites=["أساسيات الإحصاء"],
            terminology=[
                {"term": "Support", "arabic": "الدعم", "definition": "نسبة المعاملات"}
            ],
            formulas=[{"name": "Confidence", "latex": "P(B|A)", "note": "قوة القاعدة"}],
            comparisons=[
                {
                    "topic_a": "Support",
                    "topic_b": "Confidence",
                    "aspect": "المعنى",
                    "detail": "تغطية مقابل قوة",
                }
            ],
        )

        response = client.get(f"{LESSONS_URL}/{lesson.id}")

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["id"] == lesson.id
        assert body["topic_id"] == topic.id
        assert body["topic_title_en"] == "Association Rules"
        assert body["content_ar"].startswith("# قواعد الارتباط")
        assert body["content_chars"] == len("# قواعد الارتباط\n\n- Support\n- Confidence")
        assert body["objectives"] == ["تفهم Support", "تفهم Confidence"]
        assert body["prerequisites"] == ["أساسيات الإحصاء"]
        assert body["summary"] == "الخلاصة"
        assert body["english_terminology"] == [
            {"term": "Support", "arabic": "الدعم", "definition": "نسبة المعاملات"}
        ]
        assert body["formulas"] == [
            {"name": "Confidence", "latex": "P(B|A)", "note": "قوة القاعدة"}
        ]
        assert body["comparisons"] == [
            {
                "topic_a": "Support",
                "topic_b": "Confidence",
                "aspect": "المعنى",
                "detail": "تغطية مقابل قوة",
            }
        ]

    def test_missing_block_keys_fall_back_to_defaults(self, client, db_session):
        topic = _topic(db_session, "Clustering", "التجميع")
        lesson = _lesson(
            db_session,
            topic.id,
            terminology=[{"term": "Centroid"}],
            formulas=[{}],
        )

        body = client.get(f"{LESSONS_URL}/{lesson.id}").json()

        assert body["english_terminology"] == [
            {"term": "Centroid", "arabic": "", "definition": ""}
        ]
        assert body["formulas"] == [{"name": "", "latex": "", "note": ""}]

    def test_malformed_json_columns_do_not_break_the_endpoint(self, client, db_session):
        topic = _topic(db_session, "Clustering", "التجميع")
        lesson = _lesson(
            db_session,
            topic.id,
            objectives=["هدف", 7, None],
            terminology=["not-a-dict", None, 3],
            formulas={"latex": "not-a-list"},
        )

        response = client.get(f"{LESSONS_URL}/{lesson.id}")

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["objectives"] == ["هدف", "7"]
        assert body["english_terminology"] == []
        assert body["formulas"] == []
        assert body["comparison_count"] == 0

    def test_unknown_lesson_is_404(self, client):
        response = client.get(f"{LESSONS_URL}/4242")

        assert response.status_code == 404
        assert "4242" in response.json()["detail"]

    def test_lesson_without_content_is_still_readable(self, client, db_session):
        topic = _topic(db_session, "Clustering", "التجميع")
        lesson = _lesson(db_session, topic.id, content="", summary="")

        body = client.get(f"{LESSONS_URL}/{lesson.id}").json()

        assert body["content_ar"] == ""
        assert body["content_chars"] == 0
        assert body["objectives"] == ["هدف أول"]
