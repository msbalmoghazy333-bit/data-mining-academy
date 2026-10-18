/**
 * Dashboard — the learner's home: metric cards, quick actions, mastery
 * distribution, recent quiz attempts, and the revision queue.
 *
 * All data comes from `GET /api/v1/dashboard/summary` via the shared
 * summary store (which also feeds the header progress pill).
 */

import { Link } from 'react-router-dom'
import {
  BookOpen,
  FileText,
  Play,
  RefreshCcw,
  Sparkles,
  TriangleAlert,
  TrendingUp,
  Upload,
} from 'lucide-react'

import { useLanguage } from '../lib/i18n.jsx'
import { fill, formatDateTime, pct } from '../lib/format.js'
import { refreshSummary, useSummary, } from '../lib/summaryStore.js'
import { Banner, Badge, buttonClasses, Card, EmptyState, ProgressBar, Spinner } from '../components/ui.jsx'

const QUEUE_TONES = {
  needs_revision: 'rose',
  learning: 'amber',
}

const SCORE_TONES = {
  high: 'emerald', // >= 80
  mid: 'amber', // >= 50
  low: 'rose', // < 50
}

function scoreTone(score) {
  if (score >= 80) return SCORE_TONES.high
  if (score >= 50) return SCORE_TONES.mid
  return SCORE_TONES.low
}

/* ------------------------------------------------------------------ */
/* Metric card                                                         */
/* ------------------------------------------------------------------ */

