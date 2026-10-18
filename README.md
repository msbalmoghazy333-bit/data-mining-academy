# أكاديمية تعدين البيانات — Data Mining Academy

منصة تعليمية تفاعلية لتعلم **تعدين البيانات (Data Mining)** بالعربية، مع دعم كامل
للمصطلحات الإنجليزية. مبنية كـ full-stack application بـ FastAPI + React.

> الحالة الحالية: **جاهز للتوليد والاستفسار** — قاعدة البيانات، خط استخراج
> الملفات، توليد المحتوى التعليمي (دروس/أسئلة/بطاقات) عبر OpenRouter،
> **ومعلم ذكي (RAG)** يجيب من المحتوى المنشور فقط مع استشهادات متحقَّق
> منها — كلها تعمل، مع مسودة ونشر (draft & publish) لا يحذف أي محتوى
> سابق أبدًا.
>
> **ومحرّك تقييم** كامل (كويزات حتمية + إتقان + بطاقات + لوحة متعلم) فوق
> **واجهة عربية RTL** فيها لوحة التحكم ومكتبة المنهج والمعلم الذكي ومُحاكي
> الامتحان مع زر «عرض بالعربي» لكل سؤال (ترجمة عند الطلب).

**المستودع العام:** <https://github.com/msbalmoghazy333-bit/data-mining-academy>

```powershell
git clone https://github.com/msbalmoghazy333-bit/data-mining-academy.git
cd data-mining-academy
```

---

## Tech Stack

| الطبقة | التقنية |
| --- | --- |
| Backend | Python **FastAPI** + **Uvicorn** |
| ORM / DB | **SQLAlchemy 2.0** + **SQLite** |
| Migrations | **Alembic** |
| Vector Store | **ChromaDB** (local persistence) |
| Settings | **pydantic-settings** (من `.env`) |
| Frontend | **React 19** + **Vite 8** |
| Styling | **Tailwind CSS v4** |
| Icons | **Lucide React** |
| Routing | **React Router v7** |
| Direction | **RTL** (`<html dir="rtl" lang="ar">`) |
| لغة الأسئلة | **إنجليزي** دائمًا (لغة الامتحان) — والشرح عربي، مع زر «عرض بالعربي» لكل سؤال |

---

## هيكل المشروع

```
Data Mining Academy/
├── backend/
│   ├── alembic.ini                  # إعدادات Alembic
│   ├── alembic/
│   │   ├── env.py                   # يقرأ DATABASE_URL من Settings
│   │   └── versions/                # ملفات الـ migrations
│   ├── app/
│   │   ├── main.py                  # تطبيق FastAPI + CORS + lifespan + handlers
│   │   ├── core/
│   │   │   └── config.py            # Settings (pydantic-settings)
│   │   ├── db/
│   │   │   ├── base.py              # Base + TimestampMixin + naming convention
│   │   │   └── session.py           # engine + SessionLocal + get_db + FK pragma
│   │   ├── models/                  # 7 جداول SQLAlchemy
│   │   │   ├── enums.py
│   │   │   ├── source_file.py       # SourceFile
│   │   │   ├── document_chunk.py    # DocumentChunk
│   │   │   ├── topic.py             # Topic
│   │   │   ├── lesson.py            # Lesson
│   │   │   ├── question.py          # Question
│   │   │   ├── flashcard.py         # Flashcard
│   │   │   └── quiz_attempt.py      # QuizAttempt
│   │   ├── schemas/                 # Pydantic schemas
│   │   │   ├── source_file.py
│   │   │   ├── document_chunk.py
│   │   │   └── generated.py         # عقد JSON المتوقع من الـ LLM + ردود الـ API
│   │   ├── api/v1/
│   │   │   ├── router.py            # يجمّع كل الـ endpoints
│   │   │   └── endpoints/
│   │   │       ├── health.py        # GET /api/health
│   │   │       ├── files.py         # /api/v1/files/*
│   │   │       ├── generation.py    # /api/v1/files/{id}/generate|publish|draft
│   │   │       ├── tutor.py         # POST /api/v1/tutor/chat
│   │   │       ├── topics.py        # GET /api/v1/topics (كتالوج المواضيع)
│   │   │       ├── lessons.py       # /api/v1/lessons (عارض الدروس)
│   │   │       ├── translation.py   # POST /api/v1/translate (ترجمة عند الطلب)
│   │   │       ├── quizzes.py       # /api/v1/quizzes/generate|submit
│   │   │       ├── flashcards.py    # /api/v1/flashcards + /{id}/confidence
│   │   │       └── dashboard.py     # GET /api/v1/dashboard/summary
│   │   └── services/
│   │       ├── storage.py           # حفظ آمن + SHA-256 + تنظيف الأسماء
│   │       ├── extractor.py         # PDF/DOCX/PPTX/TXT → صفحات مرقّمة
│   │       ├── chunker.py           # صفحات → مقاطع 500-800 كلمة
│   │       ├── pipeline.py          # إدارة الحالة + الحفظ
│   │       ├── file_service.py      # استعلامات ودورة حياة الملفات
│   │       ├── llm_service.py       # عميل OpenRouter (متوافق مع OpenAI)
│   │       ├── content_generator.py # استخراج المواضيع → توليد الدرس → النشر
│   │       ├── vector_store.py      # ChromaDB + خلفيات embeddings قابلة للتبديل
│   │       ├── tutor_service.py     # المعلم الذكي (RAG) + تحقق الاستشهادات
│   │       ├── topic_service.py     # كتالوج المواضيع + أحجام بنك الأسئلة
│   │       ├── lesson_service.py    # الدروس المنشورة (قائمة مختصرة + درس كامل)
│   │       ├── translation_service.py # ترجمة عند الطلب (إنجليزي ↔ عربي) + كاش LRU
│   │       ├── assessment.py        # توليد الكويز + التصحيح المحمَّد + الإتقان
│   │       ├── flashcard_service.py # البطاقات + تقييم المراجعة
│   │       └── dashboard_service.py # لوحة المتعلم
│   ├── tests/
│   │   ├── conftest.py              # قاعدة بيانات ومجلد رفع مؤقتين
│   │   ├── helpers.py               # مولّدات PDF/DOCX/PPTX/TXT للاختبار
│   │   ├── test_extraction.py       # 61 اختبار (الرفع والاستخراج والتقسيم)
│   │   ├── test_generation.py       # 39 اختبار (التوليد والنشر عبر LLM وهمي)
│   │   ├── test_tutor.py            # 16 اختبار (RAG والاستشهادات المتحقَّق منها)
│   │   ├── test_assessment.py       # 26 اختبار (الكويز والتصحيح والإتقان والبطاقات)
│   │   ├── test_topics.py           # 4 اختبارات (كتالوج المواضيع وأحجام البنك)
│   │   └── test_translation.py      # 12 اختبار (الترجمة عند الطلب + الكاش)
│   ├── scripts_check_real_files.py  # فحص يدوي لملفات الكورس الحقيقية
│   ├── scripts_seed_demo.py         # تهيئة بيانات تجريبية لتجربة الشاشات بلا مفتاح LLM
│   ├── data/                        # SQLite + ChromaDB + uploads (git-ignored)
│   ├── requirements.txt
│   ├── .env.example
│   └── .env
└── frontend/
    ├── index.html                   # lang="ar" dir="rtl" + خط Cairo
    ├── vite.config.js               # Tailwind plugin + /api proxy
    └── src/
        ├── main.jsx                 # Router + LanguageProvider + root render
        ├── App.jsx                  # المسارات (Layout + كل الصفحات + 404)
        ├── index.css                # Tailwind + ثيم teal + قواعد RTL/LTR
        ├── components/
        │   ├── ui.jsx               # Button / Card / Badge / Modal / Banner…
        │   └── AppLayout.jsx        # header + شريط جانبي قابل للطي + drawer + bottom-nav
        ├── lib/
        │   ├── api.js               # عميل الـ API
        │   ├── i18n.jsx             # عربي (RTL افتراضي) ↔ إنجليزي (LTR) + localStorage
        │   ├── format.js            # bytes / dates / نسب / interpolations
        │   └── summaryStore.js      # كاش مشترك لإحصاءات الداشبورد (pill + الصفحة)
        └── pages/
            ├── Dashboard.jsx        # متريكات + إجراءات سريعة + توزيع الإتقان + طابور مراجعة
            ├── Library.jsx          # dropzone + جدول الملفات + مودال المراجعة والنشر
            ├── Tutor.jsx            # شاشة محادثة المعلم الذكي (RAG) + شرائح الاستشهاد
            ├── Quiz.jsx             # بنك الأسئلة ومُحاكي الامتحان (تدريب/امتحان) + زر «عرض بالعربي» لكل سؤال
            ├── Revision.jsx         # مركز المراجعة: طابور أضعف المواضيع + جلسة بطاقات بالتقييم الرباعي
            ├── Lessons.jsx          # عارض الدروس: قائمة مواضيع + شرح Markdown + معادلات + مسرد + خلاصة
            └── ComingSoon.jsx       # شاشة مؤقتة للمرحلة الجاية (flashcards)
```

