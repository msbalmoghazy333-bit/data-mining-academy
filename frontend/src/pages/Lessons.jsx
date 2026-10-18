/**
 * Lesson Viewer — read published lessons without leaving the app.
 *
 * Three read-only calls, all existing backend contracts:
 *   GET /v1/topics            -> syllabus sidebar (titles + mastery)
 *   GET /v1/lessons           -> compact summaries, grouped by topic
 *   GET /v1/lessons/{id}      -> the full lesson, fetched lazily per lesson
 *
 * The Markdown body is rendered by the small in-house renderer in
 * `lib/markdown.jsx`; the structured blocks (objectives, glossary, formulas,
 * comparisons) come from the JSON columns and render as cards/tables.
 *
 * `/lessons?topic=<id>` opens a specific topic (used for deep links).
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Award,
  BookOpen,
  Languages,
  Layers,
  ListChecks,
  Play,
  RefreshCcw,
  Search,
  Sigma,
} from 'lucide-react'

import api from '../lib/api.js'
import { fill, formatDateTime } from '../lib/format.js'
import { useLanguage } from '../lib/i18n.jsx'
import Markdown from '../lib/markdown.jsx'
import {
  Badge,
  Banner,
  Button,
  buttonClasses,
  Card,
  EmptyState,
  Spinner,
} from '../components/ui.jsx'

const TOPICS_URL = '/v1/topics'
const LESSONS_URL = '/v1/lessons'
const LESSON_LIMIT = 200

const QUEUE_TONES = { needs_revision: 'rose', learning: 'amber', mastered: 'emerald' }

/** Group the flat lesson catalogue into `topic_id -> [summaries]`. */
function indexByTopic(items) {
  const index = {}
  for (const item of items ?? []) {
    if (!index[item.topic_id]) index[item.topic_id] = []
    index[item.topic_id].push(item)
  }
  return index
}

/* ------------------------------------------------------------------ */
/* Structured blocks                                                   */
/* ------------------------------------------------------------------ */

