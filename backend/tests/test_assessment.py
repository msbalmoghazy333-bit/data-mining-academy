"""Assessment engine tests — generation, grading, mastery, flashcards, dashboard.

Fully deterministic: no LLM, no randomness asserted on (the draw is random,
but every assertion is structural).
"""

from __future__ import annotations

import hashlib

from app.models import Flashcard, Question, QuizAttempt, SourceFile, Topic
from app.models.enums import (
    ConfidenceLevel,
    Difficulty,
    MasteryStatus,
    QuestionType,
    SourceFileStatus,
)
from app.services import assessment
from app.services.assessment import (
    grade_answer,
    select_questions,
    submit_answers,
    update_mastery,
)

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _topic(db, title_en: str = "Clustering", title_ar: str = "العناجمة") -> Topic:
    topic = Topic(title_en=title_en, title_ar=title_ar)
    db.add(topic)
    db.commit()
    return topic


def _question(
    db,
    topic_id: int,
    *,
    qtype: str = QuestionType.MCQ.value,
    difficulty: str = Difficulty.EASY.value,
    text: str | None = None,
    options: list[str] | None = None,
    correct: str = "",
    explanation: str | None = "شرح الإجابة.",
    source: str = "lecture.pdf — page 3",
) -> Question:
    question = Question(
        topic_id=topic_id,
        type=qtype,
        question_text=text or "سؤال افتراضي؟",
        options_json=options if options is not None else ["أ", "ب", "ج"],
        correct_answer=correct,
        explanation=explanation,
        difficulty=difficulty,
        source_reference=source,
    )
    db.add(question)
    db.commit()
    return question


def _flashcard(
    db, topic_id: int, front: str = "بطاقة", confidence: str = "low"
) -> Flashcard:
    card = Flashcard(
        topic_id=topic_id, front=front, back="ظهر البطاقة", confidence_level=confidence
    )
    db.add(card)
    db.commit()
    return card


def _attempt(db, topic_id: int, score: int, total: int = 10) -> QuizAttempt:
    attempt = QuizAttempt(
        topic_id=topic_id, score=score, total_questions=total, answers_json={}
    )
    db.add(attempt)
    db.commit()
    return attempt


# ---------------------------------------------------------------------------
# Grading primitives
# ---------------------------------------------------------------------------


class TestGrading:
    def test_mcq_exact_and_casing(self, db_session):
        topic = _topic(db_session)
        question = _question(
            db_session,
            topic.id,
            text="أي خوارزمية لا تحتاج تحديد K؟",
            options=["K-Means", "DBSCAN", "Agglomerative"],
            correct="DBSCAN",
        )

        assert grade_answer(question, "DBSCAN")[0] is True
        assert grade_answer(question, " dbscan ")[0] is True, "casing/space tolerant"
        assert grade_answer(question, "K-Means")[0] is False
        assert grade_answer(question, "")[0] is False

    def test_mcq_letter_answer(self, db_session):
        topic = _topic(db_session)
        question = _question(
            db_session,
            topic.id,
            options=["أول", "ثاني", "ثالث"],
            correct="ثاني",
        )

        assert grade_answer(question, "ب")[0] is True, "Arabic letter index"
        assert grade_answer(question, "أ")[0] is False
        assert grade_answer(question, "(ب)")[0] is True, "parenthesised letter"

    def test_true_false_aliases(self, db_session):
        topic = _topic(db_session)
        true_q = _question(
            db_session,
            topic.id,
            qtype=QuestionType.TRUE_FALSE.value,
            options=["صح", "خطأ"],
            correct="صح",
        )
        false_q = _question(
            db_session,
            topic.id,
            qtype=QuestionType.TRUE_FALSE.value,
            options=["صح", "خطأ"],
            correct="خطأ",
        )

        assert grade_answer(true_q, "صح")[0] is True
        assert grade_answer(true_q, "true")[0] is True
        assert grade_answer(true_q, "خطأ")[0] is False
        assert grade_answer(false_q, "خطأ")[0] is True
        assert grade_answer(false_q, "false")[0] is True
        assert grade_answer(false_q, "صح")[0] is False

    def test_short_answer_keyword_overlap(self, db_session):
        topic = _topic(db_session)
        question = _question(
            db_session,
            topic.id,
            qtype=QuestionType.SHORT_ANSWER.value,
            options=[],
            correct="K-Means يعيد توزيع النقاط على أقرب مركز cluster center",
        )

        # ~78% keyword overlap passes the 60% short-answer threshold.
        is_correct, earned = grade_answer(
            question, "يعيد توزيع النقاط علي اقرب مركز cluster"
        )
        assert is_correct is True
        assert earned < 100

        # 56% overlap is consciously short of the bar.
        is_correct, earned = grade_answer(question, "بيوزع النقاط على أقرب مركز cluster")
        assert is_correct is False
        assert earned == 56

        is_correct, earned = grade_answer(question, "الشجرة الثنائية binary tree")
        assert is_correct is False
        assert earned == 0

        # Blank never scores.
        assert grade_answer(question, "") == (False, 0)

    def test_letter_index_out_of_range(self, db_session):
        topic = _topic(db_session)
        question = _question(db_session, topic.id, options=["أ", "ب"], correct="أ")
        # "ه" is the 5th letter but only 2 options exist -> never matches.
        assert grade_answer(question, "ه")[0] is False