---

## API Reference

| Method | Path | الوصف |
| --- | --- | --- |
| GET | `/api/health` | فحص حياة الخادم وقاعدة البيانات |
| POST | `/api/v1/files/upload` | رفع ملف + استخراج + تقسيم |
| GET | `/api/v1/files` | قائمة الملفات مع الحالات (`?status=&limit=&offset=`) |
| GET | `/api/v1/files/{id}/preview` | معاينة النص المستخرَج والصفحات قبل النشر |
| POST | `/api/v1/files/{id}/retry` | إعادة تشغيل الاستخراج (خاصة للفشل) |
| DELETE | `/api/v1/files/{id}` | حذف الملف ومقاطعه من القرص وقاعدة البيانات |
| POST | `/api/v1/files/{id}/generate` | استخراج مواضيع الملف وتوليد دروس/أسئلة/بطاقات → **مسودة** |
| POST | `/api/v1/files/{id}/publish` | اعتماد المسودة وإضافتها للمنهج — **إضافي بالكامل** + فهرسة RAG |
| GET | `/api/v1/files/{id}/draft` | استعراض المسودة المخزّنة قبل الاعتماد |
| GET | `/api/v1/topics` | كتالوج المواضيع (`?limit=&offset=`) مع عدد أسئلة/بطاقات كل موضوع وحالة الإتقان — مصدر فلتر الكويز |
| GET | `/api/v1/lessons` | كتالوج الدروس (`?topic_id=&limit=&offset=`) — ملخّصات بدون نص الدرس (أهداف/عدادات) للعارض |
| GET | `/api/v1/lessons/{id}` | الدرس كامل: نص Markdown + الأهداف + المسرد + المعادلات + المقارنات + الخلاصة |
| POST | `/api/v1/translate` | ترجمة عند الطلب (`texts` + `target=ar|en`) لزر «عرض بالعربي» — كاش داخل العملية + 409 بدون مفتاح |
| POST | `/api/v1/tutor/chat` | المعلم الذكي: سؤال ← إجابة مُسندة على المحتوى المنشور + استشهادات |
| POST | `/api/v1/quizzes/generate` | توليد كويز من بنك الأسئلة (`topic_ids`/`difficulty`/`count`/`mode`) — وضع `exam` يخفي مفتاح الإجابات |
| POST | `/api/v1/quizzes/submit` | تصحيح آلي محدَّد + تسجيل المحاولات + تحديث حالة الإتقان لكل موضوع |
| GET | `/api/v1/flashcards` | مراجعة البطاقات (`?topic_id=&confidence=&limit=&offset=`) |
| POST | `/api/v1/flashcards/{id}/confidence` | تسجيل تقييم المراجعة (`again`/`hard`/`good`/`easy`) |
| GET | `/api/v1/dashboard/summary` | لوحة المتعلم: الملفات، الإتقان، آخر المحاولات، مواضيع مرشّحة للمراجعة |

> `/api/health` خارج `/v1` عمدًا حتى لا تتعطّل أجهزة الفحص عند تغيير إصدار الـ API.

### أكواد الاستجابة

