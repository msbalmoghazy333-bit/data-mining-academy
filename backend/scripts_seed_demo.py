"""Seed a small demo question bank so the quiz/flashcard screens are usable
before a real LLM key is configured (publishing real lectures replaces it).

Run from `backend/`:

    python scripts_seed_demo.py            # seed if the DB has no topics yet
    python scripts_seed_demo.py --reset    # replace the demo topics in place

Questions are written in **English** (the exam language); only the explanations
stay Egyptian Arabic, mirroring what the generator produces since the prompt
was changed to author English questions.

Idempotent: the default run does nothing once any topic exists, so it can never
clobber real material. ``--reset`` only removes the demo topics below (by
English title) and re-creates them.
"""

from __future__ import annotations

import argparse

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Flashcard, Lesson, Question, QuizAttempt, Topic
from app.models.enums import Difficulty, QuestionType

Base.metadata.create_all(bind=engine)

TOPICS = [
    ("Clustering", "التجميع العنقودي"),
    ("Classification", "التصنيف"),
    ("Association Rules", "قواعد الارتباط"),
    ("Data Preprocessing", "تجهيز البيانات"),
]

# (topic_index, type, difficulty, question (en), options (en), correct (en),
#  explanation (ar), source)
QUESTIONS = [
    (0, QuestionType.MCQ.value, Difficulty.EASY.value,
     "Which clustering algorithm needs the number of clusters K to be chosen in advance?",
     ["K-Means", "DBSCAN", "Hierarchical Clustering"], "K-Means",
     "خوارزمية K-Means لازم تحدد K قبل التشغيل، أما DBSCAN بتحدد العناقيد حسب الكثافة.",
     "section1 DM.pptx — slide 14"),
    (0, QuestionType.MCQ.value, Difficulty.MEDIUM.value,
     "What is the default similarity measure used by K-Means?",
     ["Euclidean distance", "Jaccard coefficient", "Pearson correlation"], "Euclidean distance",
     "K-Means بتستخدم المسافة الإقليدية لقياس قرب النقطة من المركز centroid.",
     "section1 DM.pptx — slide 16"),
    (0, QuestionType.TRUE_FALSE.value, Difficulty.EASY.value,
     "Clustering is an unsupervised learning task.",
     ["True", "False"], "True",
     "التجميع مش محتاج تصنيفات مسبقة، فده unsupervised learning.",
     "section1 DM.pptx — slide 12"),
    (0, QuestionType.SHORT_ANSWER.value, Difficulty.HARD.value,
     "Explain the idea behind the DBSCAN algorithm in two lines.",
     [], "density eps neighbors core border noise",
     "DBSCAN بتجمّع النقاط حسب الكثافة: كل نقطة core ليها جيران جوه نصف قطر eps، والضوضاء noise بتفضل برة.",
     "section 2 DM.pptx — slide 22"),
    (1, QuestionType.MCQ.value, Difficulty.EASY.value,
     "Which of the following is a classification problem?",
     ["Predicting a house price", "Classifying an email as spam or not", "Grouping customers into segments"],
     "Classifying an email as spam or not",
     "تصنيف البريد بيرجّع فئة محددة (spam/not spam).",
     "sec3 data mining.pptx — slide 5"),
    (1, QuestionType.TRUE_FALSE.value, Difficulty.MEDIUM.value,
     "A Decision Tree can only model linear problems.",
     ["True", "False"], "False",
     "شجرة القرار تقدر تمثّل علاقات غير خطية عن طريق التقسيم المتكرر.",
     "sec3 data mining.pptx — slide 9"),
    (1, QuestionType.MCQ.value, Difficulty.MEDIUM.value,
     "In a Confusion Matrix, what does a False Positive mean?",
     ["The model predicted positive but the truth is negative", "The model predicted negative and the truth is negative", "The model predicted negative but the truth is positive"],
     "The model predicted positive but the truth is negative",
     "False Positive يعني تنبؤ إيجابي خاطئ: النموذج قال موجب وهو في الحقيقة سالب.",
     "sec4 data mining.pptx — slide 11"),
    (1, QuestionType.SHORT_ANSWER.value, Difficulty.MEDIUM.value,
     "What does Overfitting mean in a classification model?",
     [], "memorizes training data and fails to generalize",
     "Overfitting لما النموذج يحفظ التدريب ويفشل في التعميم على بيانات جديدة.",
     "sec4 data mining.pptx — slide 15"),
    (2, QuestionType.MCQ.value, Difficulty.MEDIUM.value,
     "In association rules, what does support measure?",
     ["The share of transactions that contain the items together", "The strength of the relation between items", "The total number of rules"],
     "The share of transactions that contain the items together",
     "Support = نسبة المعاملات اللي بتحتوي مجموعة العناصر دي.",
     "section 2 DM.pptx — slide 6"),
    (2, QuestionType.TRUE_FALSE.value, Difficulty.HARD.value,
     "The Apriori algorithm uses the anti-monotonicity property to prune the search space.",
     ["True", "False"], "True",
     "لو عنصر مجموعة مش متكرر، كل مجموعاته الفائقة مش هتكون متكررة — فبيتم التقليم pruning.",
     "section 2 DM.pptx — slide 8"),
    (2, QuestionType.MCQ.value, Difficulty.EASY.value,
     "What does the rule {bread} -> {butter} mean?",
     ["Whoever buys bread often also buys butter", "Bread and butter are unrelated", "Butter is only sold on its own"],
     "Whoever buys bread often also buys butter",
     "القاعدة بتعبّر عن اقتران: وجود خبز بيرفع احتمال وجود زبدة.",
     "section 2 DM.pptx — slide 4"),
    (3, QuestionType.MCQ.value, Difficulty.EASY.value,
     "Why do we handle missing values before modelling?",
     ["They distort the model", "They speed up training", "They have no effect"],
     "They distort the model",
     "القيم المفقودة بتخلّي حسابات المسافة والإحصاءات غلط، فلازم تُعالَج (حذف أو تعويض).",
     "01Intro.pdf — page 7"),
    (3, QuestionType.TRUE_FALSE.value, Difficulty.EASY.value,
     "Normalization maps the data into a small, unified range.",
     ["True", "False"], "True",
     "Normalization بيحوّل القيم لنطاق زي [0,1] عشان المقاييس تبقى متقاربة.",
     "01Intro.pdf — page 9"),
    (3, QuestionType.SHORT_ANSWER.value, Difficulty.EASY.value,
     "Mention one way to handle missing values.",
     [], "impute with the mean or median, or drop the rows",
     "من أشهر الطرق: التعويض بالمقياس المركزي (المتوسط/الوسيط) أو حذف الصفوف.",
     "01Intro.pdf — page 8"),
]