# ---------------------------------------------------------------------------
# Quiz generation
# ---------------------------------------------------------------------------


class TestQuizGeneration:
    def _bank(self, db_session) -> dict[str, Topic]:
        clustering = _topic(db_session, "Clustering", "العناجمة")
        classification = _topic(db_session, "Classification", "التصنيف")

        _question(db_session, clustering.id, difficulty="easy", correct="خيار أ")
        _question(db_session, clustering.id, difficulty="easy", correct="خيار ب")
        _question(db_session, clustering.id, difficulty="hard", correct="خيار ج")
        _question(db_session, classification.id, difficulty="medium", correct="خيار د")
        _question(db_session, classification.id, difficulty="hard", correct="خيار هـ")

        return {"clustering": clustering, "classification": classification}

    def test_filter_by_difficulty(self, db_session):
        self._bank(db_session)

        draft = select_questions(db_session, difficulty="hard", count=10)

        assert len(draft.questions) == 2
        assert all(q.difficulty == "hard" for q in draft.questions)

    def test_filter_by_topics(self, db_session):
        topics = self._bank(db_session)

        draft = select_questions(db_session, topic_ids=[topics["clustering"].id], count=10)

        assert len(draft.questions) == 3
        assert all(q.topic_id == topics["clustering"].id for q in draft.questions)

    def test_count_capped_at_bank_size(self, db_session):
        self._bank(db_session)
        draft = select_questions(db_session, count=50)
        assert len(draft.questions) == 5
        assert draft.available_count == 5
        assert draft.requested_count == 50

    def test_no_match_returns_empty(self, db_session):
        self._bank(db_session)
        draft = select_questions(db_session, topic_ids=[987654], count=5)
        assert draft.questions == []


# ---------------------------------------------------------------------------
# Submission + mastery
# ---------------------------------------------------------------------------