| الحالة | الكود | السبب |
| --- | --- | --- |
| `201` | Created | الرفع والاستخراج نجح → `ready_for_review` |
| `400` | Bad Request | الملف فاضي |
| `409` | Conflict | نفس الـ SHA-256 اترفع قبل كده — أو مفيش API key / مفيش مقاطع |
| `404` | Not Found | الملف غير موجود |
| `410` | Gone | الملف مفقود من القرص |
| `413` | Content Too Large | حجم الملف أكبر من `MAX_UPLOAD_SIZE_MB` |
| `415` | Unsupported Media Type | الامتداد غير مدعوم |
| `422` | Unprocessable | مخرجات الـ LLM ما نفعتش أو فشل إعادة الاستخراج |
| `502` | Bad Gateway | OpenRouter مش متاح أو رفض الطلب |

---

## خط أنابيب المعالجة (Extraction Pipeline)

```
رفع الملف
   │
   ├─ قراءة البايتات + SHA-256  ──►  تكرار؟  ──►  409 Conflict
   │
   ├─ حفظ آمن في uploads/   (اسم الملف = <hash[:16]>-<الاسم>)
   │
   └─ process_source_file()
         │
         ├─ status = processing
         ├─ extract_pages()      PDF/DOCX/PPTX/TXT → list[ExtractedPage]
         ├─ chunk_pages()        → list[ChunkData]  (يحمل رقم الصفحة)
         ├─ حفظ المقاطع في document_chunks
         └─ status = ready_for_review   (أو failed + error_message)
```

### الاستخراج (`app/services/extractor.py`)

| الصيغة | المكتبة | تتبّع الصفحة |
| --- | --- | --- |
| PDF | `pdfplumber` (احتياطي `pypdf`) | رقم الصفحة الفعلي |
| DOCX | `python-docx` | عدّ عناصر `<w:br w:type="page">` |
| PPTX | `python-pptx` | رقم الـ slide (1-based) |
| TXT / MD | مدمج | فصل بـ `\f` (Form Feed) |

**نقاط مهمة:**

- رقم الصفحة يبدأ من **1** ويظل دقيقًا حتى مع وجود slides فارغة —
  الـ slides الفارغة بتُستبعد لكن الترقيم لا يُزاح، فالأرقام المحفوظة هي
  الأرقام الحقيقية (وقد تحتوي فجوات، وهذا صحيح).
- التنظيف (`clean_text`) يوحّد المسافات والأسطر **دون** لمس الحروف العربية
  أو علامات الاتجاه الثنائي.
- ملفات DOCX بلا فواصل صفحات صريحة تُعامل كصفحة واحدة (لا يمكن معرفة
  تقسيم Word مسبقًا).

### التقسيم (`app/services/chunker.py`)

| الإعداد | الافتراضي | الوصف |
| --- | --- | --- |
| `CHUNK_TARGET_WORDS` | `650` | حجم الهدف (منتصف نطاق 500-800) |
| `CHUNK_MAX_WORDS` | `800` | الحد الأقصى الصارم |
| `CHUNK_MERGE_SHORT_PAGES` | `true` | دمج slides القصيرة لبلوغ نطاق الحجم |
| `CHUNK_MAX_PAGE_SPAN` | `32` | أقصى عدد slides في مقطع مدمج |

**لماذا خيار الدمج؟** الشرائح (slides) تحتوي ~25 كلمة فقط، فالتقسيم الحرفي
لكل slide منفردًا ينتج مقاطع صغيرة جدًا. عند تفعيل الدمج، الشرائح المتتالية
القصيرة تُدمج حتى بلوغ ~650 كلمة، ويُسجَّل رقم الـ slide **الأول** في المقطع
كمرجع للاقتباس.

القياس على ملفات الكورس الحقيقية:

```
الملف                         strict              merged
01Intro.pdf.pptx.pptx         42 chunks (avg 55)   4 chunks (avg 580)
section 2 DM.pptx.pptx        44 chunks (avg 23)   2 chunks (avg 519)
sec3 data mining.pptx.pptx    25 chunks (avg 24)   1 chunk  (avg 622)
```

اضبط `CHUNK_MERGE_SHORT_PAGES=false` إذا كان الدقة لكل slide أهم من حجم المقطع.

---

## توليد المحتوى التعليمي (LLM Content Generation)

مسار من مرحلتين، والفصل بينهم مقصود حتى يراجع الإنسان قبل أن يرى الطلاب أي شيء:

```
ready_for_review ملف
   │
   ├─ POST /api/v1/files/{id}/generate
   │     │
   │     ├─ الخطوة A: استخراج المواضيع
   │     │     chunks ──LLM──► مواضيع متميزة
   │     │     + مقارنة بجدول topics (تطبيع عربي/إنجليزي) → لا تكرار
   │     │
   │     ├─ الخطوة B: لكل موضوع نداء LLM واحد
   │     │     درس كامل (مصري + مصطلحات إنجليزية) + أمثلة محلولة خطوة بخطوة
   │     │     + معادلات LaTeX + أخطاء شائعة + ملخص
   │     │     + 5 بطاقات + 6 أسئلة **إنجليزية** (سهل/متوسط/صعب × MCQ/صح-خطأ/حل مشكلة)
   │     │     وشرح كل سؤال بالعربي (الأسئلة بلغة الامتحان)
   │     │
   │     └─ المسودة تُخزَّن على صف الملف (source_files.generated_content)
   │        لا شيء يُكتب في topics/lessons/questions/flashcards
   │
   ├─ GET /api/v1/files/{id}/draft        استعراض المسودة قبل الاعتماد
   │
   └─ POST /api/v1/files/{id}/publish     اعتماد إضافي بالكامل
         │
         ├─ الموضوع موجود؟ يحتفظ بحالته وإتقانه (لا يُضاعف ولا يُستبدل)
         ├─ الدرس موجود؟ يُحدَّث في مكانه (لا نسخة جديدة)
         ├─ الأسئلة/البطاقات تُضاف مع تخطي المكرر (بصمة SHA-256 للنص)
         ├─ كل سؤال يحمل مرجعًا: "lecture.pdf — slides 3-7"
         └─ status = published
```

### ضمانات النشر (لا شيء يُحذف أولًا)

- لا يوجد أي `DELETE` في مسار النشر — النشر **إضافي** بالكامل.
- `Topic.mastery_status` وجدول `quiz_attempts` لا يُمَسّان أبدًا بتقدمُ الطلاب محفوظ.
- النشر المتكرر لنفس المسودة لا يضيف شيئًا (idempotent — اختبارات تؤكد هذا).
- ملف آخر لنفس الموضوع **يوسّع** بنك الأسئلة والبطاقات، ولا يستبدل شيئًا.
- فشل موضوع واحد لا يُبطل العملية كاملة (الموضوع المتعطل يُتخطى).

