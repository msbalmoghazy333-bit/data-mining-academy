/**
 * Revision Center — one focused study plan, built entirely on endpoints
 * that already existed (no new backend work):
 *
 *   GET  /v1/dashboard/summary            -> weakest topics + recent attempts
 *   GET  /v1/topics                       -> topic titles and deck sizes
 *   GET  /v1/flashcards?limit=200         -> the review deck
 *   POST /v1/flashcards/{id}/confidence   -> spaced-repetition rating
 *
 * "Retake" buttons deep-link into the quiz simulator as
 * `/quiz?topic=<id>&start=1`, which Quiz.jsx understands.
 *
 * The deck is a *snapshot*: rating a card updates its confidence (and the
 * metrics), but never reshuffles the session under the learner's feet.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  Layers,
  Play,
  RefreshCcw,
  RotateCcw,
  Sparkles,
  TrendingUp,
  TriangleAlert,
} from 'lucide-react'

import api from '../lib/api.js'
import { fill, formatDateTime, pct } from '../lib/format.js'
import { useLanguage } from '../lib/i18n.jsx'
import { refreshSummary, useSummary } from '../lib/summaryStore.js'
import {
  Badge,
  Banner,
  Button,
  buttonClasses,
  Card,
  EmptyState,
  ProgressBar,
  Spinner,
} from '../components/ui.jsx'

const FLASHCARDS_URL = '/v1/flashcards'
const TOPICS_URL = '/v1/topics'
const CARD_LIMIT = 200

/** The four standard spaced-repetition ratings, in order of difficulty. */
const RATINGS = ['again', 'hard', 'good', 'easy']

const RATING_CLASSES = {
  again: 'border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100',
  hard: 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100',
  good: 'border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100',
  easy: 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100',
}

const CONFIDENCE_ORDER = { low: 0, medium: 1, high: 2 }
const CONFIDENCE_TONES = { low: 'rose', medium: 'amber', high: 'emerald' }

const QUEUE_TONES = { needs_revision: 'rose', learning: 'amber' }

/** Weakest confidence first; ties keep the oldest card first. */
function sortForReview(cards) {
  return [...cards].sort((a, b) => {
    const byConfidence =
      (CONFIDENCE_ORDER[a.confidence_level] ?? 1) -
      (CONFIDENCE_ORDER[b.confidence_level] ?? 1)
    return byConfidence !== 0 ? byConfidence : a.id - b.id
  })
}

/** Both read-only calls the plan is built from. */
function fetchPlan() {
  return Promise.all([
    api.get(`${FLASHCARDS_URL}?limit=${CARD_LIMIT}`),
    api.get(TOPICS_URL),
  ])
}

function scoreTone(score) {
  if (score >= 80) return 'emerald'
  if (score >= 50) return 'amber'
  return 'rose'
}

/* ------------------------------------------------------------------ */
/* Small pieces                                                        */
/* ------------------------------------------------------------------ */

const TILE_ICONS = {
  rose: 'bg-rose-50 text-rose-600',
  amber: 'bg-amber-50 text-amber-600',
  teal: 'bg-teal-50 text-teal-600',
  slate: 'bg-slate-100 text-slate-600',
}

function StatTile({ icon: Icon, tone = 'teal', label, value }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <span className={`rounded-xl p-2 ${TILE_ICONS[tone] ?? TILE_ICONS.teal}`}>
        <Icon className="h-4.5 w-4.5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="text-2xl font-extrabold tabular-nums text-slate-900">{value}</p>
        <p className="truncate text-xs text-slate-500">{label}</p>
      </div>
    </div>
  )
}

