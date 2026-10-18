/**
 * Flashcards — the whole deck, the learner's way.
 *
 * The Revision Center runs one curated plan over the *weak* cards; this screen
 * is the deck itself: filter by topic / confidence / free text, shuffle it, and
 * then either skim every card with quick one-click ratings or run a focused
 * study session (flip, rate, keyboard shortcuts).
 *
 * Endpoints used (all existing, no backend change):
 *   GET  /v1/flashcards?limit=&offset=      walked page by page so the deck is
 *                                           never silently truncated
 *   POST /v1/flashcards/{id}/confidence     the four-way rating
 *
 * `/flashcards?topic=<id>` pre-filters the deck (used by the lesson viewer).
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Layers, Loader2, Play, RefreshCcw, RotateCcw, Search, Shuffle } from 'lucide-react'

import api from '../lib/api.js'
import { fill, pct } from '../lib/format.js'
import { useLanguage } from '../lib/i18n.jsx'
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

const CARDS_URL = '/v1/flashcards'
const PAGE_SIZE = 200
/** Safety valve for pathological decks; the screen says so when it kicks in. */
const DECK_CAP = 1000

const RATINGS = ['again', 'hard', 'good', 'easy']
const CONFIDENCE_LEVELS = ['low', 'medium', 'high']
const CONFIDENCE_RANK = { low: 0, medium: 1, high: 2 }
const CONFIDENCE_TONES = { low: 'rose', medium: 'amber', high: 'emerald' }

const STAT_TONES = {
  slate: 'text-slate-700',
  rose: 'text-rose-600',
  amber: 'text-amber-600',
  emerald: 'text-emerald-600',
}

const RATING_CLASSES = {
  again: 'border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100',
  hard: 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100',
  good: 'border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100',
  easy: 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100',
}

/** The deck endpoint is paged — walk it so the screen never hides cards. */
async function loadDeck() {
  const first = await api.get(`${CARDS_URL}?limit=${PAGE_SIZE}`)
  const cards = [...(first.items ?? [])]
  const total = first.total ?? cards.length

  while (cards.length < total && cards.length < DECK_CAP) {
    const page = await api.get(`${CARDS_URL}?limit=${PAGE_SIZE}&offset=${cards.length}`)
    const items = page.items ?? []
    if (items.length === 0) break
    cards.push(...items)
  }

  return { total, cards }
}

/* ------------------------------------------------------------------ */
/* Small pieces                                                        */
/* ------------------------------------------------------------------ */

function StatTile({ label, value, tone = 'slate', active = false, onClick }) {
  const className = [
    'rounded-2xl border px-4 py-3 text-start transition-colors',
    active ? 'border-teal-300 bg-teal-50 ring-1 ring-teal-200' : 'border-slate-200 bg-white',
    onClick ? 'hover:bg-slate-50' : '',
  ].join(' ')

  const body = (
    <>
      <span className="block text-xs font-semibold text-slate-500">{label}</span>
      <span className={`mt-1 block text-2xl font-extrabold ${STAT_TONES[tone] ?? STAT_TONES.slate}`}>
        {value}
      </span>
    </>
  )

  if (!onClick) return <div className={className}>{body}</div>

  return (
    <button type="button" onClick={onClick} aria-pressed={active} className={className}>
      {body}
    </button>
  )
}