### المواضيع الجديدة مقابل الموجودة

المطابقة عبر تطبيع العناوين (أحرف صغيرة، إزالة التشكيل، توحيد أشكال الألف
والة والي): «العَنَاجِمَة» و «العناجمة» يُعامَلان كعنوان واحد، و «Clustering.»
و «clustering» كذلك.

### بدون مفتاح API

نداء التوليد بلا `OPENROUTER_API_KEY` يفشل بأمان برسالة واضحة، والباقي منه يعمل طبيعيًا:

```json
{
  "detail": "OPENROUTER_API_KEY is not set. Add it to backend/.env to enable content generation."
}
```

---

## المعلم الذكي (AI Tutor — RAG)

مساعد دراسي بيجاوب بناءً على **المحتوى المنشور فقط** (RAG):

```
سؤال الطالب
   │
   ├─ 1. الاسترجاع (Retrieval)
   │     تضمين السؤال (embedding) ثم البحث في ChromaDB
   │     — مصدر الفهرس: مقاطع ملفات published فقط
   │     — يُرجع أفضل RAG_TOP_K مقاطع (افتراضي 6) مع أرقام الصفحات
   │
   ├─ 2. التوليد (Generation)
   │     Prompt صارم بالمصري:
   │     - المصطلحات الإنجليزية تبقى كما هي (Clustering، K-Means ...)
   │     - الاستشهاد إلزامي بصيغة [اسم الملف — صفحة N]
   │     - لو الإجابة غير موجودة في المقاطع، يكتب حرفيًا:
   │       "المعلومة دي مش مذكورة في السلايدات أو الملفات المرفوعة"
   │     - ممنوع اختراع صفحات أو معادلات أو معلومات
   │
   └─ 3. التحقق (Anti-fabrication guard)
         كل استشهاد في الرد يُطابق ضد المقاطع التي استُرجعت فعلًا؛
         أي صفحة أو اسم ملف لم يُسترجع يُسقط من قائمة الـ citations
         النهائية — المنظومة لا تُرجع استشهادًا مختلَقًا أبدًا.
```

مثال للنداء والرد:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/tutor/chat" `
  -H "Content-Type: application/json" `
  -d '{\"message\": \"إيه الفرق بين الـ K-Means والـ DBSCAN؟\", \"difficulty_level\": \"exam_prep\"}'
```

```json
{
  "reply": "Entropy بيقيس العشوائية... [lecture.pdf — صفحة 5]",
  "citations": [{ "filename": "lecture.pdf", "page": 5 }],
  "retrieved": 3,
  "model": "anthropic/claude-3.5-sonnet",
  "used_index": true
}
```

### خلفيات الـ embeddings (`EMBEDDING_BACKEND`)

| القيمة | تشغّل | ملاحظات |
| --- | --- | --- |
| `auto` (افتراضي) | `sentence-transformers` ← ثم OpenRouter API ← ثم ONNX المدمجة | يختار الأفضل المتاح على جهازك |
| `local` | نماذج محلية فقط | بلا إنترنت بعد أول تحميل |
| `api` | OpenRouter `/embeddings` فقط | `bge-m3` / `qwen3-embedding` هي الأقوى للعربي |

ملاحظة: على بيئة Python 3.14 قد لا يتوفر `sentence-transformers` (يعتمد على
torch)، لذا `auto` يفتر تفضيل الـ API عند وجود `OPENROUTER_API_KEY` (جودة
أعلى للعربي)، وإلا يسقط على الـ ONNX المدمجة في chromadb — تبعيات إضافية
صفير، وتنزيل نموذج ~80 MB مرة واحدة فقط عند أول فهرسة.

### تحديث الفهرسة تلقائيًا

| الحدث | اللي يحصل في الفهرس |
| --- | --- |
| `publish` | مقاطع الملف تُفهرس فورًا (و `vectors_indexed` في رد الـ publish) |
| بدء تشغيل الخادم | مسح شامل لكل ملفات `published` (idempotent) |
| `DELETE /files/{id}` | كل vectors الملف تُحذف — المُعيد لا يجيب من ملف محذوف |
| `retry` | الفيكتور القديم يُمسح (المحتوى اتغير، اعتمده تاني ليُفهرس مجددًا) |

---

## محرك التقييم والإتقان (Assessment & Mastery)

منظم كثلاث خدمات **بلا LLM إطلاقًا** — كل شيء حتمي:

```
app/services/assessment.py       التوليد + التصحيح + الإتقان
app/services/flashcard_service.py عرض البطاقات + تقييم المراجعة
app/services/dashboard_service.py لوحة المتعلم
```

### توليد الكويز (`POST /api/v1/quizzes/generate`)

```jsonc
{
  "topic_ids": [1, 3],        // اختياري — كل المواضيع لو اتساب
  "difficulty": "mixed",      // easy / medium / hard / mixed
  "count": 10,                // 1-50 — بيتقصّ عند حجم البنك المتاح
  "mode": "exam"              // exam يخفي correct_answer + explanation من الـ JSON
}
```

- الاختيار عشوائي من البنك المطابق للفلاتر (كل محاولة مختلفة)،
  والرد يجيب `available_count` عشان الـ UI يعرف إن البنك البيت أخف.
- في وضع `exam` الحقول المحجوبة تُحذف فعلًا (مش `null`) — مفيش تسريب
  للمفتاح في الـ payload.
- مفيش بند "quiz" مخزّن: الـ generate عديم الحالة، والـ submit
  بيستقبل IDs الأسئلة مباشرة.

### التصحيح (`POST /api/v1/quizzes/submit`)

| النوع | الطريقة |
| --- | --- |
| `mcq` | مطابقة نصّية متسامحة (بعد التطبيع العربي) — ويقبل **حرف الخيار** (أ/ب/ج/د أو 1/2/3) |
| `true_false` | أسماء بديلة: `صح/خطأ/true/false/1/0` بعد طيّ الهمزة (`خطأ` ← `خطا`) |
| `short_answer` | **تداخل كلمات مفتاحية** مع إجابة النموذج — عتبة النجاح 60%، والرد يجيب `earned` (0-100) جزئيًا |

