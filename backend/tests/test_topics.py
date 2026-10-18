"""Topic catalogue endpoint tests — the quiz filter's data source.

Deterministic and side-effect free: the endpoint only reads counts.
"""

from __future__ import annotations

from app.models import Flashcard, Question, Topic
from app.models.enums import Difficulty, MasteryStatus, QuestionType

TOPICS_URL = "/api/v1/topics"


def _topic(db, title_en: str, title_ar: str, mastery: str = MasteryStatus.NOT_STARTED.value) -> Topic:
    topic = Topic(title_en=title_en, title_ar=title_ar, mastery_status=mastery)
    db.add(topic)
    db.commit()
    return topic


def _question(db, topic_id: int) -> Question:
    question = Question(
        topic_id=topic_id,
        type=QuestionType.MCQ.value,
        question_text="سؤال؟",
        options_json=["أ", "ب"],
        correct_answer="أ",
        difficulty=Difficulty.EASY.value,
    )
    db.add(question)
    db.commit()
    return question


def _flashcard(db, topic_id: int) -> Flashcard:
    card = Flashcard(topic_id=topic_id, front="واجهة", back="ظهر", confidence_level="low")
    db.add(card)
    db.commit()
    return card


class TestTopicCatalogue:
    def test_empty_catalogue(self, client):
        response = client.get(TOPICS_URL)

        assert response.status_code == 200, response.text
        assert response.json() == {"total": 0, "items": []}

    def test_lists_topics_with_counts_and_mastery(self, client, db_session):
        clustering = _topic(db_session, "Clustering", "العنقدة", MasteryStatus.LEARNING.value)
        classification = _topic(db_session, "Classification", "التصنيف")
        _question(db_session, clustering.id)
        _question(db_session, clustering.id)
        _flashcard(db_session, clustering.id)

        body = client.get(TOPICS_URL).json()

        assert body["total"] == 2
        assert [item["title_en"] for item in body["items"]] == [
            "Classification",
            "Clustering",
        ]  # alphabetical by English title

        by_title = {item["title_en"]: item for item in body["items"]}
        assert by_title["Clustering"] == {
            "id": clustering.id,
            "title_en": "Clustering",
            "title_ar": "العنقدة",
            "mastery_status": MasteryStatus.LEARNING.value,
            "questions": 2,
            "flashcards": 1,
        }
        # A topic with no material still appears, with zeroed counts.
        assert by_title["Classification"]["questions"] == 0
        assert by_title["Classification"]["flashcards"] == 0
        assert by_title["Classification"]["mastery_status"] == MasteryStatus.NOT_STARTED.value

    def test_pagination(self, client, db_session):
        for index in range(3):
            _topic(db_session, f"Topic {index}", f"موضوع {index}")

        body = client.get(TOPICS_URL, params={"limit": 2, "offset": 1}).json()

        assert body["total"] == 3
        assert [item["title_en"] for item in body["items"]] == ["Topic 1", "Topic 2"]

    def test_limit_validation(self, client):
        assert client.get(TOPICS_URL, params={"limit": 0}).status_code == 422
        assert client.get(TOPICS_URL, params={"limit": 999}).status_code == 422
        assert client.get(TOPICS_URL, params={"offset": -1}).status_code == 422
