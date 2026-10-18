/**
 * AI Tutor — the chat screen over `POST /api/v1/tutor/chat`.
 *
 * The backend does the heavy lifting (retrieval over published chunks, RAG
 * generation, citation verification). Here we:
 *  - render inline citation markers ("[file — pages N]") found in the reply
 *    as chips, in addition to the verified citation list,
 *  - keep a conversation transcript and replay the last turns as `history`,
 *  - offer the four explanation-depth levels accepted by the endpoint,
 *  - map every API failure code to a clear Arabic/English guidance message.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Eraser,
  FileText,
  Layers,
  Send,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'

import api from '../lib/api.js'
import { useLanguage } from '../lib/i18n.jsx'
import { fill } from '../lib/format.js'
import { Badge, Spinner } from '../components/ui.jsx'

const TUTOR_URL = '/v1/tutor/chat'
const MAX_QUESTION = 2000 // mirrors TutorChatRequest.message
const MAX_HISTORY = 24 // mirrors TutorChatRequest.history

const LEVELS = ['simple', 'normal', 'advanced', 'exam_prep']

/* Matches "[filename — صفحة 4]" / "[file.pdf - page 4]" markers the
   backend guarantees are real (fabricated ones are dropped server-side). */
const CITATION_SOURCE = '\\[([^\\]]*?)\\s*[—–-]\\s*(?:صفحة|page)\\s*(\\d+)\\s*\\]'

/* ------------------------------------------------------------------ */
/* Transcript pieces                                                   */
/* ------------------------------------------------------------------ */

/** Render reply text, converting citation markers into inline chips. */
function InlineReply({ reply }) {
  const citationRe = new RegExp(CITATION_SOURCE, 'g') // fresh instance per render
  const parts = []
  let cursor = 0
  let key = 0
  let match

  while ((match = citationRe.exec(reply))) {
    if (match.index > cursor) {
      parts.push(<span key={key++}>{reply.slice(cursor, match.index)}</span>)
    }
    parts.push(
      <span
        key={key++}
        className="mx-0.5 inline-flex translate-y-0.5 items-center gap-1 rounded-md bg-teal-50 px-1.5 py-0 align-middle text-[0.7rem] font-semibold text-teal-700 ring-1 ring-teal-200"
        title={`${match[1]} · ${match[2]}`}
      >
        <FileText className="h-3 w-3" aria-hidden="true" />
        <span className="ltr max-w-[10rem] truncate">{match[1]}</span>
        <span className="tabular-nums">{match[2]}</span>
      </span>,
    )
    cursor = match.index + match[0].length
  }
  if (cursor < reply.length) parts.push(<span key={key++}>{reply.slice(cursor)}</span>)

  return <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{parts}</p>
}

function TypingBubble() {
  return (
    <div className="flex items-center gap-1.5 rounded-2xl border border-slate-200 bg-white px-4 py-3 self-start">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          style={{ animationDelay: `${delay}ms` }}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-teal-500"
          aria-hidden="true"
        />
      ))}
    </div>
  )
}

function UserBubble({ text }) {
  return (
    <div className="self-end max-w-[85%] rounded-2xl rounded-ee-md bg-teal-600 px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm">
      {text}
    </div>
  )
}