- سطر لكل سؤال في الرد يضم المفتاح الكامل: `expected` + `explanation`
  + `source_reference` (مرجع الشريحة/الصفحة) — مناسبة للمراجعة الفورية.
- الأسئلة غير الموجودة تُرجع في `not_found` ولا تأثر على النتيجة.
- **محاولة `QuizAttempt` واحدة لكل موضوع** (جدول المحاولات لكل موضوع
  بالتصميم) — والرد يجمعها breakdown لكل موضوع بنتيجة منفصلة.

### بوليسي الإتقان — ثوابت مثبّتة + قابلة للضبط

```
متوسط آخر 3 محاولات (نافذة منزلقة بالزمن):
   >= 80  →  mastered
   50-79  →  learning
   <  50  →  needs_revision
   بلا محاولات →  not_started (مفيش إعادة تقييم)
```

- النافذة المنزلقة (آخر 3) بتضمن الطالب المتعثّر **ينزل** مستواه بسرعة
  لو بدأ يتعثر — وإن أراد الاسترداد فمحاولة واحدة ممتازة بعد فترة ضعيفة
  تعطي `learning` مش `mastered` (إعادة الترقية محتاجة تكرار للدرجات العالية).
- الثوابت في أعلى `assessment.py`: `MASTERY_MASTERED_THRESHOLD = 80`،
  `MASTERY_LEARNING_THRESHOLD = 50`، `MASTERY_HISTORY_WINDOW = 3`.

### البطاقات والمراجعة المتباعدة

`POST /api/v1/flashcards/{id}/confidence` بياخد التقييم الرباعي القياسي:
`again → low`، `hard → medium`، `good → medium`، `easy → high`
(عمود `confidence_level` ثلاثي — hard وgood يشتركوا في medium،
والإشارة المهمة محفوظة: فشل ← low، استرجاع سلس ← high).

### لوحة المتعلم (`GET /api/v1/dashboard/summary`)

`files.total` + `files.by_status` لإحصاء الحالات — `topics.studied`
(المواضيع اللي خرجت من not_started) + `topics.mastery`
مقسوم لكل حالة — آخر **10** محاولات بالترتيب الزمني — وطابور مراجعة
(حد 5): `needs_revision` أولًا، ثم `learning` الأضعف درجةً الأخيرة،
والمتقن مستبعد (يرجع تلقائيًا لو الأداء نزل تحت العتبة).

---

## الاختبارات

```powershell
cd backend
python -m pytest tests/ -v
```

**158 اختبار** في ستة ملفات — **61** في `tests/test_extraction.py` تغطي:

- **دقة أرقام الصفحات** — ملف PDF مولَّد برمجيًا بـ 4 صفحات، والاختبار يتحقق
  أن كل علامة مميزة تظهر على صفحتها الصحيحة تمامًا ولا تتسرب لغيرها.
- **الاستخراج** لكل صيغة (PDF / DOCX مع فاصل صفحة صريح / PPTX / TXT بـ `\f`).
- **التقسيم** — المقاطع داخل نطاق 500-800، لا مقطع يعبر صفحتين، النص العربي
  لا يتلوّث، وترتيب الـ `chunk_index`.
- **التخزين** — حظر `path traversal` في أسماء الملفات، وتطابق SHA-256.
- **الـ API** — الرفع، رفض التكرار (409)، الامتدادات الممنوعة (415)،
  الفهرسة، المعاينة، إعادة المحاولة، والحذف (مع التحقق من حذف المقاطع
  والبايتات من القرص).
- **الـ pipeline** — تدوير الحالة، ومنع تكرار المقاطع عند إعادة التشغيل.

> ملفات الاختبار تُكتب برمجيًا (بما في ذلك الـ PDF ببايتات محسوبة بدقة) فلا
> تحتاج أي مكتبة إضافية مثل `reportlab`.

**39 اختبار** في `tests/test_generation.py` تغطي (بـ LLM وهمي حتمي — **بدون**
استدعاء شبكة أو مفتاح حقيقي):

- **استخراج JSON** — سادة، داخل code fence، متلف بالكلام، مع نص عربي،
  ورفض الردود غير القابلة للتحليل.
- **تطبيع العناوين** — التشكيل، أشكال الألف، ة↔ه، ى↔ي، والترقيم يطوي
  العناوين المتشابهة ويُبقي المواضيع المختلفة منفصلة.
- **`/generate`** — تُنشأ مسودة دون كتابة أي صفوس في المنهج، تمييز
  المواضيع الموجودة، 404/409 للملفات الفاشلة أو الفارغة أو بلا مفتاح.
- **`/publish`** — إنشاء المواضيع والدروس والأسئلة (تغطي المستويات الثلاثة
  بأنواع متنوعة)، وأي سؤال يحمل مرجع صفحات/شرائح صحيح.
- **ضمانات "لا شيء يُحذف"** — إعادة النشر لنفس المسودة idempotent ولا تضيف
  شيئًا، تقدم الطالب و`mastery_status` لا يُمسّان، الدروس تُحدَّث دون تكرار،
  والملف الثاني لنفس الموضوع يوسّع بنك واحد دون إنشاء موضوع مكرر.

**16 اختبار** في `tests/test_tutor.py` تغطي (embedder حتمي مبني على hash
كلمات — استرجاع حقيقي بلا ملفات نماذج):

- **مخزن الفيكتور** — الـ metadata الصحيحة (file_id, filename, page_number,
  chunk_id)، إعادة الفهرسة idempotent، حذف الملف يمسح vectorsه فقط،
  والترتيب حسب الصلة، و`ensure_published_indexed` يفهرس الملفات
  المرشورة published فقط.
- **مسار الـ RAG** — سؤال بدون فهرس يعطي جملة الرفض حرفيًا بدون نداء LLM،
  والاستشهادات المُرجعة مأخوذة من الـ metadata وليس من كلام النموذج.
- **درع التزييف (anti-fabrication)** — أي استشهاد بصفحة/ملف لم يُسترجَع
  يُسقط من الرد النهائي حتى لو النموذج كتبه، بكل الصيغ (+ `page` إنجليزي).