/** The four-way rating, identical in the grid (compact) and the session. */
function RatingButtons({ onRate, disabled = false, compact = false }) {
  const { t } = useLanguage()

  return (
    <div className={compact ? 'flex flex-wrap gap-1.5' : 'grid grid-cols-2 gap-2 sm:grid-cols-4'}>
      {RATINGS.map((rating) => (
        <button
          key={rating}
          type="button"
          onClick={() => onRate(rating)}
          disabled={disabled}
          className={[
            'rounded-xl border font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60',
            compact ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-2 text-sm',
            RATING_CLASSES[rating],
          ].join(' ')}
        >
          {t.flashcards.ratings[rating]}
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Flashcards() {
  const { t } = useLanguage()
  const [searchParams] = useSearchParams()

  const linkedTopicId = useMemo(() => {
    const id = Number(searchParams.get('topic'))
    return Number.isInteger(id) && id > 0 ? id : null
  }, [searchParams])

  const [deckState, setDeckState] = useState({ status: 'loading', total: 0, cards: [] })
  const [reloadToken, setReloadToken] = useState(0)

  const [topicId, setTopicId] = useState(linkedTopicId)
  const [levels, setLevels] = useState([])
  const [query, setQuery] = useState('')
  const [order, setOrder] = useState([])
  const [shuffled, setShuffled] = useState(false)

  /** A snapshot of the filtered deck, so filtering never reshuffles a session. */
  const [study, setStudy] = useState(null)
  const [flipped, setFlipped] = useState(false)
  const [savingId, setSavingId] = useState(null)
  const [saveError, setSaveError] = useState(false)

  /* ---- the deck ---------------------------------------------------- */
  useEffect(() => {
    let cancelled = false

    loadDeck()
      .then((deck) => {
        if (cancelled) return
        setDeckState({ status: 'ready', total: deck.total, cards: deck.cards })
      })
      .catch(() => {
        if (!cancelled) setDeckState((previous) => ({ ...previous, status: 'error' }))
      })

    return () => {
      cancelled = true
    }
  }, [reloadToken])

  const cards = deckState.cards

  /* ---- derived views ----------------------------------------------- */
  const topics = useMemo(() => {
    const seen = new Map()
    for (const card of cards) {
      if (!seen.has(card.topic_id)) {
        seen.set(card.topic_id, {
          id: card.topic_id,
          title_en: card.topic_title_en,
          title_ar: card.topic_title_ar,
        })
      }
    }
    return [...seen.values()]
  }, [cards])

  const counts = useMemo(() => {
    const tally = { total: cards.length, low: 0, medium: 0, high: 0 }
    for (const card of cards) {
      if (tally[card.confidence_level] !== undefined) tally[card.confidence_level] += 1
    }
    return tally
  }, [cards])

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()

    const filtered = cards.filter((card) => {
      if (topicId != null && card.topic_id !== topicId) return false
      if (levels.length > 0 && !levels.includes(card.confidence_level)) return false
      if (needle && !`${card.front} ${card.back}`.toLowerCase().includes(needle)) return false
      return true
    })

    if (order.length === 0) return filtered

    const rank = new Map(order.map((id, position) => [id, position]))
    return [...filtered].sort((a, b) => (rank.get(a.id) ?? 0) - (rank.get(b.id) ?? 0))
  }, [cards, topicId, levels, query, order])

  /* ---- writes ------------------------------------------------------ */
  const applyRating = useCallback(async (card, rating) => {
    setSavingId(card.id)
    setSaveError(false)

    try {
      const response = await api.post(`${CARDS_URL}/${card.id}/confidence`, { rating })
      const patch = (item) =>
        item.id === card.id ? { ...item, confidence_level: response.confidence_level } : item

      setDeckState((previous) => ({ ...previous, cards: previous.cards.map(patch) }))
      setStudy((previous) =>
        previous ? { ...previous, cards: previous.cards.map(patch) } : previous,
      )

      return response
    } catch {
      setSaveError(true)
      return null
    } finally {
      setSavingId(null)
    }
  }, [])

  const studyCard = study && study.index < study.cards.length ? study.cards[study.index] : null

  const rateStudyCard = useCallback(
    async (rating) => {
      if (!studyCard) return

      const response = await applyRating(studyCard, rating)
      if (!response) return

      const improved =
        (CONFIDENCE_RANK[response.confidence_level] ?? 0) >
        (CONFIDENCE_RANK[response.previous_confidence] ?? 0)

      setFlipped(false)
      setStudy((previous) =>
        previous
          ? {
              ...previous,
              index: previous.index + 1,
              reviewed: previous.reviewed + 1,
              improved: previous.improved + (improved ? 1 : 0),
            }
          : previous,
      )
    },
    [studyCard, applyRating],
  )

  const skipStudyCard = useCallback(() => {
    setFlipped(false)
    setStudy((previous) => (previous ? { ...previous, index: previous.index + 1 } : previous))
  }, [])

  /* ---- controls ---------------------------------------------------- */
  const startStudy = () => {
    if (visible.length === 0) return
    setSaveError(false)
    setFlipped(false)
    setStudy({ cards: visible, index: 0, reviewed: 0, improved: 0 })
  }

  const exitStudy = () => {
    setFlipped(false)
    setStudy(null)
  }

  const toggleLevel = (level) => {
    setLevels((previous) =>
      previous.includes(level)
        ? previous.filter((item) => item !== level)
        : [...previous, level],
    )
  }

  const toggleShuffle = () => {
    if (shuffled) {
      setShuffled(false)
      setOrder([])
      return
    }

    const ids = cards.map((card) => card.id)
    for (let i = ids.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1))
      const swap = ids[i]
      ids[i] = ids[j]
      ids[j] = swap
    }

    setShuffled(true)
    setOrder(ids)
  }

  const clearFilters = () => {
    setTopicId(null)
    setLevels([])
    setQuery('')
    setShuffled(false)
    setOrder([])
  }

  /* ---- keyboard shortcuts (session only) --------------------------- */
  useEffect(() => {
    if (!study || study.index >= study.cards.length) return undefined

    const onKey = (event) => {
      const tag = event.target instanceof HTMLElement ? event.target.tagName : ''
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      if (event.key === 'Escape') {
        setFlipped(false)
        setStudy(null)
        return
      }

      if (event.code === 'Space' || event.key === ' ') {
        event.preventDefault()
        setFlipped((value) => !value)
        return
      }

      const position = ['1', '2', '3', '4'].indexOf(event.key)
      if (position >= 0 && flipped) {
        event.preventDefault()
        rateStudyCard(RATINGS[position])
      }
    }

    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [study, flipped, rateStudyCard])

  const sessionRunning = Boolean(study)

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-extrabold text-slate-900">
            <Layers className="h-6 w-6 text-teal-600" aria-hidden="true" />
            {t.flashcards.title}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{t.flashcards.subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            icon={RefreshCcw}
            onClick={() => setReloadToken((value) => value + 1)}
            disabled={deckState.status === 'loading'}
          >
            {t.flashcards.refresh}
          </Button>
          {!sessionRunning && (
            <Button icon={Play} onClick={startStudy} disabled={visible.length === 0}>
              {t.flashcards.study}
            </Button>
          )}
        </div>
      </header>

      {deckState.status === 'error' && (
        <div className="space-y-2">
          <Banner tone="error">{t.flashcards.offline}</Banner>
          <button
            type="button"
            onClick={() => setReloadToken((value) => value + 1)}
            className={buttonClasses({ variant: 'secondary' })}
          >
            {t.flashcards.retry}
          </button>
        </div>
      )}

      {saveError && (
        <Banner tone="error" onDismiss={() => setSaveError(false)}>
          {t.flashcards.saveError}
        </Banner>
      )}

      {deckState.status === 'loading' ? (
        <div className="flex items-center gap-2 py-10 text-slate-500">
          <Spinner />
          {t.common.loading}
        </div>
      ) : cards.length === 0 ? (
        <Card>
          <EmptyState
            icon={Layers}
            title={t.flashcards.empty}
            hint={t.flashcards.emptyHint}
            action={
              <Link to="/library" className={buttonClasses({})}>
                {t.flashcards.goLibrary}
              </Link>
            }
          />
        </Card>
      ) : study ? (
        /* ---------------------------- session --------------------------- */
        <Card
          icon={Layers}
          title={t.flashcards.session.title}
          actions={
            <button
              type="button"
              onClick={exitStudy}
              className={buttonClasses({ variant: 'ghost', size: 'sm' })}
            >
              {t.flashcards.session.exit}
            </button>
          }
        >
          {studyCard ? (
            <div className="mx-auto w-full max-w-2xl space-y-4">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-slate-500">
                  {fill(t.flashcards.session.progress, {
                    n: study.index + 1,
                    total: study.cards.length,
                  })}
                </span>
                <Badge tone={CONFIDENCE_TONES[studyCard.confidence_level] ?? 'slate'}>
                  {t.flashcards.tones[studyCard.confidence_level]}
                </Badge>
              </div>

              <ProgressBar value={pct(study.index, study.cards.length)} />

              <button
                type="button"
                onClick={() => setFlipped((value) => !value)}
                className="flex min-h-[15rem] w-full flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-6 py-8 text-center transition-colors hover:bg-white"
              >
                <span className="text-[11px] font-bold tracking-wide text-slate-400 uppercase">
                  {flipped ? t.flashcards.session.back : t.flashcards.session.front}
                </span>
                <span className="text-lg leading-relaxed font-semibold text-slate-800">
                  {flipped ? studyCard.back : studyCard.front}
                </span>
                {!flipped && (
                  <span className="text-xs text-slate-400">{t.flashcards.session.flipHint}</span>
                )}
                <span className="ltr text-[11px] text-slate-400">{studyCard.topic_title_en}</span>
              </button>

              {flipped && <RatingButtons onRate={rateStudyCard} disabled={savingId !== null} />}

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
                <span className="text-[11px] text-slate-400">{t.flashcards.session.keys}</span>
                <button
                  type="button"
                  onClick={skipStudyCard}
                  className={buttonClasses({ variant: 'secondary', size: 'sm' })}
                >
                  {t.flashcards.session.skip}
                </button>
              </div>
            </div>
          ) : (
            <div className="mx-auto w-full max-w-2xl py-4 text-center">
              <p className="text-lg font-bold text-slate-800">{t.flashcards.done.title}</p>
              <p className="mt-1 text-sm text-slate-500">
                {study.reviewed > 0
                  ? fill(t.flashcards.done.desc, {
                      reviewed: study.reviewed,
                      improved: study.improved,
                    })
                  : t.flashcards.done.descSkipped}
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                <Button icon={RotateCcw} onClick={startStudy}>
                  {t.flashcards.done.restart}
                </Button>
                <button
                  type="button"
                  onClick={exitStudy}
                  className={buttonClasses({ variant: 'secondary' })}
                >
                  {t.flashcards.done.back}
                </button>
              </div>
            </div>
          )}
        </Card>
      ) : (
        /* ---------------------------- deck ------------------------------ */
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label={t.flashcards.stats.total} value={counts.total} tone="slate" />
            {CONFIDENCE_LEVELS.map((level) => (
              <StatTile
                key={level}
                label={t.flashcards.stats[level]}
                value={counts[level]}
                tone={CONFIDENCE_TONES[level]}
                active={levels.includes(level)}
                onClick={() => toggleLevel(level)}
              />
            ))}
          </div>

          <Card
            icon={Search}
            title={t.flashcards.filters.title}
            actions={
              <span className="text-xs font-semibold text-slate-400">
                {fill(t.flashcards.filters.shown, {
                  n: visible.length,
                  total: counts.total,
                })}
              </span>
            }
          >
            <div className="grid gap-3 lg:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-slate-500">
                  {t.flashcards.filters.topic}
                </span>
                <select
                  value={topicId ?? ''}
                  onChange={(event) =>
                    setTopicId(event.target.value ? Number(event.target.value) : null)
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-teal-400 focus:outline-none"
                >
                  <option value="">{t.flashcards.filters.allTopics}</option>
                  {topics.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.title_ar} — {topic.title_en}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-semibold text-slate-500">
                  {t.flashcards.filters.search}
                </span>
                <span className="relative block">
                  <Search
                    className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                    aria-hidden="true"
                  />
                  <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder={t.flashcards.filters.search}
                    className="w-full rounded-xl border border-slate-300 bg-white py-2 pe-9 ps-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-teal-400 focus:outline-none"
                  />
                </span>
              </label>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
              <span className="text-xs font-semibold text-slate-500">
                {t.flashcards.filters.confidence}:
              </span>
              {CONFIDENCE_LEVELS.map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => toggleLevel(level)}
                  aria-pressed={levels.includes(level)}
                  className={[
                    'rounded-full border px-3 py-1 text-xs font-semibold transition-colors',
                    levels.includes(level)
                      ? 'border-teal-300 bg-teal-50 text-teal-700'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                  ].join(' ')}
                >
                  {t.flashcards.tones[level]} ({counts[level]})
                </button>
              ))}
              <button
                type="button"
                onClick={toggleShuffle}
                aria-pressed={shuffled}
                className={[
                  'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition-colors',
                  shuffled
                    ? 'border-teal-300 bg-teal-50 text-teal-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
                ].join(' ')}
              >
                <Shuffle className="h-3.5 w-3.5" aria-hidden="true" />
                {t.flashcards.filters.shuffle}
              </button>
              <button
                type="button"
                onClick={clearFilters}
                className="ms-auto text-xs font-semibold text-slate-500 underline hover:text-slate-700"
              >
                {t.flashcards.filters.clear}
              </button>
            </div>
          </Card>

          <Card icon={Layers} title={t.flashcards.browse.title}>
            <p className="mb-3 text-xs text-slate-400">{t.flashcards.browse.hint}</p>

            {deckState.total > cards.length && (
              <p className="mb-3 text-xs font-semibold text-amber-600">
                {fill(t.flashcards.capped, { shown: cards.length, total: deckState.total })}
              </p>
            )}

            {visible.length === 0 ? (
              <EmptyState
                icon={Search}
                title={t.flashcards.emptyFiltered}
                hint={t.flashcards.emptyFilteredHint}
                action={
                  <button
                    type="button"
                    onClick={clearFilters}
                    className={buttonClasses({ variant: 'secondary' })}
                  >
                    {t.flashcards.filters.clear}
                  </button>
                }
              />
            ) : (
              <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {visible.map((card) => (
                  <li
                    key={card.id}
                    className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <span className="ltr min-w-0 text-[11px] font-semibold text-slate-400">
                          {card.topic_title_en}
                        </span>
                        <Badge tone={CONFIDENCE_TONES[card.confidence_level] ?? 'slate'}>
                          {t.flashcards.tones[card.confidence_level]}
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm leading-relaxed font-semibold text-slate-800">
                        {card.front}
                      </p>
                      <p className="mt-1 text-sm leading-relaxed text-slate-600">{card.back}</p>
                    </div>

                    <div className="mt-3 border-t border-slate-100 pt-2">
                      <div className="mb-1.5 flex items-center justify-between gap-2">
                        <span className="text-[11px] font-semibold text-slate-400">
                          {t.flashcards.browse.quickRate}
                        </span>
                        {savingId === card.id && (
                          <Loader2
                            className="h-3.5 w-3.5 animate-spin text-teal-600"
                            aria-hidden="true"
                          />
                        )}
                      </div>
                      <RatingButtons
                        compact
                        disabled={savingId !== null}
                        onRate={(rating) => applyRating(card, rating)}
                      />
                    </div>
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
