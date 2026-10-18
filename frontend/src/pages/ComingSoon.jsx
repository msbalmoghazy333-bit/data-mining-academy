/**
 * Placeholder view for the last feature screen still missing from the UI
 * (flashcards). Honest about what exists: it lists the backend endpoints the
 * screen will be wired to.
 */

import { Link } from 'react-router-dom'
import { Clock, TriangleAlert } from 'lucide-react'

import { useLanguage } from '../lib/i18n.jsx'
import { buttonClasses, Card } from '../components/ui.jsx'

/* Endpoint chips shown per view — `ltr` so slugs read correctly in RTL. */
const ENDPOINTS = {
  flashcards: ['GET /v1/flashcards', 'POST /v1/flashcards/{id}/confidence'],
}

export default function ComingSoon({ view }) {
  const { t } = useLanguage()
  const copy = t.placeholder[view]

  const icon = (
    <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-50">
      <Clock className="h-7 w-7 text-teal-600" aria-hidden="true" />
    </div>
  )

  return (
    <main className="mx-auto max-w-3xl space-y-6">
      <Card>
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          {icon}
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900">{copy.title}</h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">
              {copy.desc}
            </p>
          </div>
          <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700 ring-1 ring-amber-200">
            {t.common.soon} — {t.placeholder.eta}
          </span>
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-700">
          <TriangleAlert className="h-4 w-4 text-slate-400" aria-hidden="true" />
          {t.placeholder.poweredBy}
        </h2>
        <div className="flex flex-wrap gap-2">
          {(ENDPOINTS[view] ?? []).map((endpoint) => (
            <code
              key={endpoint}
              className="ltr rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-600"
            >
              {endpoint}
            </code>
          ))}
        </div>
        <Link to="/" className={`${buttonClasses({ variant: 'secondary' })} mt-4`}>
          {t.placeholder.back}
        </Link>
      </Card>
    </main>
  )
}