- **`/tutor/chat`** — 422 للرسائل الفارغة وأدوار history الغريبة، وردود
  200 كاملة بالاستشهادات، ومعالجة `difficulty_level`.

**26 اختبار** في `tests/test_assessment.py` تغطي محرك التقييم بالكامل —
بلا LLM إطلاقًا، حتمي 100%:

- **التصحيح المحمَّد (deterministic grading)** — MCQ بمطابقة نصّية متسامحة
  (حالة حروف/مسافات/أقواس) وقبول حرف الخيار (أ/ب/ج/...)، وصح/خطأ بكل
  الأسماء البديلة (صح/خطأ/true/false/1/0 مع طيّ الهمزة)، والإجابات
  المقالية بتداخل الكلمات المفتاحية (عتبة 60% مع `earned` يساوي
  نسبة التداخل 0-100).
- **توليد الكويز** — فلاتر `difficulty`/`topic_ids`، سقف العدد بحجم
  البنك، عرض `available_count`، ووضع `exam` يحذف مفتاح الإجابة والشرح
  **فعليًا من الـ JSON** (`exclude_none`) بينما `practice` يعيدهم كاملين.
- **الإرسال** — النسبة الإجمالية لكل موضوع، سطر لكل سؤال بالمفتاح
  الكامل (`expected` + `explanation` + مرجع المصدر)، `not_found` للأسئلة
  غير الموجودة، محاولة `QuizAttempt` واحدة لكل موضوع بـ `answers_json`
  مطبَّع.
- **الإتقان (mastery)** — الثوابت مثبّتة باختبارات: متوسط آخر **3 محاولات**
  فقط (نافذة منزلقة): ≥80 → `mastered`، 50-79 → `learning`،
  <50 → `needs_revision`، وبلا محاولات → `not_started` — مع تنزيل
  الطالب المتعثّر وترقية اللي رجع للمستوى (استرداد يتطلب تكرارًا).
- **البطاقات** — الفلاتر (`topic_id`، `confidence`)، خريطة التقييم
  (again→low، hard/good→medium، easy→high)، و404 للبطاقة غير الموجودة.
- **الداشبورد** — إحصاء الملفات بحالة لكل حالة، إتقان المواضيع، آخر 10
  محاولات، وطابور المراجعة (needs_revision أولًا ثم learning الأضعف،
  والمتقن مستبعد).

**12 اختبار** في `tests/test_translation.py` تغطي الترجمة عند الطلب
(بـ LLM وهمي سكربتي — **بدون** شبكة ولا مفتاح):

- **الخدمة** — ترتيب الترجمات كما هي، المطالبة بنفس عدد العناصر
  (`LLMInvalidOutput` عند عدم التطابق)، ورفض الهدف غير المدعوم والنصوص
  الفاضية، واتجاهان (نص عربي لطلب العربي مقابل prompt إنجليزي لطلب الإنجليزي).
- **الكاش + إزالة التكرار** — النداء التاني على نفس النص يرجع `cached=true`
  من غير أي نداء للموديل، والنصوص المكررة داخل نفس الطلب تُترجم **مرة واحدة**
  وتُرجع لكل عنصر، وسقف LRU محدود.
- **`/translate`** — 200 بالترجمات والـ `target` والـ `model`، و422 لطلب فاضي
  أو عنصر فاضي أو هدف غريب أو نص أطول من 2000 حرف أو أكتر من 20 عنصر،
  و409 واضح لما مفيش `OPENROUTER_API_KEY`.

---

## المتطلبات

- **Python 3.10+** (تم التطوير والاختبار على Python 3.14)
- **Node.js 20+** (تم الاختبار على Node 24 / npm 11)

> ملاحظة: على Python 3.14، استخدم أحدث إصدارات المكتبات (كما في
> `requirements.txt`) لأن الإصدارات القديمة لا تملك wheels جاهزة، وتحتاج
> MSVC Build Tools للبناء من المصدر على Windows.

---

## التشغيل

### 1) الـ Backend

```powershell
cd backend

# تثبيت الاعتماديات
python -m pip install -r requirements.txt

# إنشاء ملف البيئة
Copy-Item .env.example .env

# تطبيق الـ migrations (ينشئ قاعدة البيانات والجداول)
python -m alembic upgrade head

# تشغيل السيرفر
python -m uvicorn app.main:app --reload
```

- **API**: <http://127.0.0.1:8000>
- **Swagger UI**: <http://127.0.0.1:8000/docs>
- **ReDoc**: <http://127.0.0.1:8000/redoc>
- **Health check**: <http://127.0.0.1:8000/api/health>
- **Files API**: <http://127.0.0.1:8000/docs#/files>

### مثال سريع على الرفع

```powershell
# PowerShell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/files/upload" -F "file=@lecture.pptx"

# bash
curl -X POST "http://127.0.0.1:8000/api/v1/files/upload" -F "file=@lecture.pdf"
```

### مثال كامل على التوليد والاعتماد

```powershell
# 1) رفع الملف (يرجع المعرف في الخانة id)  → ready_for_review
curl.exe -X POST "http://127.0.0.1:8000/api/v1/files/upload" -F "file=@section1 DM.pptx"

# 2) توليد محتوى من المقاطع → مسودة stored، منهج فأش
curl.exe -X POST "http://127.0.0.1:8000/api/v1/files/{id}/generate"

# 3) استعراض المسودة قبل الاعتماد
curl.exe "http://127.0.0.1:8000/api/v1/files/{id}/draft"

# 4) اعتماد — إضافي بالكامل، لا يحذف أي شيء
curl.exe -X POST "http://127.0.0.1:8000/api/v1/files/{id}/publish"
```

> بدون `OPENROUTER_API_KEY` في `backend/.env` سيرفر الـ generate
> بـ رمز `409` مع رسالة واضحة — باقي النظام يعمل طبيعي.

الرد المتوقع من `/api/health`:

```json
{
  "status": "ok",
  "app": "Data Mining Academy",
  "version": "0.1.0",
  "environment": "development",
  "database": "connected",
  "timestamp": "2026-10-17T14:02:01.530367+00:00"
}
```

### 2) الـ Frontend

```powershell
cd frontend

npm install
npm run dev
```

افتح <http://localhost:5173>. السيرفر يعمل تلقائيًا proxy لـ `/api` إلى
`http://127.0.0.1:8000` (انظر `vite.config.js`)، فلا حاجة لإعداد CORS أثناء التطوير.