class TestSubmission:
    def test_submission_grades_and_records(self, db_session):
        topic = _topic(db_session)
        easy = _question(db_session, topic.id, correct="الخيار الصح")
        q2 = _question(db_session, topic.id, correct="خيار خطأ")

        result = submit_answers(
            db_session,
            [
                {"question_id": easy.id, "answer": "الخيار الصح"},
                {"question_id": q2.id, "answer": "جواب تاني"},
            ],
        )

        assert result.score == 50
        assert result.correct_count == 1
        assert result.total_questions == 2
        assert not result.not_found

        # Answer key included with explanation + citation.
        first = result.per_question[0]
        assert first["is_correct"] is True
        assert first["expected"] == "الخيار الصح"
        assert first["explanation"] == "شرح الإجابة."
        assert first["source_reference"] == "lecture.pdf — page 3"

        group = result.topics[0]
        assert group.correct == 1 and group.total == 2
        # avg of 1 attempt = 50 → exactly at the learning threshold.
        assert group.updated_mastery == MasteryStatus.LEARNING.value

        # Attempt row persisted with graded answers.
        attempt = db_session.query(QuizAttempt).one()
        assert attempt.topic_id == topic.id
        assert attempt.score == 50
        assert attempt.answers_json[str(easy.id)]["is_correct"] is True

        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.LEARNING.value

    def test_not_found_answers_are_reported(self, db_session):
        topic = _topic(db_session)
        question = _question(db_session, topic.id, correct="أ")

        result = submit_answers(db_session, [{"question_id": 99999, "answer": "أ"}])

        assert result.not_found == [99999]
        assert result.total_questions == 0
        assert result.score == 0

    def test_multiple_topics_create_one_attempt_each(self, db_session):
        first = _topic(db_session, "Clustering", "العناجمة")
        second = _topic(db_session, "Classification", "التصنيف")

        q1 = _question(db_session, first.id, correct="أ")
        q2 = _question(db_session, second.id, correct="ب")

        result = submit_answers(
            db_session,
            [{"question_id": q1.id, "answer": "أ"}, {"question_id": q2.id, "answer": "أ"}],
        )

        assert result.score == 50
        attempts = db_session.query(QuizAttempt).all()
        assert len(attempts) == 2
        by_topic = {attempt.topic_id: attempt for attempt in attempts}
        assert by_topic[first.id].score == 100
        assert by_topic[second.id].score == 0


class TestMastery:
    def test_thresholds(self, db_session):
        topic = _topic(db_session)

        # Fresh topic keeps not_started.
        assert update_mastery(db_session, topic) == MasteryStatus.NOT_STARTED.value

        _attempt(db_session, topic.id, 85)
        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.MASTERED.value  # avg 85 >= 80

        _attempt(db_session, topic.id, 60)
        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.LEARNING.value  # avg 72.5

        # (85 + 60 + 0) / 3 = 48.3 → below the revision threshold.
        _attempt(db_session, topic.id, 0)
        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.NEEDS_REVISION.value

    def test_window_uses_only_last_three(self, db_session):
        topic = _topic(db_session)
        for score in (100, 100, 100):
            _attempt(db_session, topic.id, score)

        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.MASTERED.value

        # Window = last 3: (100, 100, 0) → avg 66.7 → demoted to learning.
        _attempt(db_session, topic.id, 0)
        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.LEARNING.value

        # Second weak attempt: (100, 0, 0) → avg 33.3 → demoted to revision.
        _attempt(db_session, topic.id, 0)
        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.NEEDS_REVISION.value

        # Recovery needs a consistent push: one good attempt gives
        # (100, 0, 0) = 33.3 → still revision...
        _attempt(db_session, topic.id, 100)
        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.NEEDS_REVISION.value

        # ...and a second push gives (100, 100, 0) = 66.7 → learning.
        _attempt(db_session, topic.id, 100)
        update_mastery(db_session, topic)
        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.LEARNING.value


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------


class TestFlashcards:
    def test_confidence_mapping(self):
        from app.services.flashcard_service import RATING_TO_CONFIDENCE

        assert RATING_TO_CONFIDENCE["again"] == ConfidenceLevel.LOW.value
        assert RATING_TO_CONFIDENCE["easy"] == ConfidenceLevel.HIGH.value
        assert RATING_TO_CONFIDENCE["hard"] == ConfidenceLevel.MEDIUM.value
        assert RATING_TO_CONFIDENCE["good"] == ConfidenceLevel.MEDIUM.value


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_recommended_prioritises_revision(self, db_session):
        from app.services.dashboard_service import _recommended_topics

        revision = _topic(db_session, "NeedsRevision", "مراجعة")
        learning = _topic(db_session, "Learning", "تعلم")
        mastered = _topic(db_session, "Mastered", "متقن")

        revision.mastery_status = MasteryStatus.NEEDS_REVISION.value
        learning.mastery_status = MasteryStatus.LEARNING.value
        mastered.mastery_status = MasteryStatus.MASTERED.value
        db_session.commit()

        _attempt(db_session, learning.id, 55)   # weak learning topic
        _attempt(db_session, revision.id, 90)   # strong score but still flagged

        recommended = _recommended_topics(db_session)

        ids = [entry["topic_id"] for entry in recommended]
        assert ids[0] == revision.id, "needs_revision always sorts first"
        assert ids == [revision.id, learning.id], "mastered topics are excluded"

        learning_entry = recommended[1]
        assert learning_entry["last_score"] == 55
        assert learning_entry["attempts"] == 1


