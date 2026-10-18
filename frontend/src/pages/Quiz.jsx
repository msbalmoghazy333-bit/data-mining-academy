/**
 * Quiz & exam simulator.
 *
 * Wraps two stateless backend endpoints:
 *   POST /api/v1/quizzes/generate  -> a random draw (exam mode hides the key)
 *   POST /api/v1/quizzes/submit    -> deterministic grading + mastery update
 *
 * The screen has three phases:
 *   setup   -> topic / difficulty / count / mode configuration
 *   active  -> one question at a time, with a question map and (exam mode) a timer
 *   results -> score, per-topic breakdown, mastery before/after, full review
 *
 * The answer key is only ever exposed in practice mode; exam mode reveals
 * everything after submission, exactly like the endpoint contract.
 *
 * Deep links (used by the Revision Center):
 *   /quiz?topic=<id>          -> pre-select one topic
 *   /quiz?topic=<id>&start=1  -> pre-select and start immediately
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Award,
  CheckCircle2,
  CircleHelp,
  Eye,
  EyeOff,
  Flag,
  Languages,
  LayoutGrid,
  ListChecks,
  Play,
  RotateCcw,
  Send,
  Target,
  Timer,
  TriangleAlert,
  XCircle,
} from 'lucide-react'

import api from '../lib/api.js'
import { useLanguage } from '../lib/i18n.jsx'
import { fill } from '../lib/format.js'
import { refreshSummary } from '../lib/summaryStore.js'
import { Badge, buttonClasses, Card, Modal, ProgressBar, Spinner } from '../components/ui.jsx'

const GENERATE_URL = '/v1/quizzes/generate'
const SUBMIT_URL = '/v1/quizzes/submit'
const TOPICS_URL = '/v1/topics'
const TRANSLATE_URL = '/v1/translate'

const DIFFICULTIES = ['easy', 'medium', 'hard', 'mixed']
const COUNT_CHOICES = [5, 10, 15, 20, 25, 30]
const MODES = ['practice', 'exam']
const LETTERS = ['أ', 'ب', 'ج', 'د', 'ه', 'و']
const SECONDS_PER_QUESTION = 60 // exam-mode budget per question

const DIFFICULTY_TONES = { easy: 'emerald', medium: 'amber', hard: 'rose', mixed: 'teal' }
const TYPE_TONES = { mcq: 'teal', true_false: 'slate', short_answer: 'amber' }

const DEFAULT_CONFIG = { difficulty: 'mixed', count: 10, mode: 'practice', topicIds: [] }

/* ------------------------------------------------------------------ */
/* Small presentational pieces                                         */
/* ------------------------------------------------------------------ */

function ScoreRing({ value, tone = 'text-teal-600' }) {
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const clamped = Math.min(100, Math.max(0, value))
  const offset = circumference * (1 - clamped / 100)

  return (
    <svg viewBox="0 0 100 100" className="h-32 w-32 -rotate-90">
      <circle cx="50" cy="50" r={radius} className="fill-none stroke-slate-100" strokeWidth="10" />
      <circle
        cx="50"
        cy="50"
        r={radius}
        className={`fill-none ${tone}`}
        stroke="currentColor"
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
      />
    </svg>
  )
}