أوامر أخرى:

```powershell
npm run build    # بناء نسخة الإنتاج في dist/
npm run preview  # معاينة نسخة الإنتاج محليًا
npm run lint     # فحص الكود بـ oxlint
```

---

## قاعدة البيانات

سبعة جداول:

| الجدول | الوصف |
| --- | --- |
| `source_files` | ملف محاضرة مرفوع (PDF/PPTX) + hash + status |
| `document_chunks` | مقاطع نصية قابلة للتضمين (embedding) لكل ملف |
| `topics` | وحدة دراسية بعنوان عربي/إنجليزي + مستوى الإتقان |
| `lessons` | محتوى الدرس (Markdown عربي) + الأهداف والمصطلحات والمعادلات |
| `questions` | بنك أسئلة (نصّها **إنجليزي** دائمًا؛ MCQ / صح-خطأ / إجابة قصيرة) + شرح عربي + صعوبة |
| `flashcards` | بطاقات تذكّر + مستوى الثقة |
| `quiz_attempts` | سجل محاولة اختبار كاملة (نتيجة + إجابات) |

**حالات `SourceFile.status`:**
`uploaded` → `processing` → `ready_for_review` → `published` | `failed`

**حالات `Topic.mastery_status`:**
`not_started` → `learning` → `needs_revision` → `mastered`

### إنشاء migration جديد

```powershell
cd backend

# توليد migration تلقائيًا من تعديلات الـ models
python -m alembic revision --autogenerate -m "description"

# تطبيقها
python -m alembic upgrade head

# التراجع عن خطوة واحدة
python -m alembic downgrade -1
```

---

## إضافة endpoint جديد

1. أنشئ الملف في `backend/app/api/v1/endpoints/`:

```python
# backend/app/api/v1/endpoints/reports.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("")
def list_reports(db: Session = Depends(get_db)) -> list[dict]:
    return []
```

2. سجّله في `backend/app/api/v1/router.py`:

```python
from app.api.v1.endpoints import health, reports

api_router.include_router(health.router)
api_router.include_router(reports.router)
```

سيصبح متاحًا على `/api/v1/reports` تلقائيًا.

---

## متغيرات البيئة

انسخ `.env.example` إلى `.env` وعدّل القيم:

| المتغير | الوصف | الافتراضي |
| --- | --- | --- |
| `DATABASE_URL` | رابط قاعدة البيانات | `sqlite:///./data/dm_academy.db` |
| `CHROMA_PERSIST_DIRECTORY` | مجلد حفظ ChromaDB | `./data/chroma` |
| `CHROMA_COLLECTION_NAME` | اسم الـ collection | `dm_academy_chunks` |
| `EMBEDDING_MODEL` | نموذج التضمين | `paraphrase-multilingual-MiniLM-L12-v2` |
| `ALLOWED_ORIGINS` | أصول CORS (مفصولة بفاصلة) | `http://localhost:5173,...` |
| `MAX_UPLOAD_SIZE_MB` | أقصى حجم للرفع | `50` |
| `ALLOWED_UPLOAD_TYPES` | الامتدادات المسموح بها | `.pdf,.pptx,.ppt,.docx,.txt,.md` |
| `CHUNK_TARGET_WORDS` | حجم المقطع المستهدف (كلمة) | `650` |
| `CHUNK_MAX_WORDS` | الحد الأقصى الصارم للمقطع | `800` |
| `CHUNK_MERGE_SHORT_PAGES` | دمج الشرائح القصيرة | `true` |
| `CHUNK_MAX_PAGE_SPAN` | أقصى عدد شرائح في مقطع مدمج | `32` |
| `OPENROUTER_API_KEY` | مفتاح OpenRouter للتوليد (بدونه يرد التوليد بـ 409) | *(فارغ)* |
| `OPENROUTER_BASE_URL` | رابط الـ API المتوافق مع OpenAI | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | النموذج الأساسي (أي slug من OpenRouter) | `anthropic/claude-3.5-sonnet` |
| `LLM_FALLBACK_MODEL` | نموذج احتياطي يجرَّب مرة عند فشل الأساسي | `google/gemini-2.0-flash` |
| `LLM_TEMPERATURE` | درجة العشوائية | `0.3` |
| `LLM_MAX_TOKENS` | أقصى طول للرد | `8192` |
| `LLM_TIMEOUT_SECONDS` | مهلة كل نداء | `120` |
| `EMBEDDING_BACKEND` | خلفية التضمين: `auto \| local \| api` | `auto` |
| `EMBEDDING_API_MODEL` | نموذج التضمين عبر OpenRouter (متعدد اللغات — مفضل للعربي) | `baai/bge-m3` |
| `RAG_TOP_K` | عدد المقاطع المسترجَعة لكل سؤال (4-6) | `6` |
| `RAG_MAX_HISTORY_MESSAGES` | أقصى عدد رسائل محادثة مرساة للنموذج | `12` |
| `RAG_TEMPERATURE` | درجة العشوائية في إجابة المعلم الذكي | `0.2` |

---

## الخطوات التالية (TO DO)

- [x] Pydantic schemas في `app/schemas/`
- [x] رفع الملفات (`POST /api/v1/files/upload`) + حساب SHA-256 ومنع التكرار
- [x] خدمة المعالجة: استخراج النص من PDF/PPTX/DOCX → تقسيم → حفظ المقاطع
- [x] تضمين المقاطع (embeddings) في ChromaDB + البحث الدلالي — **المعلم الذكي
  (RAG)**: فهرسة تلقائية للملفات المنشورة، استرجاع Top-K، وردود مُسندة على
  المصادر مع استشهادات متحقَّق منها ضد اختراع النموذج
- [x] محرك التقييم والإتقان: توليد كويز حتمي من بنك الأسئلة (وضع
  `exam` يخفي المفتاح)، تصحيح آلي لكل الأنواع، تسجيل المحاولات،
  وتحديث `mastery_status` بنافذة منزلقة — مع مراجعة البطاقات ولوحة المتعلم
- [ ] إكمال باقي الـ schemas والـ CRUD للمواضيع والدروس والأسئلة والبطاقات
- [ ] بقية شاشات الواجهة: البطاقات —
  الـ endpoints جاهزة ورا شاشة الـ ComingSoon الحالية