function FilterChip({ active, onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
        active
          ? 'border-teal-300 bg-teal-50 text-teal-700'
          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
      ].join(' ')}
    >
      {label}
    </button>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Revision() {
  const { t, lang } = useLanguage()
  const summary = useSummary()

  const [cards, setCards] = useState([])
  const [topics, setTopics] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  /* --- session filters (a snapshot of them becomes the deck) -------- */
  const [topicFilter, setTopicFilter] = useState(null)
  const [includeHigh, setIncludeHigh] = useState(false)

  /* --- running session --------------------------------------------- */
  const [deck, setDeck] = useState([])
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  /** Ratings applied during this visit: id -> {from, to}. */
  const [sessionRatings, setSessionRatings] = useState({})
  /** Latest server-confirmed confidence per card: id -> level. */
  const [overrides, setOverrides] = useState({})

  /** Take a fresh snapshot of the cards that match the current filters. */
  const buildSession = useCallback((sourceCards, { topicId, includeHigh: withHigh }) => {
    const scoped = sourceCards.filter((card) =>
      topicId == null ? true : card.topic_id === topicId,
    )
    const filtered = withHigh
      ? scoped
      : scoped.filter((card) => card.confidence_level !== 'high')

    setDeck(sortForReview(filtered))
    setIndex(0)
    setRevealed(false)
    setSessionRatings({})
  }, [])

  const applyPlan = useCallback(
    ([deckResponse, topicsResponse]) => {
      const items = deckResponse.items ?? []
      setCards(items)
      setTopics(topicsResponse.items ?? [])
      setOverrides({})
      setTopicFilter(null)
      setIncludeHigh(false)
      buildSession(items, { topicId: null, includeHigh: false })
    },
    [buildSession],
  )

  useEffect(() => {
    let cancelled = false
    fetchPlan()
      .then((responses) => {
        if (!cancelled) applyPlan(responses)
      })
      .catch(() => {
        if (!cancelled) setLoadError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [applyPlan])

  /* Cards with the ratings applied — metrics and re-snapshots use this. */
  const effectiveCards = useMemo(
    () =>
      cards.map((card) =>
        overrides[card.id] ? { ...card, confidence_level: overrides[card.id] } : card,
      ),
    [cards, overrides],
  )

  const selectTopic = (topicId) => {
    setTopicFilter(topicId)
    buildSession(effectiveCards, { topicId, includeHigh })
  }

  const toggleIncludeHigh = () => {
    const next = !includeHigh
    setIncludeHigh(next)
    buildSession(effectiveCards, { topicId: topicFilter, includeHigh: next })
  }

  const restartSession = () => {
    buildSession(effectiveCards, { topicId: topicFilter, includeHigh })
  }

  const reviewTopicCards = (topicId) => {
    selectTopic(topicId)
    document
      .getElementById('revision-cards')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  /* ---- derived data ------------------------------------------------- */

  const mastery = summary.data?.topics?.mastery ?? {}
  const recommended = summary.data?.recommended ?? []
  const recent = summary.data?.recent_attempts ?? []

  const weakCards = effectiveCards.filter((card) => card.confidence_level === 'low').length
  const mediumCards = effectiveCards.filter((card) => card.confidence_level === 'medium').length

  const cardTopics = useMemo(() => topics.filter((topic) => topic.flashcards > 0), [topics])
  const topicHasCards = useCallback(
    (topicId) => cards.some((card) => card.topic_id === topicId),
    [cards],
  )

  const currentCard = index < deck.length ? deck[index] : null
  const finished = deck.length > 0 && index >= deck.length

  const reviewed = Object.keys(sessionRatings).length
  const improved = Object.values(sessionRatings).filter(
    (entry) => (CONFIDENCE_ORDER[entry.to] ?? 1) > (CONFIDENCE_ORDER[entry.from] ?? 1),
  ).length

  const weakestTopicId = recommended[0]?.topic_id ?? null

  const isEmpty =
    topics.length === 0 && cards.length === 0 && recommended.length === 0

  const rate = async (rating) => {
    const card = currentCard
    if (!card || saving) return

    setSaving(true)
    setSaveError(null)
    try {
      const response = await api.post(`${FLASHCARDS_URL}/${card.id}/confidence`, { rating })
      setOverrides((previous) => ({ ...previous, [card.id]: response.confidence_level }))
      setSessionRatings((previous) => ({
        ...previous,
        [card.id]: { from: response.previous_confidence, to: response.confidence_level },
      }))
      setRevealed(false)
      setIndex((value) => value + 1)
    } catch (error) {
      setSaveError(error?.status ? t.revision.sessionError : t.revision.offline)
    } finally {
      setSaving(false)
    }
  }

  const skip = () => {
    setRevealed(false)
    setIndex((value) => value + 1)
  }

  const reload = () => {
    refreshSummary()
    setLoading(true)
    setLoadError(false)
    fetchPlan()
      .then(applyPlan)
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-extrabold text-slate-900">
            <RefreshCcw className="h-6 w-6 text-teal-600" aria-hidden="true" />
            {t.revision.title}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{t.revision.subtitle}</p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={RotateCcw}
          onClick={reload}
          disabled={loading}
        >
          {t.revision.refresh}
        </Button>
      </header>

      {loadError && (
        <div className="space-y-2">
          <Banner tone="error" onDismiss={() => setLoadError(false)}>
            {t.revision.offline}
          </Banner>
          <button type="button" onClick={reload} className={buttonClasses({ variant: 'secondary' })}>
            {t.revision.retry}
          </button>
        </div>
      )}

      {saveError && (
        <Banner tone="error" onDismiss={() => setSaveError(null)}>
          {saveError}
        </Banner>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-10 text-slate-500">
          <Spinner />
          {t.common.loading}
        </div>
      ) : isEmpty ? (
        <Card>
          <EmptyState
            icon={BookOpen}
            title={t.revision.empty}
            hint={t.revision.emptyHint}
            action={
              <Link to="/library" className={buttonClasses({})}>
                {t.revision.goLibrary}
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          {/* ----------------------------- metrics ---------------------------- */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              icon={TriangleAlert}
              tone="rose"
              label={t.revision.metrics.needsRevision}
              value={mastery.needs_revision ?? 0}
            />
            <StatTile
              icon={BookOpen}
              tone="amber"
              label={t.revision.metrics.learning}
              value={mastery.learning ?? 0}
            />
            <StatTile
              icon={Layers}
              tone="teal"
              label={t.revision.metrics.weakCards}
              value={weakCards}
            />
            <StatTile
              icon={Layers}
              tone="slate"
              label={t.revision.metrics.mediumCards}
              value={mediumCards}
            />
          </div>

          {/* -------------------------- queue + session ----------------------- */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <Card icon={TrendingUp} title={t.revision.queue.title}>
                <p className="mb-3 text-xs text-slate-500">{t.revision.queue.hint}</p>

                {recommended.length === 0 ? (
                  <EmptyState icon={Sparkles} title={t.revision.queue.empty} />
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {recommended.map((entry) => (
                      <li
                        key={entry.topic_id}
                        className="space-y-2 py-3 first:pt-1 last:pb-1"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800">
                            <span className="ltr">{entry.title_en}</span>
                            {entry.title_ar && (
                              <span className="text-slate-400"> — {entry.title_ar}</span>
                            )}
                          </p>
                          <Badge tone={QUEUE_TONES[entry.mastery_status] ?? 'slate'}>
                            {t.dashboard.dist.statuses[entry.mastery_status]}
                          </Badge>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs text-slate-500">
                            {fill(t.revision.queue.attempts, { n: entry.attempts })}
                            {entry.last_score != null
                              ? ` · ${fill(t.revision.queue.lastScore, { score: entry.last_score })}`
                              : ` · ${t.revision.queue.noScore}`}
                          </p>
                          <div className="flex items-center gap-2">
                            {topicHasCards(entry.topic_id) && (
                              <button
                                type="button"
                                onClick={() => reviewTopicCards(entry.topic_id)}
                                className={buttonClasses({ variant: 'secondary', size: 'sm' })}
                              >
                                <Layers className="h-3.5 w-3.5" aria-hidden="true" />
                                {t.revision.queue.cards}
                              </button>
                            )}
                            <Link
                              to={`/quiz?topic=${entry.topic_id}&start=1`}
                              className={buttonClasses({ size: 'sm' })}
                            >
                              <Play className="h-3.5 w-3.5" aria-hidden="true" />
                              {t.revision.queue.retake}
                            </Link>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <div id="revision-cards" className="scroll-mt-6 lg:col-span-3">
              <Card icon={Layers} title={t.revision.cards.title}>
                {/* filters */}
                <div className="mb-4 space-y-2">
                  <p className="text-xs font-semibold text-slate-500">
                    {t.revision.cards.filters.label}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <FilterChip
                      active={topicFilter === null}
                      onClick={() => selectTopic(null)}
                      label={t.revision.cards.filters.all}
                    />
                    {cardTopics.map((topic) => (
                      <FilterChip
                        key={topic.id}
                        active={topicFilter === topic.id}
                        onClick={() => selectTopic(topic.id)}
                        label={`${topic.title_en} (${topic.flashcards})`}
                      />
                    ))}
                  </div>
                  <label className="flex w-fit items-center gap-2 pt-1 text-xs text-slate-600">
                    <input
                      type="checkbox"
                      checked={includeHigh}
                      onChange={toggleIncludeHigh}
                      className="h-4 w-4 rounded border-slate-300 accent-teal-600"
                    />
                    {t.revision.cards.filters.includeHigh}
                  </label>
                </div>

                {cards.length === 0 ? (
                  <EmptyState
                    icon={Layers}
                    title={t.revision.cards.empty}
                    hint={t.revision.cards.emptyHint}
                  />
                ) : deck.length === 0 ? (
                  <EmptyState
                    icon={Sparkles}
                    title={t.revision.cards.emptyFiltered}
                    hint={t.revision.cards.emptyFilteredHint}
                  />
                ) : finished ? (
                  <EmptyState
                    icon={Sparkles}
                    title={t.revision.cards.done.title}
                    hint={
                      reviewed === 0
                        ? t.revision.cards.done.descSkipped
                        : fill(t.revision.cards.done.desc, { reviewed, improved })
                    }
                    action={
                      <div className="flex flex-wrap items-center justify-center gap-2">
                        <Button onClick={restartSession}>
                          {t.revision.cards.done.restart}
                        </Button>
                        {weakestTopicId != null && (
                          <Link
                            to={`/quiz?topic=${weakestTopicId}&start=1`}
                            className={buttonClasses({ variant: 'secondary' })}
                          >
                            <Play className="h-4 w-4" aria-hidden="true" />
                            {t.revision.cards.done.quiz}
                          </Link>
                        )}
                      </div>
                    }
                  />
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <Badge tone={CONFIDENCE_TONES[currentCard.confidence_level] ?? 'slate'}>
                        {t.revision.cards.tones[currentCard.confidence_level] ??
                          currentCard.confidence_level}
                      </Badge>
                      <span className="text-xs font-semibold tabular-nums text-slate-500">
                        {fill(t.revision.cards.progress, {
                          n: index + 1,
                          total: deck.length,
                        })}
                      </span>
                    </div>

                    <ProgressBar value={pct(index, deck.length) ?? 0} tone="teal" />

                    <button
                      type="button"
                      onClick={() => setRevealed(true)}
                      disabled={revealed}
                      aria-label={revealed ? t.revision.cards.back : t.revision.cards.flip}
                      className="min-h-40 w-full rounded-2xl border border-slate-200 bg-slate-50 px-5 py-6 text-center transition-colors hover:bg-slate-100 disabled:cursor-default disabled:hover:bg-slate-50"
                    >
                      <span className="block text-[11px] font-bold tracking-wide text-teal-700 uppercase">
                        {revealed ? t.revision.cards.back : t.revision.cards.front}
                      </span>
                      <span
                        dir="auto"
                        className={
                          revealed
                            ? 'mt-2 block text-base leading-relaxed text-slate-700'
                            : 'mt-2 block text-lg font-bold text-slate-900'
                        }
                      >
                        {revealed ? currentCard.back : currentCard.front}
                      </span>
                      {!revealed && (
                        <span className="mt-3 inline-block text-xs font-semibold text-slate-400">
                          {t.revision.cards.flip}
                        </span>
                      )}
                    </button>

                    <p className="text-center text-xs text-slate-400">
                      <span className="ltr">{currentCard.topic_title_en}</span>
                      {currentCard.topic_title_ar && ` — ${currentCard.topic_title_ar}`}
                    </p>

                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {RATINGS.map((rating) => (
                        <button
                          key={rating}
                          type="button"
                          onClick={() => rate(rating)}
                          disabled={!revealed || saving}
                          className={[
                            'rounded-xl border px-3 py-2 text-sm font-bold transition-colors',
                            'disabled:cursor-not-allowed disabled:opacity-50',
                            RATING_CLASSES[rating],
                          ].join(' ')}
                        >
                          {t.revision.cards.ratings[rating]}
                        </button>
                      ))}
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs text-slate-400">{t.revision.cards.hint}</p>
                      <button
                        type="button"
                        onClick={skip}
                        disabled={saving}
                        className={buttonClasses({ variant: 'ghost', size: 'sm' })}
                      >
                        {t.revision.cards.skip}
                      </button>
                    </div>
                  </div>
                )}
              </Card>
            </div>
          </div>

          {/* ----------------------------- attempts ---------------------------- */}
          <Card icon={Play} title={t.revision.recent.title}>
            <p className="mb-3 text-xs text-slate-500">{t.revision.recent.hint}</p>

            {recent.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">
                {t.revision.recent.empty}
              </p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {recent.map((attempt) => (
                  <li
                    key={attempt.attempt_id}
                    className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3 first:pt-1 last:pb-1"
                  >
                    <p className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800">
                      <span className="ltr">{attempt.topic_title_en}</span>
                    </p>
                    <span className="text-xs text-slate-400 tabular-nums">
                      {attempt.total_questions} {t.revision.recent.attempts}
                    </span>
                    <span className="text-xs text-slate-400">
                      {formatDateTime(attempt.completed_at, lang)}
                    </span>
                    <Badge tone={scoreTone(attempt.score)}>{attempt.score}%</Badge>
                    <Link
                      to={`/quiz?topic=${attempt.topic_id}&start=1`}
                      className={buttonClasses({ variant: 'secondary', size: 'sm' })}
                    >
                      <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                      {t.revision.recent.retake}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </main>
  )
}
