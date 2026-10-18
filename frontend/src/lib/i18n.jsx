/**
 * Bidirectional language layer.
 *
 * Arabic is the academic default (RTL); toggling to English flips
 * `<html dir>` to LTR so every logical Tailwind utility (ms/me/ps/pe,
 * start/end) mirrors automatically. The choice is persisted.
 */

import { createContext, useContext, useEffect, useMemo, useState } from 'react'

const STORAGE_KEY = 'dma-lang'

const DIRS = { ar: 'rtl', en: 'ltr' }

const STRINGS = {
  ar: {
    app: {
      // The Latin brand name is language-independent by design.
      title: 'Data Mining Academy',
      brand: 'Data Mining Academy',
      tagline: 'اتعلم Data Mining',
    },
    lang: {
      toggle: 'English',
      hint: 'بدّل لغة الواجهة (RTL/LTR)',
    },
    nav: {
      dashboard: 'لوحة التحكم',
      library: 'مكتبة المنهج والملفات',
      lessons: 'استعراض الدروس',
      tutor: 'المعلم الذكي',
      quiz: 'بنك الأسئلة والكويزات',
      flashcards: 'بطاقات التذكر',
      revision: 'مركز المراجعة',
      menu: 'فتح القائمة',
      closeMenu: 'إغلاق القائمة',
      collapse: 'تصغير الشريط الجانبي',
      expand: 'توسيع الشريط الجانبي',
      more: 'المزيد',
    },
    header: {
      progress: 'إتقان المنهج',
      progressEmpty: 'اعتمد أول محاضرة لبدء القياس',
    },
    dashboard: {
      title: 'لوحة التحكم',
      subtitle: 'نظرة سريعة على تقدمك في منهج تعدين البيانات',
      metrics: {
        lectures: 'عدد المحاضرات',
        lecturesSub: '{published} معتمدة من أصل {total}',
        lecturesEmpty: 'لسه اترفع ملف واحد ولا ملف',
        mastery: 'نسبة إتقان المنهج',
        masterySub: '{mastered} موضوع متقن من {total}',
        masteryEmpty: 'اعتمد محاضرة وخلّص كويز لبدء القياس',
        revise: 'موضوعات تحتاج مراجعة',
        reviseSub: '{learning} موضوع تحت التعلم كمان',
        reviseAllGood: 'مفيش حاجة محتاجة مراجعة دلوقتي',
      },
      quick: {
        title: 'إجراءات سريعة',
        subtitle: 'ضغطة واحدة من الصفحة الرئيسية',
        quiz: 'ابدأ كويز سريع',
        tutor: 'اسأل المعلم الذكي',
        upload: 'ارفع محاضرة',
      },
      dist: {
        title: 'توزيع الإتقان على المواضيع',
        of: 'من {total} موضوع',
        empty: 'لسه مفيش مواضيع في المنهج',
        statuses: {
          not_started: 'مش بدأ',
          learning: 'تحت التعلم',
          needs_revision: 'محتاج مراجعة',
          mastered: 'متقن',
        },
      },
      recent: {
        title: 'آخر محاولات الكويز',
        empty:
          'لسه مفيش محاولات — ابدأ أول كويز من «بنك الأسئلة» بعد اعتماد أول محاضرة.',
        attempts: 'سؤال',
        viewAll: 'بنك الأسئلة',
      },
      queue: {
        title: 'طابور المراجعة',
        hint: 'ترتيب أضعف المواضيع — راجّعها ببطاقات التذكر',
        empty: 'منطقة مريحة: مفيش طابور مراجعة دلوقتي',
        attempts: '{n} محاولة',
        lastScore: 'آخر درجة: {score}%',
        go: 'ابدأ المراجعة',
      },
      emptyCta: 'ارفع أول محاضرة',
      offline:
        'مش قادرين نوصل للخادم — اتأكد إن الـ backend شغال على 127.0.0.1:8000',
      retry: 'إعادة المحاولة',
    },
    library: {
      title: 'مكتبة المنهج والملفات',
      subtitle: 'ارفع محاضراتك، راجع النص المستخرَج، وبعدين اعتمد النشر',
      drop: {
        title: 'اسحب ملف المحاضرة هنا أو اضغط للاختيار',
        hint: 'PDF وPPTX وPPT وDOCX وTXT وMD — حتى {mb} ميجا',
        uploading: 'جارٍ الرفع والاستخراج…',
        wrongType: 'صيغة «{name}» غير مدعومة.',
        tooBig: 'الملف «{name}» أكبر من {mb} ميجا.',
      },
      table: {
        name: 'الملف',
        status: 'الحالة',
        pages: 'صفحات/شرائح',
        chunks: 'مقاطع',
        size: 'الحجم',
        uploaded: 'تاريخ الرفع',
        actions: 'إجراءات',
        empty: 'لسه مفيش ملفات',
        emptyHint: 'ابدأ برفع أول محاضرة من الصندوق فوق',
        total: '{total} ملف',
      },
      status: {
        uploaded: 'تم الرفع',
        processing: 'جارٍ المعالجة',
        ready_for_review: 'جاهزة للمراجعة',
        published: 'منشورة',
        failed: 'فشل',
      },
      actions: {
        preview: 'مراجعة قبل الاعتماد',
        generate: 'توليد المحتوى',
        publish: 'اعتماد النشر',
        retry: 'إعادة المحاولة',
        del: 'حذف',
      },
      banner: {
        uploaded: 'اترفع «{name}» واتستخرج بنجاح — راجعه قبل الاعتماد.',
        deleted: 'اتحذف «{name}».',
        generated:
          'تألّفت مسودة {topics} موضوع ({new} جديد) — اعتمدها لما تكون جاهز.',
        published:
          'نُشر «{name}»: {topics} موضوع و{questions} سؤال و{cards} بطاقة.',
      },
      confirmDelete: {
        title: 'حذف الملف؟',
        body:
          'هيتحذف «{name}» بكل مقاطعه من القرص وقاعدة البيانات وبيتمسح فهرس RAG بتاعه.' +
          ' ده مش بيمسح الموضوعات المنشورة ولا تقدم الطالب. متأكد؟',
      },
      review: {
        title: 'مراجعة المحتوى المستخرَج',
        closes: 'إغلاق',
        stats: {
          pages: 'صفحات/شرائح',
          words: 'كلمة',
          chunks: 'مقاطع',
        },
        draftTitle: 'المسودة المُولَّدة — {count} موضوع',
        draftMeta: 'النموذج: {model} • {when}',
        draftEmpty:
          'لسه مفيش مسودة محتوى. اضغط «توليد المحتوى» عشان المعلم الذكي يبني' +
          ' الدروس والأسئلة والبطاقات من النص المستخرَج.',
        topics: 'الموضوعات',
        objectives: 'الأهداف',
        cards: 'بطاقات',
        questions: 'أسئلة',
        publish: 'اعتماد ونشر',
        republish: 'إعادة النشر',
        publishing: 'جارٍ النشر…',
        publishedOk: 'تم النشر بنجاح: {topics} موضوع و{questions} سؤال و{cards} بطاقة.',
        pagesTitle: 'الصفحات المستخرَعة ({count})',
        page: 'صفحة/شريحة',
        fullText: 'النص الكامل',
      },
    },
    common: {
      loading: 'جارٍ التحميل…',
      cancel: 'إلغاء',
      confirm: 'تأكيد الحذف',
      close: 'إغلاق',
      delete: 'حذف',
      offline:
        'مش قادرين نوصل للخادم — اتأكد إن الـ backend شغال على 127.0.0.1:8000',
      notFound: 'الصفحة غير موجودة',
      backHome: 'العودة إلى لوحة التحكم',
      soon: 'قريبًا',
    },
    tutor: {
      title: 'المعلم الذكي',
      subtitle:
        'إجابات مُسندة على محتواك المنشور — كل استشهاد متحقَّق منه ضد اختراع النموذج',
      badge: 'مقاطع مُفهرَسة + استشهادات موثّقة',
      levelLabel: 'مستوى الشرح',
      levels: {
        simple: 'بسيط',
        normal: 'عادي',
        advanced: 'متقدم',
        exam_prep: 'إعداد امتحان',
      },
      composer: {
        placeholder: 'اسأل أي حاجة في المنهج…',
        send: 'إرسال',
        thinking: 'المعلم بيفكر…',
        hint: 'Enter للإرسال — Shift+Enter لسطر جديد',
        maxChars: '{n}/{max}',
      },
      empty: {
        title: 'اسأل المعلم الذكي',
        desc:
          'كل سؤال بيتحول لمقاطع من محاضراتك المنشورة (RAG)، والإجابة بترجع' +
          ' لشريحة محددة — ومفيش أي حاجة بتُختلق من خارج المحتوى.',
        samples: [
          'ما الفرق بين K-Means و DBSCAN؟',
          'اشرح Entropy بطريقة بسيطة بمثال',
          'لو التقييم للصف، ما أهمية المعايرة Calibration؟',
        ],
      },
      message: {
        citations: 'المصادر',
        page: 'صفحة',
        retrieved: '{n} مقاطع مسترجَعة',
        noIndex:
          'الرد ده مش مُسند على فهرس المنهج — اعتمد محاضرة استنى الفهرسة تخلص.',
      },
      actions: { clear: 'مسح المحادثة', cleared: 'اتمسحت المحادثة — نبدأ من جديد؟' },
      errors: {
        noKey:
          'مفيش OPENROUTER_API_KEY في backend/.env — ضيفه، وهو أول شرط لتشغيل المعلم.',
        unavailable: 'النموذج مش متاح دلوقتي — جرب تاني بعد شوية.',
        embeddings:
          'نموذج التضمينات (embeddings) مش جاهز — جرب تاني بعد ما يخلص التنزيل.',
        invalid: 'السؤال لازم يكون حرفين على الأقل.',
        offline:
          'مش قادرين نوصل للخادم — اتأكد إن الـ backend شغال على 127.0.0.1:8000',
      },
    },
    quiz: {
      title: 'بنك الأسئلة ومُحاكي الامتحان',
      subtitle:
        'كويزات بتتولّد من بنك الأسئلة — تصحيح فوري ونتيجة لكل موضوع وتحديث مباشر للإتقان',
      setup: {
        title: 'ظبّط الكويز',
        subtitle: 'اختار المواضيع والمستوى والوضع، وبعدين ابدأ',
        difficulty: 'مستوى الصعوبة',
        difficulties: { easy: 'سهل', medium: 'متوسط', hard: 'صعب', mixed: 'متنوّع' },
        count: 'عدد الأسئلة',
        mode: 'الوضع',
        modes: {
          practice: { title: 'تدريب', desc: 'نموذج الإجابة والشرح متاحين فورًا أثناء الحل' },
          exam: { title: 'امتحان', desc: 'الإجابات مخفية لغاية التسليم — محاكاة حقيقية' },
        },
        topics: 'المواضيع',
        allTopics: 'كل المواضيع',
        topicsLoading: 'بيجيب المواضيع…',
        noTopics: 'مفيش مواضيع منشورة لسه — اعتمد محاضرة من المكتبة الأول',
        selectAll: 'تحديد الكل',
        clearSel: 'إلغاء التحديد',
        availableNote: 'بنك أسئلة المنهج: {n} سؤال',
        questionCount: '{n} سؤال',
        start: 'ابدأ الكويز',
        starting: 'بيجهّز الأسئلة…',
      },
      active: {
        questionOf: 'سؤال {n} من {total}',
        answered: '{n} متجاوب',
        flag: 'علّم للمراجعة',
        flagged: 'مُعلَّم للمراجعة',
        prev: 'السابق',
        next: 'التالي',
        submit: 'سلّم الكويز',
        submitting: 'بيصحّح…',
        reveal: 'اكشف الإجابة',
        hide: 'اخفِ الإجابة',
        answerKey: 'نموذج الإجابة',
        explanation: 'الشرح',
        source: 'المصدر',
        shortAnswerPlaceholder: 'اكتب إجابتك هنا…',
        mcqHint: 'اختار خيار واحد',
        tfHint: 'صح ولا خطأ؟',
        timeLeft: 'الوقت المتبقي',
        elapsed: 'الوقت المستغرق',
        exit: 'خروج',
        confirmExit: 'لو خرجت هتخسر تقدمك في الكويز ده.',
        answeredAll: 'جاوبت على كل الأسئلة',
        unansweredNote: 'لسه {n} سؤال من غير إجابة',
        confirmSubmit: 'فيه {n} سؤال من غير إجابة — تحب تسلّم كده؟',
        confirmSubmitOk: 'أيوه سلّم',
        navigation: 'خريطة الأسئلة',
      },
      translate: {
        showAr: 'عرض بالعربي',
        showEn: 'English',
        translating: 'بيترجم…',
        errors: {
          noKey: 'الترجمة محتاجة OPENROUTER_API_KEY في backend/.env — ضيفه وجرّب تاني.',
          unavailable: 'الترجمة مش متاحة دلوقتي — جرّب تاني بعد شوية.',
          offline: 'مش قادرين نوصل للخادم — اتأكد إن الـ backend شغال.',
        },
      },
      types: { mcq: 'اختيار متعدد', true_false: 'صح / خطأ', short_answer: 'إجابة قصيرة' },
      results: {
        title: 'النتيجة',
        score: 'النتيجة',
        of: '{correct} صح من {total}',
        breakdown: 'النتيجة لكل موضوع',
        previous: 'قبل',
        updated: 'بعد',
        review: 'مراجعة الأسئلة',
        yourAnswer: 'إجابتك',
        correctAnswer: 'الإجابة الصحيحة',
        notAnswered: 'من غير إجابة',
        correct: 'صح',
        wrong: 'غلط',
        partial: 'جزئي {n}%',
        notFound: 'الأسئلة دي مش موجودة في البنك: {ids}',
        retry: 'أعد نفس الكويز',
        newQuiz: 'كويز جديد',
        dashboard: 'روح للوحة التحكم',
        mastery: {
          not_started: 'لم يبدأ',
          learning: 'تحت التعلم',
          needs_revision: 'محتاج مراجعة',
          mastered: 'متقن',
        },
      },
      empty: {
        title: 'مفيش أسئلة في البنك',
        desc:
          'مفيش أسئلة مطابقة للفلتر ده — جرّب مستوى تاني أو اعتمد محاضرة' +
          ' عشان تتولّد أسئلة جديدة.',
        back: 'رجوع للإعداد',
      },
      errors: {
        offline:
          'مش قادرين نوصل للخادم — اتأكد إن الـ backend شغال على 127.0.0.1:8000',
        generate: 'تعذّر تجهيز الأسئلة — جرّب تاني.',
        submit: 'تعذّر تصحيح الكويز — جرّب تسلّم تاني.',
      },
    },
    revision: {
      title: 'مركز المراجعة',
      subtitle: 'خطة واحدة مركّزة: أضعف مواضيعك + البطاقات اللي محتاجة تثبيت',
      refresh: 'حدّث الخطة',
      metrics: {
        needsRevision: 'مواضيع محتاجة مراجعة',
        learning: 'مواضيع تحت التعلم',
        weakCards: 'بطاقات ثقتها واطية',
        mediumCards: 'بطاقات متوسطة',
      },
      queue: {
        title: 'طابور المواضيع',
        hint: 'مرتّب من الأضعف للأقوى — ابدأ من فوق',
        empty: 'منطقة مريحة: مفيش مواضيع محتاجة مراجعة دلوقتي',
        attempts: '{n} محاولة',
        lastScore: 'آخر درجة: {score}%',
        noScore: 'لسه مفيش محاولات',
        retake: 'أعد الكويز',
        cards: 'بطاقاته',
      },
      cards: {
        title: 'جلسة بطاقات المراجعة',
        hint: 'اقلب البطاقة وقيّم نفسك بصدق — التقييم بيحدّث ثقة البطاقة على الخادم.',
        progress: 'بطاقة {n} من {total}',
        front: 'السؤال',
        back: 'الإجابة',
        flip: 'اقلب البطاقة',
        skip: 'تخطي',
        ratings: {
          again: 'أعِد',
          hard: 'صعب',
          good: 'تمام',
          easy: 'سهل',
        },
        filters: {
          label: 'الموضوع',
          all: 'كل المواضيع',
          includeHigh: 'شمّل البطاقات المضمونة',
        },
        tones: {
          low: 'ثقة واطية',
          medium: 'ثقة متوسطة',
          high: 'ثقة عالية',
        },
        empty: 'مفيش بطاقات للمراجعة دلوقتي',
        emptyHint: 'اعتمد محاضرة عشان تتولّد بطاقات جديدة.',
        emptyFiltered: 'مفيش بطاقات في الموضوع ده',
        emptyFilteredHint: 'جرّب «كل المواضيع».',
        done: {
          title: 'خلصت جلسة المراجعة',
          desc: 'راجعت {reviewed} بطاقة — {improved} بقى تقييمها أعلى.',
          descSkipped: 'قفلت الجلسة من غير تقييم — التقييم هو اللي بيثبّت المعلومة.',
          restart: 'جلسة جديدة',
          quiz: 'كويز على أضعف موضوع',
        },
      },
      recent: {
        title: 'آخر المحاولات',
        hint: 'أعد أي محاولة من هنا مباشرة',
        empty: 'لسه مفيش محاولات كويز',
        retake: 'إعادة',
        attempts: 'سؤال',
      },
      empty: 'لسه مفيش محتوى منشور',
      emptyHint: 'ارفع محاضرة واعتمدها من مكتبة المنهج، وبعدين ابدأ المراجعة.',
      goLibrary: 'مكتبة المنهج',
      offline:
        'مش قادرين نوصل للخادم — اتأكد إن الـ backend شغال على 127.0.0.1:8000',
      retry: 'إعادة المحاولة',
      sessionError: 'التقييم مافتحش — جرّب تاني.',
    },
    lessons: {
      title: 'استعراض الدروس',
      subtitle: 'الدروس المنشورة كاملة: أهداف، شرح، معادلات، مسرد مصطلحات، وخلاصة',
      search: 'ابحث باسم الموضوع…',
      topics: 'المواضيع',
      noLessons: 'مش منشور',
      empty: 'لسه مفيش دروس منشورة',
      emptyHint: 'ارفع محاضرة واعتمد نشرها من مكتبة المنهج، وهيتولّد درس لكل موضوع.',
      goLibrary: 'مكتبة المنهج',
      offline:
        'مش قادرين نوصل للخادم — اتأكد إن الـ backend شغال على 127.0.0.1:8000',
      retry: 'إعادة المحاولة',
      refresh: 'تحديث',
      noLesson: 'الموضوع ده لسه مفيش له درس منشور',
      noLessonHint: 'جرّب موضوع تاني، أو اعتمد محاضرة جديدة عشان يتولّد الدرس.',
      noMatch: 'مفيش موضوع بالاسم ده',
      pick: 'اختار موضوع من القايمة عشان تقرأ الدرس.',
      loadingLesson: 'جارٍ تحميل الدرس…',
      lessonError: 'الدرس مفتحش — جرّب تاني.',
      blocks: {
        objectives: 'أهداف الدرس',
        prerequisites: 'معلومات سابقة مطلوبة',
        content: 'شرح الدرس',
        formulas: 'المعادلات',
        terminology: 'مسرد المصطلحات',
        comparisons: 'مقارنات',
        summary: 'الخلاصة',
      },
      terminologyTable: {
        term: 'المصطلح (EN)',
        arabic: 'المقابل العربي',
        definition: 'التعريف',
      },
      comparisonTable: {
        pair: 'المقارنة',
        aspect: 'وجه المقارنة',
        detail: 'التفصيل',
      },
      formulaNote: 'امتى تستخدمها',
      chars: '{n} حرف',
      actions: {
        quiz: 'كويز على الدرس ده',
        prev: 'السابق',
        next: 'التالي',
      },
    },
    placeholder: {
      tutor: {
        title: 'المعلم الذكي',
        desc:
          'شاشة المحادثة مع المعلم الذكي (RAG) بإجابات مسنودة على المحتوى المنشور' +
          ' مع استشهادات متحقَّق منها — جزء من المرحلة الجاية من الواجهة.',
      },
      quiz: {
        title: 'بنك الأسئلة والكويزات',
        desc:
          'جهاز محاكاة الامتحان: كويزات سريعة ووضع الاختبار (بدون نموذج الإجابة)،' +
          ' مع تصحيح فوري ونتيجة لكل موضوع — جزء من المرحلة الجاية من الواجهة.',
      },
      flashcards: {
        title: 'بطاقات التذكر',
        desc:
          'واجهة المراجعة بالتقييم الرباعي (again / hard / good / easy) مع' +
          ' فلاتر حسب الموضوع ونسبة الثقة — جزء من المرحلة الجاية من الواجهة.',
      },
      poweredBy: 'الـ endpoints الجاهزة في الـ backend واللي الواجهة هتتوابل عليها:',
      eta: 'المرحلة الجاية من التطوير',
      back: 'رجوع للوحة التحكم',
    },
  },
  en: {
    app: {
      // Same Latin brand in every language.
      title: 'Data Mining Academy',
      brand: 'Data Mining Academy',
      tagline: 'Learn Data Mining',
    },
    lang: {
      toggle: 'العربية',
      hint: 'Switch interface language (RTL/LTR)',
    },
    nav: {
      dashboard: 'Dashboard',
      library: 'Course Library & Upload',
      lessons: 'Lesson Viewer',
      tutor: 'AI Tutor',
      quiz: 'Quiz & Exam Simulator',
      flashcards: 'Flashcards',
      revision: 'Revision Center',
      menu: 'Open menu',
      closeMenu: 'Close menu',
      collapse: 'Collapse sidebar',
      expand: 'Expand sidebar',
      more: 'More',
    },
    header: {
      progress: 'Course mastery',
      progressEmpty: 'Publish a lecture to start tracking',
    },
    dashboard: {
      title: 'Dashboard',
      subtitle: 'A quick look at your progress through the curriculum',
      metrics: {
        lectures: 'Lectures',
        lecturesSub: '{published} published of {total} total',
        lecturesEmpty: 'No file uploaded yet',
        mastery: 'Overall mastery',
        masterySub: '{mastered} of {total} topics mastered',
        masteryEmpty: 'Publish a lecture and take a quiz to start tracking',
        revise: 'Topics needing revision',
        reviseSub: '{learning} more topics still learning',
        reviseAllGood: 'Nothing needs revision right now',
      },
      quick: {
        title: 'Quick actions',
        subtitle: 'One press from the home page',
        quiz: 'Start a quick quiz',
        tutor: 'Ask the AI tutor',
        upload: 'Upload a lecture',
      },
      dist: {
        title: 'Mastery distribution',
        of: 'of {total} topics',
        empty: 'No topics in the curriculum yet',
        statuses: {
          not_started: 'Not started',
          learning: 'Learning',
          needs_revision: 'Needs revision',
          mastered: 'Mastered',
        },
      },
      recent: {
        title: 'Recent quiz attempts',
        empty:
          'No attempts yet — start your first quiz from the "Quiz" page after publishing a lecture.',
        attempts: 'questions',
        viewAll: 'Quiz bank',
      },
      queue: {
        title: 'Revision queue',
        hint: 'Weakest topics first — review them with flashcards',
        empty: 'Comfortable state: no revision queue right now',
        attempts: '{n} attempts',
        lastScore: 'Last score: {score}%',
        go: 'Review',
      },
      emptyCta: 'Upload your first lecture',
      offline: 'Cannot reach the server — make sure the backend runs on 127.0.0.1:8000',
      retry: 'Retry',
    },
    library: {
      title: 'Course Library & Upload',
      subtitle: 'Upload lectures, review the extracted text, then approve publication',
      drop: {
        title: 'Drag a lecture file here or click to browse',
        hint: 'PDF / PPTX / PPT / DOCX / TXT / MD — up to {mb} MB',
        uploading: 'Uploading and extracting…',
        wrongType: '"{name}" has an unsupported file type.',
        tooBig: '"{name}" is larger than {mb} MB.',
      },
      table: {
        name: 'File',
        status: 'Status',
        pages: 'Pages/slides',
        chunks: 'Chunks',
        size: 'Size',
        uploaded: 'Uploaded',
        actions: 'Actions',
        empty: 'No files yet',
        emptyHint: 'Start by uploading your first lecture using the dropzone above',
        total: '{total} files',
      },
      status: {
        uploaded: 'Uploaded',
        processing: 'Processing',
        ready_for_review: 'Ready for review',
        published: 'Published',
        failed: 'Failed',
      },
      actions: {
        preview: 'Review before publish',
        generate: 'Generate content',
        publish: 'Publish',
        retry: 'Retry',
        del: 'Delete',
      },
      banner: {
        uploaded: '"{name}" uploaded and extracted — review it before approving.',
        deleted: '"{name}" deleted.',
        generated:
          'Draft generated: {topics} topics ({new} new) — approve it when ready.',
        published: '"{name}" published: {topics} topics, {questions} questions, {cards} flashcards.',
        republish:
          'Already published — republishing only integrates newly added content.',
      },
      confirmDelete: {
        title: 'Delete this file?',
        body:
          '"{name}" will be removed from disk, the database, and its RAG index.' +
          ' Published topics and learner progress are never touched. Are you sure?',
      },
      review: {
        title: 'Review the extracted content',
        closes: 'Close',
        stats: {
          pages: 'Pages/slides',
          words: 'Words',
          chunks: 'Chunks',
        },
        draftTitle: 'Generated draft — {count} topics',
        draftMeta: 'Model: {model} • {when}',
        draftEmpty:
          'No content draft yet. Press "Generate content" to let the AI tutor build' +
          ' lessons, questions and flashcards from the extracted text.',
        topics: 'Topics',
        objectives: 'Objectives',
        cards: 'flashcards',
        questions: 'questions',
        publish: 'Approve & publish',
        republish: 'Republish',
        publishing: 'Publishing…',
        publishedOk: 'Published: {topics} topics, {questions} questions, {cards} flashcards.',
        pagesTitle: 'Extracted pages ({count})',
        page: 'Page/slide',
        fullText: 'Full text',
      },
    },
    common: {
      loading: 'Loading…',
      cancel: 'Cancel',
      confirm: 'Confirm delete',
      close: 'Close',
      delete: 'Delete',
      offline: 'Cannot reach the server — make sure the backend runs on 127.0.0.1:8000',
      notFound: 'Page not found',
      backHome: 'Back to the dashboard',
      soon: 'Coming soon',
    },
    tutor: {
      title: 'AI Tutor',
      subtitle:
        'Answers grounded in your published content — every citation verified, never invented',
      badge: 'Indexed chunks + verified citations',
      levelLabel: 'Explanation depth',
      levels: {
        simple: 'Simple',
        normal: 'Normal',
        advanced: 'Advanced',
        exam_prep: 'Exam prep',
      },
      composer: {
        placeholder: 'Ask anything from the curriculum…',
        send: 'Send',
        thinking: 'The tutor is thinking…',
        hint: 'Enter to send — Shift+Enter for a new line',
        maxChars: '{n}/{max}',
      },
      empty: {
        title: 'Ask the AI tutor',
        desc:
          'Every question is matched to chunks of your published lectures (RAG) and the' +
          ' reply points back to the exact slide — nothing is invented outside the content.',
        samples: [
          'What is the difference between K-Means and DBSCAN?',
          'Explain Entropy simply with an example',
          'Why does calibration matter for grading?',
        ],
      },
      message: {
        citations: 'Sources',
        page: 'page',
        retrieved: '{n} chunks retrieved',
        noIndex:
          'This reply was not grounded in the course index — approve a lecture and let' +
          ' the indexing finish first.',
      },
      actions: { clear: 'Clear chat', cleared: 'Chat cleared — shall we start over?' },
      errors: {
        noKey:
          'No OPENROUTER_API_KEY in backend/.env — add it, it is the first requirement.',
        unavailable: 'The model is unavailable right now — try again shortly.',
        embeddings:
          'The embedding model is not ready yet — try again once its download completes.',
        invalid: 'The question needs at least two characters.',
        offline: 'Cannot reach the server — make sure the backend runs on 127.0.0.1:8000',
      },
    },
    quiz: {
      title: 'Question Bank & Exam Simulator',
      subtitle:
        'Quizzes drawn from the question bank — instant grading, a score per topic and live mastery updates',
      setup: {
        title: 'Set up the quiz',
        subtitle: 'Pick the topics, difficulty and mode, then start',
        difficulty: 'Difficulty',
        difficulties: { easy: 'Easy', medium: 'Medium', hard: 'Hard', mixed: 'Mixed' },
        count: 'Number of questions',
        mode: 'Mode',
        modes: {
          practice: { title: 'Practice', desc: 'Answer key and explanations are available while you solve' },
          exam: { title: 'Exam', desc: 'Answers stay hidden until you submit — a real simulation' },
        },
        topics: 'Topics',
        allTopics: 'All topics',
        topicsLoading: 'Loading topics…',
        noTopics: 'No published topics yet — approve a lecture from the library first',
        selectAll: 'Select all',
        clearSel: 'Clear',
        availableNote: 'Curriculum question bank: {n} questions',
        questionCount: '{n} questions',
        start: 'Start quiz',
        starting: 'Preparing questions…',
      },
      active: {
        questionOf: 'Question {n} of {total}',
        answered: '{n} answered',
        flag: 'Flag for review',
        flagged: 'Flagged for review',
        prev: 'Previous',
        next: 'Next',
        submit: 'Submit quiz',
        submitting: 'Grading…',
        reveal: 'Reveal answer',
        hide: 'Hide answer',
        answerKey: 'Answer key',
        explanation: 'Explanation',
        source: 'Source',
        shortAnswerPlaceholder: 'Type your answer here…',
        mcqHint: 'Pick one option',
        tfHint: 'True or false?',
        timeLeft: 'Time left',
        elapsed: 'Elapsed',
        exit: 'Exit',
        confirmExit: 'Leaving now discards your progress in this quiz.',
        answeredAll: 'You answered every question',
        unansweredNote: '{n} questions still unanswered',
        confirmSubmit: '{n} questions are unanswered — submit anyway?',
        confirmSubmitOk: 'Yes, submit',
        navigation: 'Question map',
      },
      translate: {
        showAr: 'Show in Arabic',
        showEn: 'English',
        translating: 'Translating…',
        errors: {
          noKey: 'Translation needs OPENROUTER_API_KEY in backend/.env — add it and retry.',
          unavailable: 'Translation is unavailable right now — please try again.',
          offline: 'Cannot reach the server — make sure the backend runs.',
        },
      },
      types: { mcq: 'Multiple choice', true_false: 'True / False', short_answer: 'Short answer' },
      results: {
        title: 'Result',
        score: 'Score',
        of: '{correct} correct out of {total}',
        breakdown: 'Score per topic',
        previous: 'before',
        updated: 'after',
        review: 'Review questions',
        yourAnswer: 'Your answer',
        correctAnswer: 'Correct answer',
        notAnswered: 'No answer',
        correct: 'Correct',
        wrong: 'Wrong',
        partial: 'Partial {n}%',
        notFound: 'These questions were not in the bank: {ids}',
        retry: 'Retake this quiz',
        newQuiz: 'New quiz',
        dashboard: 'Go to dashboard',
        mastery: {
          not_started: 'Not started',
          learning: 'Learning',
          needs_revision: 'Needs revision',
          mastered: 'Mastered',
        },
      },
      empty: {
        title: 'The question bank is empty',
        desc:
          'No questions match this filter — try another difficulty or approve a' +
          ' lecture so fresh questions get generated.',
        back: 'Back to setup',
      },
      errors: {
        offline: 'Cannot reach the server — make sure the backend runs on 127.0.0.1:8000',
        generate: 'Could not prepare the questions — please try again.',
        submit: 'Could not grade the quiz — please try submitting again.',
      },
    },
    revision: {
      title: 'Revision Center',
      subtitle: 'One focused plan: your weakest topics plus the cards that need pinning down',
      refresh: 'Refresh plan',
      metrics: {
        needsRevision: 'Topics needing revision',
        learning: 'Topics still learning',
        weakCards: 'Low-confidence cards',
        mediumCards: 'Medium-confidence cards',
      },
      queue: {
        title: 'Topic queue',
        hint: 'Weakest first — start from the top',
        empty: 'Comfort zone: nothing needs revision right now',
        attempts: '{n} attempts',
        lastScore: 'Last score: {score}%',
        noScore: 'No attempts yet',
        retake: 'Retake quiz',
        cards: 'Its cards',
      },
      cards: {
        title: 'Card review session',
        hint: 'Flip the card, then rate yourself honestly — the rating is saved on the server.',
        progress: 'Card {n} of {total}',
        front: 'Question',
        back: 'Answer',
        flip: 'Flip card',
        skip: 'Skip',
        ratings: {
          again: 'Again',
          hard: 'Hard',
          good: 'Good',
          easy: 'Easy',
        },
        filters: {
          label: 'Topic',
          all: 'All topics',
          includeHigh: 'Include known cards',
        },
        tones: {
          low: 'Low confidence',
          medium: 'Medium confidence',
          high: 'High confidence',
        },
        empty: 'No cards to review right now',
        emptyHint: 'Publish a lecture to generate fresh cards.',
        emptyFiltered: 'No cards in this topic',
        emptyFilteredHint: 'Try “All topics”.',
        done: {
          title: 'Review session complete',
          desc: 'You reviewed {reviewed} cards — {improved} moved up a level.',
          descSkipped: 'You closed the session without rating — rating is what makes it stick.',
          restart: 'New session',
          quiz: 'Quiz my weakest topic',
        },
      },
      recent: {
        title: 'Recent attempts',
        hint: 'Retake any attempt straight from here',
        empty: 'No quiz attempts yet',
        retake: 'Retake',
        attempts: 'questions',
      },
      empty: 'No published content yet',
      emptyHint: 'Upload a lecture and publish it from the course library, then start revising.',
      goLibrary: 'Course library',
      offline: 'Cannot reach the server — make sure the backend runs on 127.0.0.1:8000',
      retry: 'Retry',
      sessionError: 'Could not save the rating — please try again.',
    },
    lessons: {
      title: 'Lesson Viewer',
      subtitle: 'Full published lessons: objectives, explanation, formulas, glossary and summary',
      search: 'Search topics…',
      topics: 'Topics',
      noLessons: 'not published',
      empty: 'No published lessons yet',
      emptyHint:
        'Upload a lecture and publish it from the course library to generate one lesson per topic.',
      goLibrary: 'Course library',
      offline: 'Cannot reach the server — make sure the backend runs on 127.0.0.1:8000',
      retry: 'Retry',
      refresh: 'Refresh',
      noLesson: 'This topic has no published lesson yet',
      noLessonHint: 'Try another topic, or publish a new lecture to generate it.',
      noMatch: 'No topic matches that name',
      pick: 'Pick a topic from the list to read its lesson.',
      loadingLesson: 'Loading lesson…',
      lessonError: 'Could not load the lesson — please try again.',
      blocks: {
        objectives: 'Lesson objectives',
        prerequisites: 'Prerequisites',
        content: 'Lesson body',
        formulas: 'Formulas',
        terminology: 'Terminology',
        comparisons: 'Comparisons',
        summary: 'Summary',
      },
      terminologyTable: {
        term: 'Term (EN)',
        arabic: 'Arabic',
        definition: 'Definition',
      },
      comparisonTable: {
        pair: 'Comparison',
        aspect: 'Aspect',
        detail: 'Detail',
      },
      formulaNote: 'When to use it',
      chars: '{n} chars',
      actions: {
        quiz: 'Quiz this lesson',
        prev: 'Previous',
        next: 'Next',
      },
    },
    placeholder: {
      tutor: {
        title: 'AI Tutor',
        desc:
          'The chat interface for the RAG tutor, grounded in published content with' +
          ' citation verification, ships in the next UI phase.',
      },
      quiz: {
        title: 'Quiz & Exam Simulator',
        desc:
          'The exam simulator: quick quizzes plus exam mode (no answer key leaked),' +
          ' instant grading and per-topic breakdowns — next UI phase.',
      },
      flashcards: {
        title: 'Flashcards',
        desc:
          'The review interface with four-way confidence ratings' +
          ' (again / hard / good / easy), topic filters and confidence stats — next UI phase.',
      },
      poweredBy: 'Backend endpoints already live and waiting for this view:',
      eta: 'Next development phase',
      back: 'Back to the dashboard',
    },
  },
}

const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    if (typeof window === 'undefined') return 'ar'
    try {
      return window.localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'ar'
    } catch {
      return 'ar'
    }
  })

  const dir = DIRS[lang]

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = dir
    document.title = STRINGS[lang].app.title
  }, [lang, dir])

  const value = useMemo(() => {
    const setLang = (next) => {
      try {
        window.localStorage.setItem(STORAGE_KEY, next)
      } catch {
        /* storage may be unavailable (private mode) — still switch */
      }
      setLangState(next)
    }
    return {
      lang,
      dir,
      isRTL: dir === 'rtl',
      setLang,
      toggle: () => setLang(lang === 'ar' ? 'en' : 'ar'),
      t: STRINGS[lang],
    }
  }, [lang, dir])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  const context = useContext(LanguageContext)
  if (!context) throw new Error('useLanguage must be used inside <LanguageProvider>')
  return context
}