function timeText(totalSeconds) {
  const safe = Math.max(0, totalSeconds)
  const minutes = Math.floor(safe / 60)
  const seconds = safe % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function SegmentedControl({ options, value, onChange }) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={[
            'rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors',
            value === option.value
              ? 'bg-white text-teal-700 shadow-sm'
              : 'text-slate-500 hover:text-slate-800',
          ].join(' ')}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

/** Pick the localised topic title (Arabic when available). */
function topicTitle(topic, lang) {
  if (!topic) return null
  return lang === 'ar' && topic.title_ar ? topic.title_ar : topic.title_en
}

/* ------------------------------------------------------------------ */
/* Per-question Arabic translation (on demand)                         */
/* ------------------------------------------------------------------ */

function translateError(error, t) {
  const status = error?.status ?? 0
  if (status === 0) return t.quiz.translate.errors.offline
  if (status === 409) return t.quiz.translate.errors.noKey
  return t.quiz.translate.errors.unavailable
}

/**
 * Questions are stored in English (the exam language). This hook adds the
 * optional Arabic rendering for the small per-question toggle: the first click
 * on a question calls `POST /v1/translate` (text + options) and caches the
 * result; later clicks just flip between the two languages.
 *
 * The answer value always stays the canonical English option, so grading is
 * unaffected by which language is on screen.
 */
function useQuestionTranslation(t) {
  const [cache, setCache] = useState({})
  const [showAr, setShowAr] = useState({})
  const [busy, setBusy] = useState({})
  const [error, setError] = useState(null)

  const toggle = async (question) => {
    const id = question.id

    if (cache[id]) {
      setShowAr((previous) => ({ ...previous, [id]: !previous[id] }))
      return
    }

    setBusy((previous) => ({ ...previous, [id]: true }))
    setError(null)
    try {
      const texts = [question.question_text, ...(question.options ?? [])]
      const response = await api.post(TRANSLATE_URL, { texts, target: 'ar' })
      const [text, ...options] = response.translations ?? []
      setCache((previous) => ({ ...previous, [id]: { text, options } }))
      setShowAr((previous) => ({ ...previous, [id]: true }))
    } catch (err) {
      setError(translateError(err, t))
    } finally {
      setBusy((previous) => ({ ...previous, [id]: false }))
    }
  }

  return { cache, showAr, busy, error, dismiss: () => setError(null), toggle }
}

/** Small «show in Arabic / show in English» pill used next to a question. */
function TranslationToggle({ question, translation, t, className = '' }) {
  const cached = translation.cache[question.id]
  const isArabic = Boolean(cached) && translation.showAr[question.id]
  const loading = Boolean(translation.busy[question.id])

  return (
    <button
      type="button"
      onClick={() => translation.toggle(question)}
      disabled={loading}
      title={isArabic ? t.quiz.translate.showEn : t.quiz.translate.showAr}
      className={`flex shrink-0 items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-teal-700 disabled:opacity-60 ${className}`}
    >
      {loading ? (
        <Spinner className="h-3.5 w-3.5" />
      ) : (
        <Languages className="h-3.5 w-3.5 text-teal-600" aria-hidden="true" />
      )}
      {loading
        ? t.quiz.translate.translating
        : isArabic
          ? t.quiz.translate.showEn
          : t.quiz.translate.showAr}
    </button>
  )
}

/** Localised question text + option labels for a question (English default). */
function questionView(question, translation) {
  const cached = translation.cache[question.id]
  const isArabic = Boolean(cached) && translation.showAr[question.id]
  return {
    isArabic,
    text: isArabic ? cached.text : question.question_text,
    views: (question.options ?? []).map((option, index) => ({
      // The value stays canonical (English) so grading never breaks.
      value: option,
      label: isArabic && cached.options?.[index] ? cached.options[index] : option,
    })),
  }
}

/* ------------------------------------------------------------------ */
/* Setup                                                               */
/* ------------------------------------------------------------------ */

function SetupPanel({ config, setConfig, topics, topicsLoading, bankTotal, onStart, starting, t, lang }) {
  const toggleTopic = (id) => {
    setConfig((previous) => ({
      ...previous,
      topicIds: previous.topicIds.includes(id)
        ? previous.topicIds.filter((item) => item !== id)
        : [...previous.topicIds, id],
    }))
  }

  return (
    <div className="space-y-5">
      <Card title={t.quiz.setup.title} icon={ListChecks}>
        <p className="mb-5 text-sm text-slate-500">{t.quiz.setup.subtitle}</p>

        <div className="space-y-5">
          {/* mode */}
          <div>
            <p className="mb-2 text-xs font-semibold text-slate-500">{t.quiz.setup.mode}</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {MODES.map((modeKey) => {
                const active = config.mode === modeKey
                return (
                  <button
                    key={modeKey}
                    type="button"
                    onClick={() => setConfig((previous) => ({ ...previous, mode: modeKey }))}
                    className={[
                      'rounded-xl border p-3 text-start transition-colors',
                      active
                        ? 'border-teal-300 bg-teal-50 ring-1 ring-teal-200'
                        : 'border-slate-200 bg-white hover:bg-slate-50',
                    ].join(' ')}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-bold text-slate-800">{t.quiz.setup.modes[modeKey].title}</span>
                      <span
                        className={[
                          'h-3.5 w-3.5 rounded-full border-2',
                          active ? 'border-teal-600 bg-teal-600' : 'border-slate-300',
                        ].join(' ')}
                        aria-hidden="true"
                      />
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-slate-500">
                      {t.quiz.setup.modes[modeKey].desc}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* difficulty */}
          <div>
            <p className="mb-2 text-xs font-semibold text-slate-500">{t.quiz.setup.difficulty}</p>
            <SegmentedControl
              value={config.difficulty}
              onChange={(value) => setConfig((previous) => ({ ...previous, difficulty: value }))}
              options={DIFFICULTIES.map((key) => ({ value: key, label: t.quiz.setup.difficulties[key] }))}
            />
          </div>

          {/* count */}
          <div>
            <p className="mb-2 text-xs font-semibold text-slate-500">{t.quiz.setup.count}</p>
            <div className="flex flex-wrap gap-1.5">
              {COUNT_CHOICES.map((count) => (
                <button
                  key={count}
                  type="button"
                  onClick={() => setConfig((previous) => ({ ...previous, count }))}
                  className={[
                    'h-9 min-w-9 rounded-xl px-2.5 text-sm font-bold tabular-nums transition-colors',
                    config.count === count
                      ? 'bg-teal-600 text-white shadow-sm'
                      : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {count}
                </button>
              ))}
            </div>
          </div>

          {/* topics */}
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold text-slate-500">{t.quiz.setup.topics}</p>
              {topics.length > 0 && (
                <div className="flex items-center gap-2 text-[11px] font-semibold text-teal-700">
                  <button
                    type="button"
                    onClick={() =>
                      setConfig((previous) => ({ ...previous, topicIds: topics.map((topic) => topic.id) }))
                    }
                    className="hover:underline"
                  >
                    {t.quiz.setup.selectAll}
                  </button>
                  <span className="text-slate-300" aria-hidden="true">
                    ·
                  </span>
                  <button
                    type="button"
                    onClick={() => setConfig((previous) => ({ ...previous, topicIds: [] }))}
                    className="hover:underline"
                  >
                    {t.quiz.setup.clearSel}
                  </button>
                </div>
              )}
            </div>

            {topicsLoading ? (
              <div className="flex items-center gap-2 py-2 text-sm text-slate-500">
                <Spinner className="h-4 w-4" />
                {t.quiz.setup.topicsLoading}
              </div>
            ) : topics.length === 0 ? (
              <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700 ring-1 ring-amber-200">
                {t.quiz.setup.noTopics}
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setConfig((previous) => ({ ...previous, topicIds: [] }))}
                  className={[
                    'rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
                    config.topicIds.length === 0
                      ? 'border-teal-300 bg-teal-50 text-teal-700'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {t.quiz.setup.allTopics}
                </button>
                {topics.map((topic) => {
                  const active = config.topicIds.includes(topic.id)
                  return (
                    <button
                      key={topic.id}
                      type="button"
                      onClick={() => toggleTopic(topic.id)}
                      className={[
                        'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
                        active
                          ? 'border-teal-300 bg-teal-50 text-teal-700'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                      ].join(' ')}
                    >
                      <span className="max-w-[12rem] truncate" dir="auto">
                        {topicTitle(topic, lang)}
                      </span>
                      <span className="tabular-nums text-slate-400">
                        {fill(t.quiz.setup.questionCount, { n: topic.questions })}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          <Target className="h-4 w-4 text-teal-600" aria-hidden="true" />
          {fill(t.quiz.setup.availableNote, { n: bankTotal })}
        </span>
        <button type="button" onClick={onStart} disabled={starting} className={buttonClasses({ size: 'lg' })}>
          {starting ? (
            <Spinner className="h-4 w-4 text-white" />
          ) : (
            <Play className="h-4 w-4" aria-hidden="true" />
          )}
          {starting ? t.quiz.setup.starting : t.quiz.setup.start}
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Active                                                              */
/* ------------------------------------------------------------------ */

function AnswerInput({ question, value, onChange, views, t }) {
  if (question.type === 'short_answer') {
    return (
      <textarea
        rows={4}
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value.slice(0, 8000))}
        placeholder={t.quiz.active.shortAnswerPlaceholder}
        dir="auto"
        className="w-full resize-y rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500"
      />
    )
  }

  // `views` holds {value, label}: the value is always the canonical (English)
  // option used for grading, while the label may be the Arabic translation.
  const options = views?.length
    ? views
    : (question.options ?? []).map((option) => ({ value: option, label: option }))
  const hint = question.type === 'true_false' ? t.quiz.active.tfHint : t.quiz.active.mcqHint

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-400">{hint}</p>
      {options.map((option, index) => {
        const selected = value === option.value
        return (
          <button
            key={`${index}-${option.value}`}
            type="button"
            onClick={() => onChange(option.value)}
            className={[
              'flex w-full items-center gap-3 rounded-xl border px-3.5 py-3 text-start transition-colors',
              selected
                ? 'border-teal-300 bg-teal-50 ring-1 ring-teal-200'
                : 'border-slate-200 bg-white hover:bg-slate-50',
            ].join(' ')}
          >
            <span
              className={[
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold',
                selected ? 'bg-teal-600 text-white' : 'bg-slate-100 text-slate-500',
              ].join(' ')}
            >
              {question.type === 'true_false' ? (index === 0 ? '✓' : '✕') : LETTERS[index]}
            </span>
            <span className="text-sm text-slate-700" dir="auto">
              {option.label}
            </span>
          </button>
        )
      })}
    </div>
  )
}

function RevealBox({ question, t }) {
  return (
    <div className="mt-4 space-y-3 rounded-xl border border-teal-100 bg-teal-50/60 p-3.5">
      <div>
        <p className="text-[11px] font-semibold uppercase text-teal-700">{t.quiz.active.answerKey}</p>
        <p className="mt-0.5 text-sm font-semibold text-slate-800" dir="auto">
          {question.correct_answer}
        </p>
      </div>
      {question.explanation && (
        <div>
          <p className="text-[11px] font-semibold uppercase text-teal-700">
            {t.quiz.active.explanation}
          </p>
          <p className="mt-0.5 text-sm leading-relaxed text-slate-700" dir="auto">
            {question.explanation}
          </p>
        </div>
      )}
      {question.source_reference && (
        <p className="text-[11px] text-slate-500">
          {t.quiz.active.source}:{' '}
          <span className="ltr font-medium text-slate-600">{question.source_reference}</span>
        </p>
      )}
    </div>
  )
}

function ActivePanel({
  quiz,
  config,
  topicMap,
  t,
  lang,
  isRTL,
  translation,
  onSubmit,
  submitting,
  onExit,
  remaining,
  elapsed,
}) {
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState({})
  const [flags, setFlags] = useState(() => new Set())
  const [revealed, setRevealed] = useState(() => new Set())
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [exitOpen, setExitOpen] = useState(false)

  const questions = quiz.questions
  const question = questions[current]
  const view = questionView(question, translation)
  const answeredCount = questions.filter((item) => (answers[item.id] ?? '').trim() !== '').length
  const unanswered = questions.length - answeredCount

  const PrevIcon = isRTL ? ArrowRight : ArrowLeft
  const NextIcon = isRTL ? ArrowLeft : ArrowRight

  const setAnswer = (value) => setAnswers((previous) => ({ ...previous, [question.id]: value }))

  const toggleFlag = () =>
    setFlags((previous) => {
      const next = new Set(previous)
      if (next.has(question.id)) next.delete(question.id)
      else next.add(question.id)
      return next
    })

  const toggleReveal = () =>
    setRevealed((previous) => {
      const next = new Set(previous)
      if (next.has(question.id)) next.delete(question.id)
      else next.add(question.id)
      return next
    })

  const canReveal = config.mode === 'practice' && Boolean(question.correct_answer)

  const requestSubmit = () => {
    if (unanswered > 0) setConfirmOpen(true)
    else onSubmit(answers)
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_16rem]">
      {/* ---- question column ---- */}
      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-bold text-slate-800">
              {fill(t.quiz.active.questionOf, { n: current + 1, total: questions.length })}
            </p>
            <div className="flex items-center gap-3">
              {remaining !== null ? (
                <span
                  className={[
                    'flex items-center gap-1 text-sm font-bold tabular-nums',
                    remaining <= 30 ? 'text-rose-600' : 'text-slate-600',
                  ].join(' ')}
                  dir="ltr"
                >
                  <Timer className="h-4 w-4" aria-hidden="true" />
                  {timeText(remaining)}
                  <span className="ms-1 text-[11px] font-medium text-slate-400">
                    {t.quiz.active.timeLeft}
                  </span>
                </span>
              ) : (
                <span className="flex items-center gap-1 text-sm font-bold tabular-nums text-slate-500" dir="ltr">
                  <Timer className="h-4 w-4" aria-hidden="true" />
                  {timeText(elapsed)}
                  <span className="ms-1 text-[11px] font-medium text-slate-400">
                    {t.quiz.active.elapsed}
                  </span>
                </span>
              )}
              <span className="text-xs text-slate-500">
                {fill(t.quiz.active.answered, { n: answeredCount })}
              </span>
            </div>
          </div>
          <ProgressBar className="mt-3" value={(answeredCount / questions.length) * 100} />
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge tone={TYPE_TONES[question.type] ?? 'slate'}>{t.quiz.types[question.type]}</Badge>
            <Badge tone={DIFFICULTY_TONES[question.difficulty] ?? 'slate'}>
              {t.quiz.setup.difficulties[question.difficulty] ?? question.difficulty}
            </Badge>
            {topicTitle(topicMap.get(question.topic_id), lang) && (
              <span className="text-xs text-slate-400">
                {topicTitle(topicMap.get(question.topic_id), lang)}
              </span>
            )}
            <button
              type="button"
              onClick={toggleFlag}
              className={[
                'ms-auto flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors',
                flags.has(question.id)
                  ? 'bg-amber-100 text-amber-700'
                  : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600',
              ].join(' ')}
            >
              <Flag className="h-3.5 w-3.5" aria-hidden="true" />
              {flags.has(question.id) ? t.quiz.active.flagged : t.quiz.active.flag}
            </button>
          </div>

          <div className="mb-4 flex items-start justify-between gap-3">
            <p className="text-base font-semibold leading-relaxed text-slate-800" dir="auto">
              {view.text}
            </p>
            <TranslationToggle question={question} translation={translation} t={t} />
          </div>

          <AnswerInput
            question={question}
            value={answers[question.id]}
            onChange={setAnswer}
            views={view.views}
            t={t}
          />

          {canReveal && (
            <button
              type="button"
              onClick={toggleReveal}
              className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-teal-700 hover:underline"
            >
              {revealed.has(question.id) ? (
                <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <Eye className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              {revealed.has(question.id) ? t.quiz.active.hide : t.quiz.active.reveal}
            </button>
          )}

          {canReveal && revealed.has(question.id) && <RevealBox question={question} t={t} />}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setCurrent((index) => Math.max(0, index - 1))}
            disabled={current === 0}
            className={buttonClasses({ variant: 'secondary' })}
          >
            <PrevIcon className="h-4 w-4" aria-hidden="true" />
            {t.quiz.active.prev}
          </button>

          {current < questions.length - 1 ? (
            <button
              type="button"
              onClick={() => setCurrent((index) => Math.min(questions.length - 1, index + 1))}
              className={buttonClasses({ variant: 'secondary' })}
            >
              {t.quiz.active.next}
              <NextIcon className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : (
            <button type="button" onClick={requestSubmit} disabled={submitting} className={buttonClasses()}>
              {submitting ? <Spinner className="h-4 w-4 text-white" /> : <Send className="h-4 w-4" aria-hidden="true" />}
              {submitting ? t.quiz.active.submitting : t.quiz.active.submit}
            </button>
          )}
        </div>
      </div>

      {/* ---- side column: map + submit ---- */}
      <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-slate-500">
            <LayoutGrid className="h-3.5 w-3.5 text-teal-600" aria-hidden="true" />
            {t.quiz.active.navigation}
          </p>
          <div className="grid grid-cols-6 gap-1.5 lg:grid-cols-5" dir="ltr">
            {questions.map((item, index) => {
              const isCurrent = index === current
              const isAnswered = (answers[item.id] ?? '').trim() !== ''
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setCurrent(index)}
                  className={[
                    'relative flex h-8 items-center justify-center rounded-lg text-xs font-bold tabular-nums transition-colors',
                    isCurrent
                      ? 'bg-teal-600 text-white shadow-sm'
                      : isAnswered
                        ? 'bg-teal-50 text-teal-700 ring-1 ring-teal-200'
                        : 'bg-slate-100 text-slate-500 hover:bg-slate-200',
                  ].join(' ')}
                >
                  {index + 1}
                  {flags.has(item.id) && (
                    <span className="absolute -end-0.5 -top-0.5 h-2 w-2 rounded-full bg-amber-400" aria-hidden="true" />
                  )}
                </button>
              )
            })}
          </div>

          <p className="mt-4 text-xs">
            {unanswered === 0 ? (
              <span className="flex items-center gap-1.5 font-semibold text-emerald-600">
                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                {t.quiz.active.answeredAll}
              </span>
            ) : (
              <span className="flex items-center gap-1.5 font-semibold text-amber-600">
                <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
                {fill(t.quiz.active.unansweredNote, { n: unanswered })}
              </span>
            )}
          </p>

          <button
            type="button"
            onClick={requestSubmit}
            disabled={submitting}
            className={`${buttonClasses()} mt-4 w-full`}
          >
            {submitting ? <Spinner className="h-4 w-4 text-white" /> : <Send className="h-4 w-4" aria-hidden="true" />}
            {submitting ? t.quiz.active.submitting : t.quiz.active.submit}
          </button>

          <button
            type="button"
            onClick={() => setExitOpen(true)}
            className="mt-2 w-full text-center text-xs font-semibold text-slate-400 hover:text-rose-600"
          >
            {t.quiz.active.exit}
          </button>
        </div>
      </aside>

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={t.quiz.active.submit}
        footer={
          <>
            <button
              type="button"
              onClick={() => setConfirmOpen(false)}
              className={buttonClasses({ variant: 'secondary' })}
            >
              {t.common.cancel}
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirmOpen(false)
                onSubmit(answers)
              }}
              className={buttonClasses()}
            >
              {t.quiz.active.confirmSubmitOk}
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-600">{fill(t.quiz.active.confirmSubmit, { n: unanswered })}</p>
      </Modal>

      <Modal
        open={exitOpen}
        onClose={() => setExitOpen(false)}
        title={t.quiz.active.exit}
        footer={
          <>
            <button
              type="button"
              onClick={() => setExitOpen(false)}
              className={buttonClasses({ variant: 'secondary' })}
            >
              {t.common.cancel}
            </button>
            <button
              type="button"
              onClick={() => {
                setExitOpen(false)
                onExit()
              }}
              className={buttonClasses({ variant: 'danger' })}
            >
              {t.quiz.active.exit}
            </button>
          </>
        }
      >
        <p className="text-sm text-slate-600">{t.quiz.active.confirmExit}</p>
      </Modal>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Results                                                             */
/* ------------------------------------------------------------------ */

function MasteryBadge({ status, t }) {
  const tones = {
    mastered: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    needs_revision: 'bg-rose-50 text-rose-700 ring-rose-200',
    learning: 'bg-teal-50 text-teal-700 ring-teal-200',
    not_started: 'bg-slate-100 text-slate-600 ring-slate-200',
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${
        tones[status] ?? tones.not_started
      }`}
    >
      {t.quiz.results.mastery[status] ?? status}
    </span>
  )
}

function ResultsPanel({ result, quiz, t, lang, translation, onRetry, onNewQuiz, retrying }) {
  const byId = useMemo(() => {
    const map = new Map()
    for (const question of quiz.questions) map.set(question.id, question)
    return map
  }, [quiz])

  const passed = result.score >= 50
  const tone = result.score >= 80 ? 'text-emerald-500' : passed ? 'text-teal-600' : 'text-rose-500'

  return (
    <div className="space-y-5">
      <div className="flex flex-col items-center gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:flex-row sm:justify-between">
        <div className="flex items-center gap-5">
          <div className="relative flex items-center justify-center">
            <ScoreRing value={result.score} tone={tone} />
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-extrabold tabular-nums text-slate-800">{result.score}%</span>
              <span className="text-[11px] text-slate-400">{t.quiz.results.score}</span>
            </div>
          </div>
          <div className="space-y-1.5">
            <h2 className="text-xl font-extrabold text-slate-900">{t.quiz.results.title}</h2>
            <p className="text-sm text-slate-500">
              {fill(t.quiz.results.of, { correct: result.correct_count, total: result.total_questions })}
            </p>
            <Badge tone={passed ? 'emerald' : 'rose'}>
              {passed ? <Award className="h-3.5 w-3.5" /> : <CircleHelp className="h-3.5 w-3.5" />}
              {passed ? t.quiz.results.correct : t.quiz.results.wrong}
            </Badge>
          </div>
        </div>
        <button type="button" onClick={onRetry} disabled={retrying} className={buttonClasses()}>
          {retrying ? <Spinner className="h-4 w-4 text-white" /> : <RotateCcw className="h-4 w-4" aria-hidden="true" />}
          {t.quiz.results.retry}
        </button>
      </div>

      {result.not_found?.length > 0 && (
        <p className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {fill(t.quiz.results.notFound, { ids: result.not_found.join(', ') })}
        </p>
      )}

      <Card title={t.quiz.results.breakdown} icon={Target}>
        <div className="space-y-4">
          {result.topics.map((topic) => {
            const label = topicTitle(topic, lang)
            const changed = topic.previous_mastery !== topic.updated_mastery
            return (
              <div key={topic.topic_id}>
                <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-700" dir="auto">
                    {label}
                  </span>
                  <span className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="tabular-nums">
                      {topic.correct}/{topic.total}
                    </span>
                    <MasteryBadge status={topic.previous_mastery} t={t} />
                    {changed && (
                      <>
                        {lang === 'ar' ? (
                          <ArrowLeft className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                        ) : (
                          <ArrowRight className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                        )}
                        <MasteryBadge status={topic.updated_mastery} t={t} />
                      </>
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <ProgressBar
                    value={topic.score}
                    tone={topic.score >= 80 ? 'emerald' : topic.score >= 50 ? 'teal' : 'rose'}
                  />
                  <span className="w-10 shrink-0 text-end text-xs font-bold tabular-nums text-slate-600">
                    {topic.score}%
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <Card title={t.quiz.results.review} icon={ListChecks}>
        <div className="space-y-3">
          {result.questions.map((item, index) => {
            const source = byId.get(item.question_id)
            const correct = item.is_correct
            const partial = !correct && item.earned > 0
            const isArabic = Boolean(source) && translation.showAr[source.id]
            const questionText = source
              ? isArabic
                ? translation.cache[source.id].text
                : source.question_text
              : `#${item.question_id}`
            return (
              <div key={item.question_id} className="rounded-xl border border-slate-200 p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="flex-1 text-sm font-semibold text-slate-800" dir="auto">
                    <span className="me-1.5 tabular-nums text-slate-400">{index + 1}.</span>
                    {questionText}
                  </p>
                  <div className="flex items-center gap-2">
                    <Badge tone={correct ? 'emerald' : partial ? 'amber' : 'rose'}>
                      {correct ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                      {correct
                        ? t.quiz.results.correct
                        : partial
                          ? fill(t.quiz.results.partial, { n: item.earned })
                          : t.quiz.results.wrong}
                    </Badge>
                    {source && (
                      <TranslationToggle
                        question={source}
                        translation={translation}
                        t={t}
                        className="!px-2 !py-0.5 !text-[10px]"
                      />
                    )}
                  </div>
                </div>

                <dl className="mt-2.5 space-y-1.5 text-sm">
                  <div className="flex gap-2">
                    <dt className="w-24 shrink-0 text-xs font-semibold text-slate-400">
                      {t.quiz.results.yourAnswer}
                    </dt>
                    <dd
                      className={[
                        'min-w-0 flex-1',
                        item.your_answer ? 'text-slate-700' : 'italic text-slate-400',
                      ].join(' ')}
                      dir="auto"
                    >
                      {item.your_answer || t.quiz.results.notAnswered}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-24 shrink-0 text-xs font-semibold text-slate-400">
                      {t.quiz.results.correctAnswer}
                    </dt>
                    <dd className="min-w-0 flex-1 font-medium text-emerald-700" dir="auto">
                      {item.expected}
                    </dd>
                  </div>
                  {item.explanation && (
                    <div className="flex gap-2">
                      <dt className="w-24 shrink-0 text-xs font-semibold text-slate-400">
                        {t.quiz.active.explanation}
                      </dt>
                      <dd className="min-w-0 flex-1 leading-relaxed text-slate-600" dir="auto">
                        {item.explanation}
                      </dd>
                    </div>
                  )}
                </dl>

                {item.source_reference && (
                  <p className="mt-2 text-[11px] text-slate-400">
                    {t.quiz.active.source}:{' '}
                    <span className="ltr font-medium text-slate-500">{item.source_reference}</span>
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </Card>

      <div className="flex justify-center">
        <button
          type="button"
          onClick={onNewQuiz}
          disabled={retrying}
          className={buttonClasses({ variant: 'secondary' })}
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          {t.quiz.results.newQuiz}
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Quiz() {
  const { t, lang, isRTL } = useLanguage()
  const translation = useQuestionTranslation(t)

  const [searchParams] = useSearchParams()

  // Deep link `/quiz?topic=<id>` — pre-select the topic (Revision Center).
  const linkedTopicId = useMemo(() => {
    const id = Number(searchParams.get('topic'))
    return Number.isInteger(id) && id > 0 ? id : null
  }, [searchParams])

  const [phase, setPhase] = useState('setup')
  const [config, setConfig] = useState(() =>
    linkedTopicId == null ? DEFAULT_CONFIG : { ...DEFAULT_CONFIG, topicIds: [linkedTopicId] },
  )
  const [topics, setTopics] = useState([])
  const [topicsLoading, setTopicsLoading] = useState(true)
  const [quiz, setQuiz] = useState(null)
  const [result, setResult] = useState(null)
  const [starting, setStarting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [now, setNow] = useState(() => Date.now())
  const [startedAt, setStartedAt] = useState(0)
  const autoSubmittedRef = useRef(false)
  const stateRef = useRef({})
  const submitRef = useRef(null)

  const topicMap = useMemo(() => {
    const map = new Map()
    for (const topic of topics) map.set(topic.id, topic)
    return map
  }, [topics])

  const bankTotal = useMemo(() => topics.reduce((sum, topic) => sum + topic.questions, 0), [topics])

  const duration = config.count * SECONDS_PER_QUESTION
  const elapsed = startedAt ? Math.floor((now - startedAt) / 1000) : 0
  const remaining = phase === 'active' && config.mode === 'exam' ? Math.max(0, duration - elapsed) : null

  // ---- topics catalogue (once) ----
  useEffect(() => {
    let cancelled = false
    api
      .get(TOPICS_URL)
      .then((data) => {
        if (!cancelled) setTopics(data.items ?? [])
      })
      .catch(() => {
        if (!cancelled) setTopics([])
      })
      .finally(() => {
        if (!cancelled) setTopicsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const startQuiz = useCallback(async () => {
    setStarting(true)
    setError(null)
    try {
      const response = await api.post(GENERATE_URL, {
        topic_ids: config.topicIds.length > 0 ? config.topicIds : null,
        difficulty: config.difficulty,
        count: config.count,
        mode: config.mode,
      })

      if (!response.questions?.length) {
        setError(t.quiz.empty.desc)
        return
      }

      const started = Date.now()
      setStartedAt(started)
      autoSubmittedRef.current = false
      setNow(started)
      setQuiz(response)
      setResult(null)
      setPhase('active')
    } catch (err) {
      setError(err?.status ? t.quiz.errors.generate : t.quiz.errors.offline)
    } finally {
      setStarting(false)
    }
  }, [config, t])

  // `/quiz?topic=<id>&start=1` runs the quiz straight away — exactly once.
  const autoStartedRef = useRef(false)
  useEffect(() => {
    if (searchParams.get('start') !== '1' || autoStartedRef.current) return
    autoStartedRef.current = true
    startQuiz()
  }, [searchParams, startQuiz])

  const submit = async (answers) => {
    if (!quiz || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const payload = {
        answers: quiz.questions.map((question) => ({
          question_id: question.id,
          answer: (answers?.[question.id] ?? '').slice(0, 8000),
        })),
      }
      const response = await api.post(SUBMIT_URL, payload)
      setResult(response)
      setPhase('results')
      refreshSummary()
    } catch (err) {
      setError(err?.status ? t.quiz.errors.submit : t.quiz.errors.offline)
    } finally {
      setSubmitting(false)
    }
  }

  // ---- keep latest values for the interval callback ----
  useEffect(() => {
    stateRef.current = { phase, mode: config.mode, remaining, submitting }
    submitRef.current = submit
  })

  // ---- exam countdown / practice stopwatch ----
  useEffect(() => {
    if (phase !== 'active') return undefined
    const id = setInterval(() => {
      setNow(Date.now())
      const snapshot = stateRef.current
      if (snapshot.mode === 'exam' && snapshot.remaining <= 0 && !snapshot.submitting && !autoSubmittedRef.current) {
        autoSubmittedRef.current = true
        submitRef.current?.()
      }
    }, 1000)
    return () => clearInterval(id)
  }, [phase])

  const backToSetup = () => {
    setPhase('setup')
    setQuiz(null)
    setResult(null)
    setError(null)
    setStartedAt(0)
  }

  return (
    <main className="mx-auto w-full max-w-5xl space-y-5">
      <header>
        <h1 className="flex items-center gap-2.5 text-2xl font-extrabold text-slate-900">
          <ListChecks className="h-6 w-6 text-teal-600" aria-hidden="true" />
          {t.quiz.title}
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">{t.quiz.subtitle}</p>
      </header>

      {phase !== 'results' && error && (
        <p className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}

      {phase !== 'setup' && translation.error && (
        <p className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="flex-1">{translation.error}</span>
          <button
            type="button"
            onClick={translation.dismiss}
            aria-label={t.common.close}
            className="shrink-0 rounded-full p-0.5 text-amber-600 transition-colors hover:bg-amber-100 hover:text-amber-800"
          >
            <XCircle className="h-4 w-4" aria-hidden="true" />
          </button>
        </p>
      )}

      {phase === 'setup' && (
        <SetupPanel
          config={config}
          setConfig={setConfig}
          topics={topics}
          topicsLoading={topicsLoading}
          bankTotal={bankTotal}
          onStart={startQuiz}
          starting={starting}
          t={t}
          lang={lang}
        />
      )}

      {phase === 'active' && quiz && (
        <ActivePanel
          quiz={quiz}
          config={config}
          topicMap={topicMap}
          t={t}
          lang={lang}
          isRTL={isRTL}
          translation={translation}
          onSubmit={submit}
          submitting={submitting}
          onExit={backToSetup}
          remaining={remaining}
          elapsed={elapsed}
        />
      )}

      {phase === 'results' && result && quiz && (
        <ResultsPanel
          result={result}
          quiz={quiz}
          t={t}
          lang={lang}
          translation={translation}
          onRetry={startQuiz}
          onNewQuiz={backToSetup}
          retrying={starting}
        />
      )}
    </main>
  )
}