FLASHCARDS = [
    (0, "يعني إيه centroid؟", "مركز العنقود = متوسط النقاط اللي فيه."),
    (1, "يعني إيه Precision؟", "نسبة التنبؤات الموجبة اللي كانت صح فعلًا."),
    (2, "يعني إيه Confidence في قواعد الارتباط؟", "احتمال وجود العنصر التالي بشرط وجود الأول."),
]


def _demo_topic_ids(db) -> list[int]:
    titles = [title_en for title_en, _ in TOPICS]
    return [topic.id for topic in db.query(Topic).filter(Topic.title_en.in_(titles)).all()]


def reset_demo(db) -> int:
    """Delete the demo topics (and their children) so they can be re-seeded."""

    ids = _demo_topic_ids(db)
    if not ids:
        return 0

    db.query(Question).filter(Question.topic_id.in_(ids)).delete(synchronize_session=False)
    db.query(Flashcard).filter(Flashcard.topic_id.in_(ids)).delete(synchronize_session=False)
    db.query(Lesson).filter(Lesson.topic_id.in_(ids)).delete(synchronize_session=False)
    db.query(QuizAttempt).filter(QuizAttempt.topic_id.in_(ids)).delete(synchronize_session=False)
    db.query(Topic).filter(Topic.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return len(ids)


def seed(db) -> tuple[int, int, int]:
    topics = []
    for title_en, title_ar in TOPICS:
        topic = Topic(title_en=title_en, title_ar=title_ar)
        db.add(topic)
        topics.append(topic)
    db.commit()

    for topic_index, qtype, difficulty, text, options, correct, explanation, source in QUESTIONS:
        db.add(
            Question(
                topic_id=topics[topic_index].id,
                type=qtype,
                question_text=text,
                options_json=options,
                correct_answer=correct,
                explanation=explanation,
                difficulty=difficulty,
                source_reference=source,
            )
        )

    for topic_index, front, back in FLASHCARDS:
        db.add(
            Flashcard(
                topic_id=topics[topic_index].id,
                front=front,
                back=back,
                confidence_level="low",
            )
        )

    db.commit()
    return len(topics), len(QUESTIONS), len(FLASHCARDS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete the demo topics first, then re-seed them in place",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            removed = reset_demo(db)
            print(f"Removed {removed} demo topic(s).")
        elif db.query(Topic).count():
            print("Database already has topics — nothing to do. (use --reset to replace)")
            return

        topics, questions, flashcards = seed(db)
        print(f"Seeded {topics} topics, {questions} questions, {flashcards} flashcards.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