function MetricCard({ icon: Icon, title, value, sub, tone = 'teal' }) {
  const iconTones = {
    teal: 'bg-teal-50 text-teal-600',
    amber: 'bg-amber-50 text-amber-600',
    emerald: 'bg-emerald-50 text-emerald-600',
  }
  return (
    <div className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <span className={`rounded-xl p-2.5 ${iconTones[tone] ?? iconTones.teal}`}>
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-500">{title}</p>
        <p className="mt-0.5 text-3xl font-extrabold tabular-nums text-slate-900">
          {value}
        </p>
        <p className="mt-1 text-xs text-slate-500">{sub}</p>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Mastery distribution                                                */
/* ------------------------------------------------------------------ */

const DIST_BARS = [
  { key: 'mastered', tone: 'teal' },
  { key: 'learning', tone: 'amber' },
  { key: 'needs_revision', tone: 'rose' },
  { key: 'not_started', tone: 'slate' },
]

function MasteryDistribution({ topics, t }) {
  const total = topics.total ?? 0

  return (
    <Card icon={TrendingUp} title={t.dashboard.dist.title}>
      {total === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          {t.dashboard.dist.empty}
        </p>
      ) : (
        <div className="space-y-3">
          {DIST_BARS.map(({ key, tone }) => {
            const count = topics.mastery?.[key] ?? 0
            const width = pct(count, total) ?? 0
            return (
              <div key={key} className="grid grid-cols-[8rem_1fr_2.25rem] items-center gap-3">
                <span className="truncate text-xs font-medium text-slate-600">
                  {t.dashboard.dist.statuses[key]}
                </span>
                <ProgressBar value={width} tone={tone} />
                <span className="text-end text-xs font-bold tabular-nums text-slate-700">
                  {count}
                </span>
              </div>
            )
          })}
          <p className="pt-1 text-center text-xs text-slate-500">
            {fill(t.dashboard.dist.of, { total })}
          </p>
        </div>
      )}
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/* Revision queue                                                      */
/* ------------------------------------------------------------------ */

function RevisionQueue({ recommended, t }) {
  return (
    <Card icon={RefreshCcw} title={t.dashboard.queue.title}>
      <p className="mb-3 text-xs text-slate-500">{t.dashboard.queue.hint}</p>

      {recommended.length === 0 ? (
        <EmptyState icon={Sparkles} title={t.dashboard.queue.empty} />
      ) : (
        <ul className="divide-y divide-slate-100">
          {recommended.map((entry) => (
            <li
              key={entry.topic_id}
              className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 first:pt-1 last:pb-1"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-800">
                  <span className="ltr">{entry.title_en}</span>
                  {entry.title_ar && (
                    <span className="text-slate-400"> — {entry.title_ar}</span>
                  )}
                </p>
                <p className="text-xs text-slate-500">
                  {fill(t.dashboard.queue.attempts, { n: entry.attempts })}
                  {entry.last_score != null &&
                    ` · ${fill(t.dashboard.queue.lastScore, { score: entry.last_score })}`}
                </p>
              </div>
              <Badge tone={QUEUE_TONES[entry.mastery_status] ?? 'slate'}>
                {t.dashboard.dist.statuses[entry.mastery_status]}
              </Badge>
              <Link
                to="/flashcards"
                className={buttonClasses({ variant: 'secondary', size: 'sm' })}
              >
                {t.dashboard.queue.go}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/* Recent attempts                                                     */
/* ------------------------------------------------------------------ */

function RecentAttempts({ attempts, t, lang }) {
  return (
    <Card icon={Play} title={t.dashboard.recent.title}>
      {attempts.length === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          {t.dashboard.recent.empty}
        </p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {attempts.map((attempt) => (
            <li
              key={attempt.attempt_id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1 py-3 first:pt-1 last:pb-1"
            >
              <p className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-800">
                <span className="ltr">{attempt.topic_title_en}</span>
              </p>
              <span className="text-xs text-slate-400 tabular-nums">
                {attempt.total_questions} {t.dashboard.recent.attempts}
              </span>
              <span className="text-xs text-slate-400">
                {formatDateTime(attempt.completed_at, lang)}
              </span>
              <Badge tone={scoreTone(attempt.score)}>{attempt.score}%</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Dashboard() {
  const { t, lang } = useLanguage()
  const summary = useSummary()

  const data = summary.data

  if (summary.status === 'error') {
    return (
      <main className="mx-auto max-w-5xl space-y-6">
        <Header t={t} />
        <Banner tone="error">
          {t.dashboard.offline}
        </Banner>
        <button
          type="button"
          onClick={refreshSummary}
          className={buttonClasses({ variant: 'secondary' })}
        >
          {t.dashboard.retry}
        </button>
      </main>
    )
  }

  if (summary.loading || !data) {
    return (
      <main className="mx-auto max-w-5xl space-y-6">
        <Header t={t} />
        <div className="flex items-center gap-2 text-slate-500">
          <Spinner />
          {t.common.loading}
        </div>
      </main>
    )
  }

  const { files, topics } = data
  const totalFiles = files.total
  const publishedFiles = files.by_status?.published ?? 0
  const totalTopics = topics.total
  const masteredTopics = topics.mastery?.mastered ?? 0
  const needsRevision = topics.mastery?.needs_revision ?? 0
  const learningTopics = topics.mastery?.learning ?? 0
  const masteryPct = pct(masteredTopics, totalTopics)

  const isEmpty = totalFiles === 0 && totalTopics === 0

  return (
    <main className="mx-auto max-w-5xl space-y-6">
      <Header t={t} />

      {isEmpty && (
        <Card>
          <EmptyState
            icon={Upload}
            title={t.dashboard.emptyCta}
            action={
              <Link to="/library" className={buttonClasses({})}>
                <Upload className="h-4 w-4" aria-hidden="true" />
                {t.dashboard.emptyCta}
              </Link>
            }
          />
        </Card>
      )}

      {/* ----------------------------- metrics ----------------------------- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard
          icon={FileText}
          title={t.dashboard.metrics.lectures}
          value={totalFiles}
          sub={
            totalFiles > 0
              ? fill(t.dashboard.metrics.lecturesSub, {
                  published: publishedFiles,
                  total: totalFiles,
                })
              : t.dashboard.metrics.lecturesEmpty
          }
        />
        <MetricCard
          icon={TrendingUp}
          title={t.dashboard.metrics.mastery}
          value={masteryPct === null ? '—' : `${masteryPct}%`}
          sub={
            totalTopics > 0
              ? fill(t.dashboard.metrics.masterySub, {
                  mastered: masteredTopics,
                  total: totalTopics,
                })
              : t.dashboard.metrics.masteryEmpty
          }
          tone="emerald"
        />
        <MetricCard
          icon={TriangleAlert}
          title={t.dashboard.metrics.revise}
          value={needsRevision}
          sub={
            needsRevision > 0 || learningTopics > 0
              ? fill(t.dashboard.metrics.reviseSub, { learning: learningTopics })
              : t.dashboard.metrics.reviseAllGood
          }
          tone={needsRevision > 0 ? 'amber' : 'teal'}
        />
      </div>

      {/* --------------------------- quick actions --------------------------- */}
      <section aria-label={t.dashboard.quick.title}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Link to="/quiz" className={buttonClasses({ size: 'lg' })}>
            <Play className="h-4 w-4" aria-hidden="true" />
            {t.dashboard.quick.quiz}
          </Link>
          <Link to="/tutor" className={buttonClasses({ variant: 'secondary', size: 'lg' })}>
            <Sparkles className="h-4 w-4 text-teal-600" aria-hidden="true" />
            {t.dashboard.quick.tutor}
          </Link>
          <Link to="/library" className={buttonClasses({ variant: 'secondary', size: 'lg' })}>
            <Upload className="h-4 w-4 text-teal-600" aria-hidden="true" />
            {t.dashboard.quick.upload}
          </Link>
        </div>
      </section>

      {/* ------------------------------ lists ------------------------------ */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <MasteryDistribution topics={topics} t={t} />
        </div>
        <div className="lg:col-span-3">
          <RecentAttempts attempts={data.recent_attempts ?? []} t={t} lang={lang} />
        </div>
        <div className="lg:col-span-5">
          <RevisionQueue recommended={data.recommended ?? []} t={t} />
        </div>
      </div>
    </main>
  )
}

function Header({ t }) {
  return (
    <div>
      <h1 className="flex items-center gap-2.5 text-2xl font-extrabold text-slate-900">
        <BookOpen className="h-6 w-6 text-teal-600" aria-hidden="true" />
        {t.dashboard.title}
      </h1>
      <p className="mt-1 text-sm text-slate-500">{t.dashboard.subtitle}</p>
    </div>
  )
}
