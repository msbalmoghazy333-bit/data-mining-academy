/**
 * Shared UI primitives — calm academic styling, teal accents.
 * Everything uses logical properties so RTL/LTR flip automatically.
 */

import { useEffect } from 'react'
import { Loader2, TriangleAlert, X } from 'lucide-react'

/* ------------------------------------------------------------------ */
/* Button                                                              */
/* ------------------------------------------------------------------ */

const VARIANTS = {
  primary:
    'bg-teal-600 text-white shadow-sm hover:bg-teal-700 active:bg-teal-800 disabled:hover:bg-teal-600',
  secondary:
    'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  danger:
    'border border-red-200 bg-red-50 text-red-700 hover:bg-red-100',
}

const SIZES = {
  md: 'px-4 py-2 text-sm gap-2',
  sm: 'px-2.5 py-1.5 text-xs gap-1.5',
  lg: 'px-5 py-2.5 text-base gap-2.5',
}

export function buttonClasses({ variant = 'primary', size = 'md' } = {}) {
  return [
    'inline-flex items-center justify-center rounded-xl font-semibold',
    'transition-colors disabled:cursor-not-allowed disabled:opacity-60',
    VARIANTS[variant] ?? VARIANTS.primary,
    SIZES[size] ?? SIZES.md,
  ].join(' ')
}

export function Button({
  variant = 'primary',
  size = 'md',
  icon: Icon,
  loading = false,
  className = '',
  children,
  disabled,
  ...props
}) {
  return (
    <button
      className={`${buttonClasses({ variant, size })} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      )}
      {children}
    </button>
  )
}

/* ------------------------------------------------------------------ */
/* Surfaces                                                            */
/* ------------------------------------------------------------------ */

export function Card({ icon: Icon, title, actions, className = '', children }) {
  return (
    <section
      className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}
      aria-label={title}
    >
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-4">
          <h2 className="flex items-center gap-2 text-base font-bold text-slate-800">
            {Icon && <Icon className="h-4.5 w-4.5 text-teal-600" aria-hidden="true" />}
            {title}
          </h2>
          {actions}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  )
}

export function ProgressBar({ value, tone = 'teal', className = '' }) {
  const tones = {
    teal: 'bg-teal-600',
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-500',
    rose: 'bg-rose-400',
    slate: 'bg-slate-300',
  }
  return (
    <div
      className={`h-1.5 w-full overflow-hidden rounded-full bg-slate-100 ${className}`}
      role="progressbar"
      aria-valuenow={value ?? undefined}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${tones[tone] ?? tones.teal}`}
        style={{ width: `${Math.min(100, Math.max(0, value ?? 0))}%` }}
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Feedback                                                           */
/* ------------------------------------------------------------------ */

const TONES = {
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
  teal: 'bg-teal-50 text-teal-700 ring-teal-200',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-700 ring-amber-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
}

export function Badge({ tone = 'slate', children }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${TONES[tone] ?? TONES.slate}`}
    >
      {children}
    </span>
  )
}

const BANNER_TONES = {
  success: 'border-teal-200 bg-teal-50 text-teal-800',
  error: 'border-red-200 bg-red-50 text-red-700',
}

export function Banner({ tone = 'success', onDismiss, children }) {
  return (
    <div
      role="status"
      className={`flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm font-medium ${BANNER_TONES[tone] ?? BANNER_TONES.success}`}
    >
      <div className="min-w-0 flex items-start gap-2">
        {tone === 'error' && (
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        )}
        <span className="min-w-0 break-words">{children}</span>
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="dismiss"
          className="shrink-0 rounded-lg p-0.5 opacity-60 hover:opacity-100"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

export function EmptyState({ icon: Icon, title, hint, action }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      {Icon && (
        <div className="rounded-full bg-teal-50 p-3">
          <Icon className="h-6 w-6 text-teal-600" aria-hidden="true" />
        </div>
      )}
      <div>
        <p className="font-semibold text-slate-700">{title}</p>
        {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
      </div>
      {action}
    </div>
  )
}

export function Spinner({ className = 'h-5 w-5' }) {
  return <Loader2 className={`animate-spin text-teal-600 ${className}`} aria-hidden="true" />
}

/* ------------------------------------------------------------------ */
/* Modal                                                               */
/* ------------------------------------------------------------------ */

export function Modal({ open, onClose, title, children, footer, wide = false }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-6">
      <div
        className="absolute inset-0 bg-slate-900/50"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        className={`relative z-10 flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl ${
          wide ? 'sm:max-w-3xl' : 'sm:max-w-xl'
        }`}
      >
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <h3 className="text-base font-bold text-slate-900">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="close dialog"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {footer && (
          <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 px-5 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  )
}