- [x] **كتالوج المواضيع** (`GET /api/v1/topics`): مواضيع المنهج مع عدد
  أسئلة/بطاقات كل موضوع وحالة الإتقان — أساس فلتر الكويز والتنقّل في الدروس
- [x] شاشة **بنك الأسئلة ومُحاكي الامتحان**: ثلاثة أطوار (إعداد/حل/نتيجة) فوق
  `POST /api/v1/quizzes/generate` و`submit` — فلتر مواضيع متعدد + صعوبة
  (سهل/متوسط/صعب/متنوّع) + عدد (5..30) + وضع **تدريب/امتحان**؛ شاشة الحل
  بسؤال واحد في المرة مع خريطة أسئلة (مُجاب/حالي)، تعليم للمراجعة، عدّاد
  تنازلي في وضع الامتحان (دقيقة/سؤال) مع تسليم تلقائي عند الصفر، وكشف
  الإجابة + الشرح + المصدر في وضع التدريب فقط؛ شاشة النتيجة بحلقة نسبة،
  تفصيل لكل موضوع مع انتقال الإتقان (قبل→بعد)، ومراجعة كاملة لكل سؤال
  (إجابتك/الإجابة الصحيحة/الشرح/المصدر) — مع مؤكِّدات للأسئلة غير المُجابة
  وللخروج، وتحديث فوري لشريط الإتقان في الهيدر
- [x] شاشة **المعلم الذكي**: محادثة كاملة فوق `POST /api/v1/tutor/chat` —
  ترانسكريبت طويل قابل للتمرير (user/assistant/أخطاء)، سِمبلات أسئلة جاهزة،
  مستوى الشرح بالأربعة `difficulty_level` (محفوظ)، إرسال بـ Enter مع عدّاد
  حروف (2000)، تمرير الـ history لآخر 24 دورة، تشيبات استشهاد inline
  (`[ملف — صفحة N]`) بجانب قائمة المصادر المتحقَّق منها، وmeta للرد
  (النموذج + عدد المقاطع المسترجَعة)، وتحذير كهرماني عند `used_index=false`،
  وmap واضح لأكواد الأخطاء (409 مفتاح ناقص / 502 نموذج / 503 فهرس)
- [x] هيكل الواجهة العربية: Layout بواجهة RTL افتراضية + تبديل إنجليزي LTR
  (محفوظ)، شريط جانبي قابل للطي + drawer/bottom-nav للموبايل، **لوحة
  التحكم** (متريكات + إجراءات سريعة + توزيع الإتقان + آخر المحاولات +
  طابور المراجعة)، و **مكتبة المنهج** (رفع بسحب وإفلات مع تحقق من
  الصيغة/الحجم، جدول بحالات ملونة، مودال مراجعة النص المستخرَج والمسودة
  قبل الاعتماد والتوليد والنشر)
- [x] توليد الدروس والأسئلة تلقائيًا من المقاطع عبر LLM (OpenRouter) — بمسودة
  ونشر إضافي لا يُحذف فيه أي محتوى سابق أبدًا
- [x] **الأسئلة بالإنجليزي + ترجمة عند الطلب**: الـ prompt يولّد نص السؤال
  والخيارات والإجابة **بالإنجليزية** (الشرح يفضل عربي)، والواجهة تعرض السؤال
  إنجليزي **دايمًا** مهما كانت لغة الواجهة، مع زر صغير **«عرض بالعربي»** أمام كل
  سؤال (في الحل وفي المراجعة) بينادي `POST /api/v1/translate` ويبدّل النص
  والخيارات للعربي مع كاش داخل العملية (بدون أي نداء متكرر) — والقيمة
  المُختارة تفضل إنجليزية فالتصحيح ما بيتأثرش باللغة المعروضة
- [x] شاشة **مركز المراجعة** (`/revision`): خطة واحدة فوق endpoints موجودة
  أصلًا **من غير أي backend جديد** — متريكات (مواضيع محتاجة مراجعة / تحت
  التعلم + بطاقات ضعيفة / متوسطة)، **طابور المواضيع** مرتّب من الأضعف
  (من `dashboard/summary`) مع زرّي «أعد الكويز» و«بطاقاته»، و**جلسة بطاقات**
  (لقطة *snapshot* من `GET /api/v1/flashcards` مش بتتبدّل تحت إيد المتعلّم)
  بفلتر موضوع + «شمّل المضمونة»، قلب البطاقة ثم تقييم رباعي
  (`POST /api/v1/flashcards/{id}/confidence`) مع شريط تقدّم ومتريكات بتتحدّث
  لحظيًا، و**آخر المحاولات** بزر إعادة — وكل أزرار الإعادة بتفتح الكويز على
  الموضوع ده فورًا عبر `/quiz?topic=<id>&start=1` (دعم deep-link جديد في شاشة
  الكويز: `topic` بتختار الموضوع و`start=1` بتبدأ فورًا)
- [x] شاشة **عارض الدروس** (`/lessons`): endpoints جديدة **قراءة فقط**
  (`GET /api/v1/lessons` للملخّصات + `GET /api/v1/lessons/{id}` للدرس كامل)،
  والواجهة قايمة مواضيع جانبية (بحث فوري + حالة الإتقان + عدّاد دروس كل موضوع)
  مع لوحة قراءة بتحمّل الدرس **كسول**؛ الأهداف والمتطلبات السابقة، ونص الدرس
  Markdown بمُصيّر صغير **جوه المشروع من غير أي مكتبة جديدة** (عناوين/قوايم
  متداخلة/اقتباسات/كود/جداول/عريض/كود inline — عناصر React مش HTML خام)،
  وكروت **المعادلات** (LaTeX كنص LTR)، وجدول **مسرد المصطلحات**، وجدول
  **المقارنات**، و**الخلاصة** في بوكس مميز، وزر «كويز على الدرس ده» بيفتح الكويز
  فورًا على الموضوع (`/quiz?topic=<id>&start=1`) + تنقّل السابق/التالي في ترتيب
  المنهج، ودعم deep-link `?topic=<id>` — والـ `scripts_seed_demo.py` بقى بينشئ
  درسًا تجريبيًا كامل لكل موضوع عشان الشاشة تبان من غير مفتاح LLM