# ===========================================================================
# API endpoints
# ===========================================================================


class TestQuizEndpoints:
    GENERATE_URL = "/api/v1/quizzes/generate"
    SUBMIT_URL = "/api/v1/quizzes/submit"

    def _api_bank(self, db_session):
        topic = _topic(db_session)
        questions = [
            _question(
                db_session, topic.id,
                text="ما هي العناجمة clustering؟",
                options=["تقسيمة بيانات", "خوارزمية ترتيب", "SQL"],
                correct="تقسيمة بيانات",
                difficulty="easy",
            ),
            _question(
                db_session, topic.id,
                text="هل الـ clustering supervised؟",
                qtype="true_false",
                options=["صح", "خطأ"],
                correct="خطأ",
                difficulty="medium",
                explanation="التجميع يُعد unsupervised learning.",
            ),
            _question(
                db_session, topic.id,
                text="اشرح خطوة الـ assignment في K-Means.",
                qtype="short_answer",
                options=[],
                correct="كل نقطة تُسند لأقرب مركز centroid cluster",
                difficulty="hard",
            ),
        ]
        return topic, questions

    def test_practice_mode_includes_answer_key(self, client, db_session):
        self._api_bank(db_session)

        response = client.post(
            self.GENERATE_URL,
            json={"difficulty": "mixed", "count": 10, "mode": "practice"},
        )

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["mode"] == "practice"
        assert body["answer_key_hidden"] is False
        assert len(body["questions"]) == 3
        assert body["questions"][0]["correct_answer"]
        assert body["questions"][0]["explanation"]

    def test_exam_mode_hides_the_key(self, client, db_session):
        self._api_bank(db_session)

        response = client.post(
            self.GENERATE_URL,
            json={"difficulty": "mixed", "count": 10, "mode": "exam"},
        )

        assert response.status_code == 200
        body = response.json()

        assert body["answer_key_hidden"] is True
        assert "correct_answer" not in body["questions"][0]
        assert "explanation" not in body["questions"][0]
        # The question itself is intact.
        assert all(q["question_text"] for q in body["questions"])

    def test_generate_validation(self, client):
        assert client.post(self.GENERATE_URL, json={"count": 0}).status_code == 422
        assert client.post(
            self.GENERATE_URL, json={"difficulty": "impossible"}
        ).status_code == 422

    def test_submit_endpoint_full_cycle(self, client, db_session):
        topic, questions = self._api_bank(db_session)

        # mcq right, true/false wrong, short answer graded by overlap — answer
        # order: [0] correct, [1] wrong, [2] keyword hit.
        response = client.post(
            self.SUBMIT_URL,
            json={
                "answers": [
                    {"question_id": questions[0].id, "answer": "تقسيمة بيانات"},
                    {"question_id": questions[1].id, "answer": "صح"},
                    {
                        "question_id": questions[2].id,
                        "answer": "كل نقطة تُسند لأقرب مركز centroid",
                    },
                ]
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["correct_count"] == 2
        assert body["total_questions"] == 3
        assert body["score"] == 67
        assert not body["not_found"]

        by_question = {item["question_id"]: item for item in body["questions"]}
        assert by_question[questions[1].id]["is_correct"] is False
        assert by_question[questions[1].id]["expected"] == "خطأ"
        assert by_question[questions[2].id]["is_correct"] is True

        topic_row = body["topics"][0]
        assert topic_row["topic_id"] == topic.id
        assert topic_row["total"] == 3
        assert topic_row["attempt_id"] is not None

        # 4/6? no — 2 correct of 3 → 66.7 → avg 67 → learning.
        assert topic_row["updated_mastery"] == MasteryStatus.LEARNING.value

        db_session.refresh(topic)
        assert topic.mastery_status == MasteryStatus.LEARNING.value

    def test_submit_rejects_empty_answers(self, client):
        assert client.post(self.SUBMIT_URL, json={"answers": []}).status_code == 422


class TestFlashcardEndpoints:
    LIST_URL = "/api/v1/flashcards"

    def test_list_filters(self, client, db_session):
        topic = _topic(db_session)
        other = _topic(db_session, "Classification", "التصنيف")

        _flashcard(db_session, topic.id, front="بطاقة 1", confidence="low")
        _flashcard(db_session, topic.id, front="بطاقة 2", confidence="high")
        _flashcard(db_session, other.id, front="بطاقة 3", confidence="low")

        response = client.get(self.LIST_URL)
        assert response.status_code == 200
        assert response.json()["total"] == 3

        filtered = client.get(self.LIST_URL, params={"topic_id": topic.id}).json()
        assert filtered["total"] == 2

        confident = client.get(self.LIST_URL, params={"confidence": "high"}).json()
        assert confident["total"] == 1
        assert confident["items"][0]["front"] == "بطاقة 2"
        assert confident["items"][0]["topic_title_en"] == "Clustering"

    def test_confidence_endpoint_updates_level(self, client, db_session):
        topic = _topic(db_session)
        card = _flashcard(db_session, topic.id, confidence="low")

        response = client.post(
            f"{self.LIST_URL}/{card.id}/confidence", json={"rating": "easy"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["previous_confidence"] == "low"
        assert body["confidence_level"] == "high"

        again = client.post(
            f"{self.LIST_URL}/{card.id}/confidence", json={"rating": "again"}
        ).json()
        assert again["confidence_level"] == "low"

    def test_confidence_unknown_card_is_404(self, client):
        response = client.post(
            f"{self.LIST_URL}/424242/confidence", json={"rating": "good"}
        )
        assert response.status_code == 404

    def test_confidence_validation(self, client, db_session):
        topic = _topic(db_session)
        card = _flashcard(db_session, topic.id)

        response = client.post(
            f"{self.LIST_URL}/{card.id}/confidence", json={"rating": "sorta"}
        )
        assert response.status_code == 422


class TestDashboardEndpoint:
    URL = "/api/v1/dashboard/summary"

    def test_summary_rollup(self, client, db_session):
        db_session.add(
            SourceFile(
                filename="lecture.pdf",
                file_hash=hashlib.sha256(b"summary-test-file").hexdigest()[:32],
                file_type="pdf",
                file_size=10,
                status=SourceFileStatus.PUBLISHED.value,
            )
        )

        topic = _topic(db_session)
        _question(db_session, topic.id, correct="أ")
        _flashcard(db_session, topic.id)
        _attempt(db_session, topic.id, 60)
        update_mastery(db_session, topic)  # 60 → learning
        db_session.commit()

        response = client.get(self.URL)

        assert response.status_code == 200, response.text
        body = response.json()

        assert body["files"]["total"] == 1
        assert body["files"]["by_status"]["published"] == 1

        assert body["topics"]["total"] == 1
        assert body["topics"]["studied"] == 1
        assert body["topics"]["mastery"]["learning"] == 1

        assert len(body["recent_attempts"]) == 1
        recent = body["recent_attempts"][0]
        assert recent["score"] == 60
        assert recent["topic_title_en"] == "Clustering"
        assert recent["attempt_id"] > 0

        # A learning topic (avg 60) appears in the revision queue.
        assert len(body["recommended"]) == 1
        assert body["recommended"][0]["topic_id"] == topic.id
        assert body["recommended"][0]["mastery_status"] == "learning"
