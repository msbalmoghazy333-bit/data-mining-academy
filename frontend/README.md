# Data Mining Academy — Frontend

واجهة React 19 + Vite 8 + Tailwind v4 لتطبيق **Data Mining Academy** (بطريقة عربية RTL مع تبديل إنجليزي LTR).

الدليل الكامل (النظرة العامة، المعمارية، الـ API، طرق التشغيل) موجود في
[`../README.md`](../README.md).

## التشغيل السريع

```powershell
npm install

npm run dev      # سيرفر التطوير على http://localhost:5173 (بروكسي /api إلى 127.0.0.1:8000)
npm run build    # بناء نسخة الإنتاج في dist/
npm run preview  # معاينة نسخة الإنتاج محليًا
npm run lint     # فحص الكود بـ oxlint
```

> لازم يكون الـ backend شغال على المنفذ `8000` علشان نداءات `/api` تشتغل
> (شوف قسم «التشغيل» في الدليل الرئيسي).

## المسارات

| المسار | الشاشة |
| --- | --- |
| `/` | لوحة التحكم |
| `/library` | مكتبة المنهج والرفع |
| `/tutor` | المعلم الذكي (RAG) |
| `/quiz` | بنك الأسئلة ومُحاكي الامتحان |
| `/revision` | مركز المراجعة |
| `/lessons` | عارض الدروس |
| `/flashcards` | بطاقات التذكر |