function TutorBubble({ turn, t }) {
  return (
    <div className="self-start max-w-[92%] space-y-2">
      <div className="rounded-2xl rounded-es-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <InlineReply reply={turn.reply} />
      </div>

      {turn.citations.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-1">
          <span className="text-[11px] font-semibold text-slate-400">
            {t.tutor.message.citations}:
          </span>
          {turn.citations.map((citation) => (
            <span
              key={`${citation.filename}-${citation.page}`}
              className="inline-flex items-center gap-1 rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200"
              title={`${citation.filename} · ${citation.page}`}
            >
              <FileText className="h-3 w-3 text-teal-600" aria-hidden="true" />
              <span className="ltr max-w-[9rem] truncate">{citation.filename}</span>
              <span className="tabular-nums text-slate-400">· {citation.page}</span>
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 px-1 text-[11px] text-slate-400">
        {turn.usedIndex ? (
          <>
            <span className="ltr">{turn.model}</span>
            <span aria-hidden="true">·</span>
            <span>{fill(t.tutor.message.retrieved, { n: turn.retrieved })}</span>
          </>
        ) : (
          <span className="flex items-center gap-1 text-amber-600">
            <TriangleAlert className="h-3 w-3" aria-hidden="true" />
            {t.tutor.message.noIndex}
          </span>
        )}
      </div>
    </div>
  )
}

function ErrorBubble({ text }) {
  return (
    <div className="self-start max-w-[92%] flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      {text}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Composer                                                            */
/* ------------------------------------------------------------------ */

function Composer({ value, onChange, onSend, sending, t }) {
  const textareaRef = useRef(null)

  // Auto-grow up to ~6 rows.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 9 * 1.75 * 16)}px`
  }, [value])

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        onSend()
      }}
      className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm"
    >
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value.slice(0, MAX_QUESTION))}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSend()
            }
          }}
          placeholder={t.tutor.composer.placeholder}
          className="min-w-0 flex-1 resize-none rounded-xl border-0 bg-slate-50 px-3 py-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-teal-500 disabled:opacity-60"
          disabled={sending}
          dir="auto"
        />
        <button
          type="submit"
          disabled={sending || value.trim().length < 2}
          aria-label={t.tutor.composer.send}
          title={t.tutor.composer.send}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white shadow-sm transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {sending ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
      <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-slate-400">
        <span>{t.tutor.composer.hint}</span>
        <span className="tabular-nums" dir="ltr">
          {fill(t.tutor.composer.maxChars, { n: value.length, max: MAX_QUESTION })}
        </span>
      </div>
    </form>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Tutor() {
  const { t } = useLanguage()

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [level, setLevel] = useState(() => {
    try {
      const stored = window.localStorage.getItem('dma-tutor-level')
      return LEVELS.includes(stored) ? stored : 'normal'
    } catch {
      return 'normal'
    }
  })

  const transcriptRef = useRef(null)
  const isEmpty = messages.length === 0

  // Follow the newest message (both directions: bottom-anchored scroll).
  useEffect(() => {
    const el = transcriptRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, sending])

  const setLevelStored = (next) => {
    setLevel(next)
    try {
      window.localStorage.setItem('dma-tutor-level', next)
    } catch {
      /* ignore */
    }
  }

  const historyForApi = useMemo(
    () =>
      messages
        .filter((turn) => turn.role !== 'error')
        .slice(-MAX_HISTORY)
        .map((turn) =>
          turn.role === 'user'
            ? { role: 'user', content: turn.text }
            : { role: 'assistant', content: turn.reply },
        ),
    [messages],
  )

  const send = async (rawText) => {
    const text = (rawText ?? input).trim()
    if (!text || sending || text.length < 2) return

    const history = historyForApi // computed before adding the current turn
    setMessages((previous) => [...previous, { role: 'user', text }])
    setInput('')
    setSending(true)

    try {
      const response = await api.post(TUTOR_URL, {
        message: text,
        history,
        difficulty_level: level,
      })
      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          reply: response.reply,
          citations: response.citations ?? [],
          retrieved: response.retrieved ?? 0,
          model: response.model ?? '',
          usedIndex: Boolean(response.used_index),
        },
      ])
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        { role: 'error', text: errorForStatus(error, t) },
      ])
    } finally {
      setSending(false)
    }
  }

  const clearChat = () => {
    setMessages([])
    setInput('')
  }

  return (
    <main className="mx-auto flex h-[calc(100dvh-14.5rem)] min-h-[520px] w-full max-w-3xl flex-col gap-4 lg:h-[calc(100dvh-13rem)]">
      {/* ------------------------------ header ------------------------------ */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-extrabold text-slate-900">
            <Sparkles className="h-6 w-6 text-teal-600" aria-hidden="true" />
            {t.tutor.title}
          </h1>
          <p className="mt-1 max-w-xl text-sm text-slate-500">{t.tutor.subtitle}</p>
        </div>
        {!isEmpty && (
          <button
            type="button"
            onClick={clearChat}
            title={t.tutor.actions.clear}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm hover:bg-slate-50 hover:text-red-600"
          >
            <Eraser className="h-3.5 w-3.5" aria-hidden="true" />
            {t.tutor.actions.clear}
          </button>
        )}
      </div>

      {/* -------------------------- level selector -------------------------- */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-500">
          <Layers className="h-3.5 w-3.5 text-teal-600" aria-hidden="true" />
          {t.tutor.levelLabel}
        </span>
        <div className="flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1">
          {LEVELS.map((levelKey) => (
            <button
              key={levelKey}
              type="button"
              onClick={() => setLevelStored(levelKey)}
              className={[
                'rounded-lg px-3 py-1 text-xs font-semibold transition-colors',
                level === levelKey
                  ? 'bg-white text-teal-700 shadow-sm'
                  : 'text-slate-500 hover:text-slate-800',
              ].join(' ')}
            >
              {t.tutor.levels[levelKey]}
            </button>
          ))}
        </div>
        <Badge tone="teal">{t.tutor.badge}</Badge>
      </div>

      {/* ---------------------------- transcript ---------------------------- */}
      <div
        ref={transcriptRef}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50 p-4"
        aria-live="polite"
      >
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
            <div className="rounded-2xl bg-teal-50 p-4">
              <Sparkles className="h-7 w-7 text-teal-600" aria-hidden="true" />
            </div>
            <div>
              <p className="font-bold text-slate-800">{t.tutor.empty.title}</p>
              <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500">
                {t.tutor.empty.desc}
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-2">
              {t.tutor.empty.samples.map((sample) => (
                <button
                  key={sample}
                  type="button"
                  onClick={() => send(sample)}
                  className="rounded-full border border-teal-200 bg-white px-3.5 py-1.5 text-xs font-medium text-teal-700 shadow-sm transition-colors hover:bg-teal-50"
                  dir="auto"
                >
                  {sample}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((turn, index) =>
            turn.role === 'user' ? (
              <UserBubble key={index} text={turn.text} />
            ) : turn.role === 'error' ? (
              <ErrorBubble key={index} text={turn.text} />
            ) : (
              <TutorBubble key={index} turn={turn} t={t} />
            ),
          )
        )}
        {sending && <TypingBubble />}
      </div>

      {/* ------------------------------ composer ------------------------------ */}
      <Composer
        value={input}
        onChange={setInput}
        onSend={() => send()}
        sending={sending}
        t={t}
      />
    </main>
  )
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function errorForStatus(error, t) {
  const status = error?.status ?? 0
  if (status === 0) return t.tutor.errors.offline
  if (status === 409) return t.tutor.errors.noKey
  if (status === 503) return t.tutor.errors.embeddings
  if (status === 502) return t.tutor.errors.unavailable
  if (status === 422) return t.tutor.errors.invalid
  return error?.message ?? t.tutor.errors.unavailable
}
