"""Seed a small demo question bank so the quiz/flashcard/lesson screens are
usable before a real LLM key is configured (publishing real lectures replaces
it).

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

# Demo lessons — Arabic Markdown bodies plus the structured teaching blocks the
# lesson viewer renders (objectives / glossary / formulas / comparisons).
LESSONS = [
    {
        "topic_index": 0,
        "content_ar": (
            "# التجميع العنقودي (Clustering)\n"
            "\n"
            "## الفكرة الأساسية\n"
            "**Clustering** هو تقسيم البيانات لمجموعات (عناقيد) بحيث تكون النقاط جوه\n"
            "العنقود متشابهة، والنقاط اللي في عناقيد مختلفة غير متشابهة. ده تعلّم\n"
            "**غير مُوجَّه (Unsupervised)** لأننا مش بنستخدم تصنيفات مسبقة.\n"
            "\n"
            "## خوارزمية K-Means خطوة بخطوة\n"
            "1. اختر عدد العناقيد `K` بشكل مبدئي.\n"
            "2. اختر `K` نقطة كمراكز مبدئية (centroids).\n"
            "3. عيّن كل نقطة لأقرب مركز باستخدام المسافة الإقليدية.\n"
            "4. أعد حساب كل مركز = متوسط النقاط اللي اتخصّصت له.\n"
            "5. كرّر الخطوتين 3 و4 لحد ما المراكز تستقر.\n"
            "\n"
            "```text\n"
            "while centroids change:\n"
            "    assign each point to nearest centroid\n"
            "    recompute centroids as the mean of their points\n"
            "```\n"
            "\n"
            "## مثال محلول\n"
            "لو عندنا 5 عملاء بأعمار: 20، 22، 25، 60، 62 ونختار `K = 2`:\n"
            "- العنقود الأول: 20، 22، 25 → المركز = 22.3\n"
            "- العنقود الثاني: 60، 62 → المركز = 61\n"
            "\n"
            "> تنبيه: نتيجة K-Means بتعتمد على المراكز المبدئية، فالأفضل تشغّلها كذا\n"
            "> مرة وتختار أفضل تقسيم.\n"
            "\n"
            "## إزاي تختار عدد العناقيد؟\n"
            "\n"
            "| الطريقة | بتقيس إيه؟ | بتستخدم إمتى؟ |\n"
            "| --- | --- | --- |\n"
            "| Elbow Method | مجموع مربعات المسافات | تقدير أولي لـ K |\n"
            "| Silhouette Score | تماسك العنقود | مقارنة حلول مختلفة |\n"
            "\n"
            "## الأخطاء الشائعة\n"
            "- اختيار `K` بالرأي الشخصي من غير قياس.\n"
            "- التشغيل على بيانات مش مُطبَّعة، فالمقياس الأكبر يسيطر على المسافة.\n"
        ),
        "objectives": [
            "تفرّق بين التعلّم غير المُوجَّه والتعلّم المُوجَّه",
            "تنفّذ K-Means خطوة بخطوة على مثال صغير",
            "تختار عدد العناقيد بمنهج (Elbow / Silhouette)",
        ],
        "prerequisites": ["أساسيات الجبر والمتوسط الحسابي", "مفهوم المسافة الإقليدية"],
        "english_terminology": [
            {"term": "Clustering", "arabic": "التجميع العنقودي", "definition": "تقسيم البيانات لمجموعات متشابهة داخليًا."},
            {"term": "Centroid", "arabic": "المركز", "definition": "متوسط النقاط المنتمية للعنقود."},
            {"term": "Unsupervised Learning", "arabic": "تعلّم غير مُوجَّه", "definition": "تعلّم بدون تصنيفات جاهزة."},
        ],
        "formulas": [
            {"name": "تحديث المركز (Centroid update)", "latex": "c_k = (1 / |S_k|) * sum(x_i for x_i in S_k)", "note": "متوسط نقاط العنقود بعد كل تخصيص."},
            {"name": "المسافة الإقليدية", "latex": "d(x, c) = sqrt(sum((x_j - c_j)^2))", "note": "معيار القرب الافتراضي في K-Means."},
        ],
        "comparisons": [
            {"topic_a": "K-Means", "topic_b": "DBSCAN", "aspect": "عدد العناقيد", "detail": "K-Means لازم تحدّد K مسبقًا، أما DBSCAN بتحدد العناقيد حسب الكثافة."},
            {"topic_a": "K-Means", "topic_b": "DBSCAN", "aspect": "الشكل والضوضاء", "detail": "K-Means بتفترض عناقيد كروية وما بتتعاملش مع noise، وDBSCAN بتكشف الضوضاء."},
        ],
        "summary": "التجميع العنقودي بيقسّم بيانات بدون تصنيفات لمجموعات متشابهة. K-Means بتشتغل "
        "بتكرار خطوتين: تخصيص النقاط لأقرب مركز، ثم إعادة حساب المراكز كمتوسط. اختيار K "
        "قرار مهم بيتّخذ بقياس (Elbow أو Silhouette) مش بالرأي، وتطبيع البيانات شرط عملي.",
    },
    {
        "topic_index": 1,
        "content_ar": (
            "# التصنيف (Classification)\n"
            "\n"
            "## الفكرة الأساسية\n"
            "**Classification** تعلّم **مُوجَّه (Supervised)**: عندنا بيانات فيها الفئة\n"
            "الصحيحة (label)، والنموذج بيتعلّم يفصل بين الفئات، وبعدين يتوقّع فئة\n"
            "عناصر جديدة.\n"
            "\n"
            "## أنواع المصنّفات\n"
            "- **Decision Tree**: تقسيمات متتالية على السمات، سهلة الفهم والتفسير.\n"
            "- **Naive Bayes**: احتمال مبني على قاعدة Bayes مع افتراض استقلال السمات.\n"
            "- **K-Nearest Neighbors**: الفئة بتيجي من تصويت أقرب `K` جار.\n"
            "\n"
            "## مصطلحات لازم تعرفها\n"
            "- **True Positive (TP)**: توقّعنا موجب وهو فعلًا موجب.\n"
            "- **False Positive (FP)**: توقّعنا موجب وهو في الحقيقة سالب.\n"
            "- **False Negative (FN)**: توقّعنا سالب وهو في الحقيقة موجب.\n"
            "\n"
            "## مثال محلول\n"
            "مصفوفة تبويب (Confusion Matrix) لموديل سبام: `TP = 40`، `FP = 10`، `FN = 5`.\n"
            "\n"
            "1. `Precision = 40 / (40 + 10) = 0.8`\n"
            "2. `Recall = 40 / (40 + 5) = 0.89`\n"
            "\n"
            "يعني لما الموديل يقول «spam» بيكون صح في 80% من المرات، وبيعرف يمسك 89%\n"
            "من رسائل السبام الفعلية.\n"
            "\n"
            "> في البيانات غير المتوازنة (imbalanced)، **Precision** و**Recall** أهم\n"
            "> بكتير من **Accuracy** وحدها.\n"
            "\n"
            "## الأخطاء الشائعة\n"
            "- الاعتماد على Accuracy وحدها مع بيانات غير متوازنة.\n"
            "- **Overfitting**: الموديل يحفظ بيانات التدريب ويفشل في التعميم.\n"
        ),
        "objectives": [
            "تفرّق بين Classification و Clustering",
            "تحسب Precision و Recall و F1 من مصفوفة التبويب",
            "تفسّر Overfitting وإزاي تتجنّبه",
        ],
        "prerequisites": ["مفهوم بيانات التدريب والاختبار", "أساسيات الاحتمالات"],
        "english_terminology": [
            {"term": "Classification", "arabic": "التصنيف", "definition": "توقّع فئة محددة من فئات معروفة."},
            {"term": "Confusion Matrix", "arabic": "مصفوفة التبويب", "definition": "جدول بيقارن التوقّع بالحقيقة لكل فئة."},
            {"term": "Overfitting", "arabic": "فرط التخصيص", "definition": "الموديل يحفظ التدريب ويفشل في التعميم."},
        ],
        "formulas": [
            {"name": "Precision", "latex": "TP / (TP + FP)", "note": "دقة التنبؤات الموجبة."},
            {"name": "Recall", "latex": "TP / (TP + FN)", "note": "نسبة الحالات الموجبة اللي اتمسكت."},
            {"name": "F1 Score", "latex": "2 * (P * R) / (P + R)", "note": "توازن بين Precision و Recall."},
        ],
        "comparisons": [
            {"topic_a": "Decision Tree", "topic_b": "KNN", "aspect": "التفسير", "detail": "شجرة القرار قواعدها واضحة وقابلة للتفسير، أما KNN قرارها بيعتمد على الجيران."},
            {"topic_a": "Precision", "topic_b": "Recall", "aspect": "المعنى", "detail": "Precision بتقيس جودة التنبؤ الموجب، وRecall بتقيس التغطية."},
        ],
        "summary": "التصنيف بيتعلّم من بيانات فيها الفئة الصحيحة ويتوقّع فئات عناصر جديدة. "
        "التقييم لازم يمشي أبعد من Accuracy: مصفوفة التبويب بتدّينا Precision و Recall وF1. "
        "وOverfitting أخطر مشكلة، وعلاجها بيانات أكتر وتبسيط الموديل والتحقق المتقاطع.",
    },
    {
        "topic_index": 2,
        "content_ar": (
            "# قواعد الارتباط (Association Rules)\n"
            "\n"
            "## الفكرة الأساسية\n"
            "قواعد الارتباط بتدوّر على علاقات من نوع «لو حصل A، فغالبًا يحصل B» جوه\n"
            "بيانات المعاملات (زي سلة المشتريات). الهدف توصية أذكى أو تحليل سلوك.\n"
            "\n"
            "## المقاييس الثلاثة\n"
            "- **Support**: نسبة المعاملات اللي فيها العناصر مع بعض.\n"
            "- **Confidence**: احتمال وجود B بشرط وجود A.\n"
            "- **Lift**: هل العلاقة أقوى من الصدفة؟\n"
            "\n"
            "## مثال محلول\n"
            "في 100 معاملة: `{bread}` في 30، و`{butter}` في 40، والاتنين مع بعض في 24.\n"
            "\n"
            "1. `Support(bread -> butter) = 24 / 100 = 0.24`\n"
            "2. `Confidence = 24 / 30 = 0.8`\n"
            "3. `Lift = 0.8 / 0.4 = 2`\n"
            "\n"
            "الـ **Lift** أكبر من 1، يعني العلاقة حقيقية ومش من الصدفة.\n"
            "\n"
            "## خوارزمية Apriori\n"
            "```text\n"
            "L1 = frequent 1-itemsets\n"
            "k = 2\n"
            "while L(k-1) not empty:\n"
            "    C_k = candidates from L(k-1)      # join\n"
            "    prune C_k using anti-monotonicity # support(A u B) <= support(A)\n"
            "    L_k = {c in C_k : support(c) >= min_support}\n"
            "    k = k + 1\n"
            "```\n"
            "\n"
            "> مبدأ عدم الرتابة (Anti-monotonicity): لو مجموعة عناصر غير متكررة، فكل\n"
            "> مجموعاتها الفائقة أكيد غير متكررة — وده اللي بيخلّي التقليم فعّال.\n"
            "\n"
            "## الأخطاء الشائعة\n"
            "- تقليل `min_support` بشكل مبالغ فيه فيتولّد عدد ضخم من القواعد.\n"
            "- الاعتماد على **Confidence** وحدها من غير **Lift**.\n"
        ),
        "objectives": [
            "تحسب Support و Confidence و Lift من بيانات معاملات",
            "تفسّر معنى Lift أكبر من 1 وأقل من 1",
            "تشرح دور مبدأ عدم الرتابة في تقليم Apriori",
        ],
        "prerequisites": ["أساسيات الاحتمال الشرطي"],
        "english_terminology": [
            {"term": "Support", "arabic": "الدعم", "definition": "نسبة المعاملات اللي بتضم مجموعة العناصر."},
            {"term": "Confidence", "arabic": "الثقة", "definition": "احتمال وجود العنصر التالي بشرط وجود الأول."},
            {"term": "Lift", "arabic": "الرفع", "definition": "نسبة الثقة الفعلية للثقة المتوقعة لو كانوا مستقلين."},
        ],
        "formulas": [
            {"name": "Support", "latex": "support(A -> B) = count(A u B) / N", "note": "تغطية القاعدة في البيانات."},
            {"name": "Confidence", "latex": "confidence(A -> B) = support(A u B) / support(A)", "note": "قوة القاعدة."},
            {"name": "Lift", "latex": "lift(A -> B) = confidence(A -> B) / support(B)", "note": "أكبر من 1 يعني ارتباط حقيقي."},
        ],
        "comparisons": [
            {"topic_a": "Support", "topic_b": "Confidence", "aspect": "بيقيس إيه", "detail": "Support بتقيس التكرار، أما Confidence فبتقيس قوة العلاقة."},
            {"topic_a": "Confidence", "topic_b": "Lift", "aspect": "الكفاية", "detail": "Confidence لوحدها ممكن تضلّل، وLift بتصحّح بمقارنة العلاقة بالصدفة."},
        ],
        "summary": "قواعد الارتباط بتكشف اقترانات متكررة في بيانات المعاملات، وتتقيّم بثلاث "
        "مقاييس: Support للتكرار، Confidence لقوة القاعدة، وLift للتأكد إن العلاقة مش "
        "صدفة. وخوارزمية Apriori بتقلم مساحة البحث بمبدأ عدم الرتابة.",
    },
    {
        "topic_index": 3,
        "content_ar": (
            "# تجهيز البيانات (Data Preprocessing)\n"
            "\n"
            "## ليه بنجهّز البيانات؟\n"
            "البيانات الخام بتيجي ناقصة أو مكررة أو بمقاييس مختلفة، وده يخلّي نتايج أي\n"
            "خوارزمية تعدين غير موثوقة. التجهيز بياخد غالبًا **70% من وقت المشروع**.\n"
            "\n"
            "## خطوات التجهيز\n"
            "1. **تنظيف (Cleaning)**: شيل التكرارات وعالج القيم الشاذة (outliers).\n"
            "2. **القيم المفقودة**: احذف الصف، أو عوّض بالمقياس المركزي، أو تنبّأ بالقيمة.\n"
            "3. **التحويل (Transformation)**: تطبيع النطاق (Normalization) أو توحيده (Standardization).\n"
            "4. **تقليل الأبعاد (Reduction)**: اختيار سمات مهمة أو PCA.\n"
            "\n"
            "## معادلات التحويل\n"
            "\n"
            "| الطريقة | المعادلة | الناتج |\n"
            "| --- | --- | --- |\n"
            "| Min-Max Normalization | `(x - min) / (max - min)` | نطاق [0, 1] |\n"
            "| Z-Score Standardization | `(x - mean) / std` | متوسط 0 وانحراف 1 |\n"
            "\n"
            "## مثال محلول\n"
            "مقياسين: العمر من 20 لـ 60، والدخل من 5,000 لـ 50,000. من غير تطبيع، الدخل\n"
            "هيسيطر على حساب المسافة؛ وبعد Min-Max الاتنين يبقوا في نفس النطاق.\n"
            "\n"
            "> تنبيه: احسب `min` و`max` من بيانات التدريب بس، وطبّق نفس القيم على\n"
            "> بيانات الاختبار عشان ما يحصلش **Data Leakage**.\n"
            "\n"
            "## الأخطاء الشائعة\n"
            "- تطبيع البيانات قبل تقسيمها تدريب/اختبار (تسريب).\n"
            "- حذف القيم المفقودة من غير ما تشوف نسبتها وتأثيرها على التوزيع.\n"
        ),
        "objectives": [
            "تعدّد خطوات تجهيز البيانات وترتيبها المنطقي",
            "تفرّق بين Normalization و Standardization",
            "تشرح Data Leakage وإزاي تتجنّبه",
        ],
        "prerequisites": ["أساسيات الإحصاء الوصفي", "مفهوم المتوسط والانحراف المعياري"],
        "english_terminology": [
            {"term": "Data Cleaning", "arabic": "تنظيف البيانات", "definition": "إصلاح القيم الغلط أو المكررة أو الشاذة."},
            {"term": "Normalization", "arabic": "التطبيع", "definition": "تحويل القيم لنطاق صغير موحّد زي [0, 1]."},
            {"term": "Data Leakage", "arabic": "تسريب البيانات", "definition": "دخول معلومة من بيانات الاختبار في التدريب."},
        ],
        "formulas": [
            {"name": "Min-Max Normalization", "latex": "(x - min) / (max - min)", "note": "لما القيم معروفة المدى."},
            {"name": "Z-Score Standardization", "latex": "(x - mean) / std", "note": "لما فيه قيم شاذة أو توزيع غير معروف."},
        ],
        "comparisons": [
            {"topic_a": "Normalization", "topic_b": "Standardization", "aspect": "الناتج", "detail": "التطبيع بيحصر القيم في [0,1]، أما التوحيد فمتوسطه 0 وانحرافه 1."},
            {"topic_a": "حذف الصفوف", "topic_b": "التعويض", "aspect": "التأثير", "detail": "الحذف بسيط بس بيقلّل البيانات، والتعويض بيحافظ عليها وبيحتاج حكمًا سليمًا."},
        ],
        "summary": "تجهيز البيانات هو أطول مرحلة عملية: تنظيف، ومعالجة قيم مفقودة، وتحويل "
        "المقاييس، وتقليل الأبعاد. التطبيع أو التوحيد بيخلّي المقاييس متكافئة، وأخطر "
        "خطأ هو تسريب معلومة من الاختبار للتدريب.",
    },
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

    for entry in LESSONS:
        db.add(
            Lesson(
                topic_id=topics[entry["topic_index"]].id,
                content_ar=entry["content_ar"],
                objectives=entry["objectives"],
                prerequisites=entry["prerequisites"],
                english_terminology=entry["english_terminology"],
                formulas=entry["formulas"],
                comparisons=entry["comparisons"],
                summary=entry["summary"],
                language="ar",
            )
        )

    db.commit()
    return len(topics), len(QUESTIONS), len(FLASHCARDS), len(LESSONS)


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

        topics, questions, flashcards, lessons = seed(db)
        print(
            f"Seeded {topics} topics, {questions} questions, "
            f"{flashcards} flashcards, {lessons} lessons."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