function ObjectivesCard({ objectives, prerequisites, t }) {
  return (
    <Card icon={ListChecks} title={t.lessons.blocks.objectives}>
      <ul className="space-y-2">
        {objectives.map((objective, index) => (
          <li key={index} className="flex gap-2 text-sm leading-relaxed text-slate-700">
            <span className="mt-0.5 shrink-0 font-bold text-teal-600" aria-hidden="true">
              ✓
            </span>
            <span className="min-w-0">{objective}</span>
          </li>
        ))}
      </ul>

      {prerequisites.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <p className="mb-2 text-xs font-semibold text-slate-500">
            {t.lessons.blocks.prerequisites}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {prerequisites.map((item, index) => (
              <Badge key={index} tone="slate">
                {item}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

function FormulasCard({ formulas, t }) {
  return (
    <Card icon={Sigma} title={t.lessons.blocks.formulas}>
      <ul className="space-y-3">
        {formulas.map((formula, index) => (
          <li
            key={index}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3"
          >
            <p className="text-sm font-bold text-slate-800">
              {formula.name || t.lessons.blocks.formulas}
            </p>
            {formula.latex && (
              <pre
                dir="ltr"
                className="mt-2 overflow-x-auto rounded-lg bg-slate-900 px-3 py-2 text-start font-mono text-xs leading-relaxed text-slate-100"
              >
                <code>{formula.latex}</code>
              </pre>
            )}
            {formula.note && (
              <p className="mt-2 text-xs leading-relaxed text-slate-500">
                <span className="font-semibold text-slate-400">
                  {t.lessons.formulaNote}:{' '}
                </span>
                {formula.note}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function TerminologyCard({ entries, t }) {
  return (
    <Card icon={Languages} title={t.lessons.blocks.terminology}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              {[t.lessons.terminologyTable.term, t.lessons.terminologyTable.arabic, t.lessons.terminologyTable.definition].map(
                (label) => (
                  <th
                    key={label}
                    className="border border-slate-200 bg-slate-50 px-3 py-2 text-start font-bold text-slate-700"
                  >
                    {label}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, index) => (
              <tr key={index}>
                <td className="border border-slate-200 px-3 py-2 align-top font-semibold text-slate-800">
                  <span className="ltr">{entry.term}</span>
                </td>
                <td className="border border-slate-200 px-3 py-2 align-top text-slate-700">
                  {entry.arabic}
                </td>
                <td className="border border-slate-200 px-3 py-2 align-top text-slate-600">
                  {entry.definition}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function ComparisonsCard({ entries, t }) {
  return (
    <Card icon={Layers} title={t.lessons.blocks.comparisons}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              {[t.lessons.comparisonTable.pair, t.lessons.comparisonTable.aspect, t.lessons.comparisonTable.detail].map(
                (label) => (
                  <th
                    key={label}
                    className="border border-slate-200 bg-slate-50 px-3 py-2 text-start font-bold text-slate-700"
                  >
                    {label}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, index) => (
              <tr key={index}>
                <td className="border border-slate-200 px-3 py-2 align-top font-semibold text-slate-800">
                  <span className="ltr">{entry.topic_a}</span>
                  <span className="text-slate-400"> ↔ </span>
                  <span className="ltr">{entry.topic_b}</span>
                </td>
                <td className="border border-slate-200 px-3 py-2 align-top text-slate-700">
                  {entry.aspect}
                </td>
                <td className="border border-slate-200 px-3 py-2 align-top text-slate-600">
                  {entry.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Lessons() {
  const { t, lang } = useLanguage()
  const [searchParams] = useSearchParams()

  const linkedTopicId = useMemo(() => {
    const id = Number(searchParams.get('topic'))
    return Number.isInteger(id) && id > 0 ? id : null
  }, [searchParams])

  const [catalogue, setCatalogue] = useState({
    status: 'loading',
    topics: [],
    lessonIndex: {},
  })
  const [reloadToken, setReloadToken] = useState(0)

  const [selectedTopicId, setSelectedTopicId] = useState(linkedTopicId)
  const [selectedLessonId, setSelectedLessonId] = useState(null)
  const [query, setQuery] = useState('')

  /** id -> full lesson (or `{ error: true }`), so retry is just a delete. */
  const [lessons, setLessons] = useState({})

  /* ---- catalogue (topics + lesson summaries) ------------------------ */
  useEffect(() => {
    let cancelled = false

    Promise.all([
      api.get(TOPICS_URL),
      api.get(`${LESSONS_URL}?limit=${LESSON_LIMIT}`),
    ])
      .then(([topicsResponse, lessonsResponse]) => {
        if (cancelled) return
        setCatalogue({
          status: 'ready',
          topics: topicsResponse.items ?? [],
          lessonIndex: indexByTopic(lessonsResponse.items),
        })
      })
      .catch(() => {
        if (!cancelled) setCatalogue((previous) => ({ ...previous, status: 'error' }))
      })

    return () => {
      cancelled = true
    }
  }, [reloadToken])

  const { topics, lessonIndex } = catalogue

  /* ---- active topic / lesson --------------------------------------- */
  const activeTopicId = useMemo(() => {
    if (selectedTopicId != null) return selectedTopicId
    const firstWithLesson = topics.find((topic) => lessonIndex[topic.id]?.length)
    return firstWithLesson?.id ?? topics[0]?.id ?? null
  }, [selectedTopicId, topics, lessonIndex])

  const activeTopic = topics.find((topic) => topic.id === activeTopicId) ?? null
  const activeLessons = activeTopicId != null ? lessonIndex[activeTopicId] ?? [] : []
  const activeLessonId = selectedLessonId ?? activeLessons[0]?.id ?? null

  /* ---- lesson body, fetched once per lesson ------------------------ */
  useEffect(() => {
    if (activeLessonId == null || lessons[activeLessonId] !== undefined) return undefined

    let cancelled = false

    api
      .get(`${LESSONS_URL}/${activeLessonId}`)
      .then((data) => {
        if (!cancelled) {
          setLessons((previous) => ({ ...previous, [activeLessonId]: data }))
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLessons((previous) => ({ ...previous, [activeLessonId]: { error: true } }))
        }
      })

    return () => {
      cancelled = true
    }
  }, [activeLessonId, lessons])

  const entry = activeLessonId != null ? lessons[activeLessonId] : undefined
  const lesson = entry && !entry.error ? entry : null
  const lessonError = Boolean(entry?.error)

  const retryLesson = useCallback((lessonId) => {
    setLessons((previous) => {
      const next = { ...previous }
      delete next[lessonId]
      return next
    })
  }, [])

  const selectTopic = (topicId) => {
    setSelectedTopicId(topicId)
    setSelectedLessonId(null)
  }

  const selectLesson = (lessonId) => {
    if (lessonId === activeLessonId) return
    setSelectedLessonId(lessonId)
  }

  const filteredTopics = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return topics
    return topics.filter(
      (topic) =>
        topic.title_en.toLowerCase().includes(needle) ||
        topic.title_ar.toLowerCase().includes(needle),
    )
  }, [topics, query])

  const position = topics.findIndex((topic) => topic.id === activeTopicId)
  const previousTopic = position > 0 ? topics[position - 1] : null
  const nextTopic = position >= 0 && position < topics.length - 1 ? topics[position + 1] : null

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-extrabold text-slate-900">
            <BookOpen className="h-6 w-6 text-teal-600" aria-hidden="true" />
            {t.lessons.title}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{t.lessons.subtitle}</p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={RefreshCcw}
          onClick={() => setReloadToken((value) => value + 1)}
          disabled={catalogue.status === 'loading'}
        >
          {t.lessons.refresh}
        </Button>
      </header>

      {catalogue.status === 'error' && (
        <div className="space-y-2">
          <Banner tone="error">{t.lessons.offline}</Banner>
          <button
            type="button"
            onClick={() => setReloadToken((value) => value + 1)}
            className={buttonClasses({ variant: 'secondary' })}
          >
            {t.lessons.retry}
          </button>
        </div>
      )}

      {catalogue.status === 'loading' ? (
        <div className="flex items-center gap-2 py-10 text-slate-500">
          <Spinner />
          {t.common.loading}
        </div>
      ) : topics.length === 0 ? (
        <Card>
          <EmptyState
            icon={BookOpen}
            title={t.lessons.empty}
            hint={t.lessons.emptyHint}
            action={
              <Link to="/library" className={buttonClasses({})}>
                {t.lessons.goLibrary}
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[19rem_1fr]">
          {/* ---------------------------- syllabus --------------------------- */}
          <aside className="lg:sticky lg:top-6 lg:self-start">
            <Card icon={BookOpen} title={t.lessons.topics}>
              <div className="relative mb-3">
                <Search
                  className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t.lessons.search}
                  aria-label={t.lessons.search}
                  className="w-full rounded-xl border border-slate-300 bg-white py-2 pe-9 ps-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-teal-400 focus:outline-none"
                />
              </div>

              {filteredTopics.length === 0 ? (
                <p className="py-4 text-center text-sm text-slate-500">
                  {t.lessons.noMatch}
                </p>
              ) : (
                <ul className="max-h-[60vh] space-y-1.5 overflow-y-auto pe-1">
                  {filteredTopics.map((topic) => {
                    const count = lessonIndex[topic.id]?.length ?? 0
                    const active = topic.id === activeTopicId
                    return (
                      <li key={topic.id}>
                        <button
                          type="button"
                          onClick={() => selectTopic(topic.id)}
                          aria-current={active ? 'true' : undefined}
                          className={[
                            'w-full rounded-xl border px-3 py-2.5 text-start transition-colors',
                            active
                              ? 'border-teal-300 bg-teal-50 ring-1 ring-teal-200'
                              : 'border-slate-200 bg-white hover:bg-slate-50',
                          ].join(' ')}
                        >
                          <span className="flex items-start justify-between gap-2">
                            <span className="min-w-0">
                              <span className="block truncate text-sm font-bold text-slate-800">
                                <span className="ltr">{topic.title_en}</span>
                              </span>
                              <span className="block truncate text-xs text-slate-500">
                                {topic.title_ar}
                              </span>
                            </span>
                            {count > 0 ? (
                              <Badge tone="teal">{count}</Badge>
                            ) : (
                              <span className="shrink-0 text-[11px] text-slate-400">
                                {t.lessons.noLessons}
                              </span>
                            )}
                          </span>
                          <span className="mt-1.5 block text-[11px] font-semibold text-slate-400">
                            {t.dashboard.dist.statuses[topic.mastery_status]}
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </Card>
          </aside>

          {/* ---------------------------- reading pane ---------------------- */}
          <section className="space-y-5">
            {activeTopic == null ? (
              <Card>
                <EmptyState icon={BookOpen} title={t.lessons.pick} />
              </Card>
            ) : activeLessons.length === 0 ? (
              <Card>
                <EmptyState
                  icon={BookOpen}
                  title={t.lessons.noLesson}
                  hint={t.lessons.noLessonHint}
                />
              </Card>
            ) : (
              <>
                {/* topic head */}
                <Card>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="text-lg font-extrabold text-slate-900">
                        <span className="ltr">{activeTopic.title_en}</span>
                        {activeTopic.title_ar && (
                          <span className="text-slate-400"> — {activeTopic.title_ar}</span>
                        )}
                      </h2>
                      {lesson && (
                        <p className="mt-1 text-xs text-slate-400">
                          {fill(t.lessons.chars, { n: lesson.content_chars })} ·{' '}
                          {formatDateTime(lesson.updated_at, lang)}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={QUEUE_TONES[activeTopic.mastery_status] ?? 'slate'}>
                        {t.dashboard.dist.statuses[activeTopic.mastery_status]}
                      </Badge>
                      <Link
                        to={`/quiz?topic=${activeTopic.id}&start=1`}
                        className={buttonClasses({ size: 'sm' })}
                      >
                        <Play className="h-3.5 w-3.5" aria-hidden="true" />
                        {t.lessons.actions.quiz}
                      </Link>
                    </div>
                  </div>

                  {activeLessons.length > 1 && (
                    <div className="mt-4 flex flex-wrap gap-1.5 border-t border-slate-100 pt-3">
                      {activeLessons.map((item, index) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => selectLesson(item.id)}
                          className={[
                            'rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
                            item.id === activeLessonId
                              ? 'border-teal-300 bg-teal-50 text-teal-700'
                              : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                          ].join(' ')}
                        >
                          {index + 1}
                        </button>
                      ))}
                    </div>
                  )}
                </Card>

                {lessonError ? (
                  <Card>
                    <Banner tone="error">{t.lessons.lessonError}</Banner>
                    <button
                      type="button"
                      onClick={() => retryLesson(activeLessonId)}
                      className={`${buttonClasses({ variant: 'secondary' })} mt-3`}
                    >
                      {t.lessons.retry}
                    </button>
                  </Card>
                ) : !lesson ? (
                  <Card>
                    <div className="flex items-center gap-2 py-6 text-slate-500">
                      <Spinner />
                      {t.lessons.loadingLesson}
                    </div>
                  </Card>
                ) : (
                  <>
                    {lesson.objectives.length > 0 && (
                      <ObjectivesCard
                        objectives={lesson.objectives}
                        prerequisites={lesson.prerequisites}
                        t={t}
                      />
                    )}

                    <Card title={t.lessons.blocks.content}>
                      <Markdown source={lesson.content_ar} />
                    </Card>

                    {lesson.formulas.length > 0 && (
                      <FormulasCard formulas={lesson.formulas} t={t} />
                    )}

                    {lesson.english_terminology.length > 0 && (
                      <TerminologyCard entries={lesson.english_terminology} t={t} />
                    )}

                    {lesson.comparisons.length > 0 && (
                      <ComparisonsCard entries={lesson.comparisons} t={t} />
                    )}

                    {lesson.summary && (
                      <section className="rounded-2xl border border-teal-200 bg-teal-50/70 px-5 py-4">
                        <h2 className="flex items-center gap-2 text-base font-bold text-teal-800">
                          <Award className="h-4.5 w-4.5" aria-hidden="true" />
                          {t.lessons.blocks.summary}
                        </h2>
                        <div className="mt-1">
                          <Markdown source={lesson.summary} />
                        </div>
                      </section>
                    )}
                  </>
                )}

                {/* prev / next in syllabus order */}
                {(previousTopic || nextTopic) && (
                  <nav className="flex flex-wrap items-center justify-between gap-2">
                    {previousTopic ? (
                      <button
                        type="button"
                        onClick={() => selectTopic(previousTopic.id)}
                        className={buttonClasses({ variant: 'secondary', size: 'sm' })}
                      >
                        {t.lessons.actions.prev} ·{' '}
                        <span className="ltr">{previousTopic.title_en}</span>
                      </button>
                    ) : (
                      <span />
                    )}
                    {nextTopic && (
                      <button
                        type="button"
                        onClick={() => selectTopic(nextTopic.id)}
                        className={buttonClasses({ variant: 'secondary', size: 'sm' })}
                      >
                        {t.lessons.actions.next} ·{' '}
                        <span className="ltr">{nextTopic.title_en}</span>
                      </button>
                    )}
                  </nav>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </main>
  )
}
