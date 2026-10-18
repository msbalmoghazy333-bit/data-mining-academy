/**
 * Course Library & Upload — the teacher's workflow screen.
 *
 * 1. Drag-and-drop upload zone with client-side validation mirroring the
 *    backend rules (allowed extensions + max size), then the upload API.
 * 2. Files table with lifecycle status badges and per-row actions.
 * 3. Review modal: full extracted text per page/slide + the generated draft
 *    summary, then "Approve & publish" — before anything enters the course.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Eye,
  FileText,
  RefreshCcw,
  Send,
  Sparkles,
  Trash2,
  TriangleAlert,
  Upload,
} from 'lucide-react'

import api from '../lib/api.js'
import { useLanguage } from '../lib/i18n.jsx'
import { fill, formatBytes, formatDateTime } from '../lib/format.js'
import { refreshSummary } from '../lib/summaryStore.js'
import {
  Badge,
  Banner,
  buttonClasses,
  Card,
  EmptyState,
  Modal,
  Button,
  Spinner,
} from '../components/ui.jsx'

/* Mirrors backend `Settings.ALLOWED_UPLOAD_TYPES` / `MAX_UPLOAD_SIZE_MB`. */
const ALLOWED_EXTENSIONS = ['.pdf', '.pptx', '.ppt', '.docx', '.txt', '.md']
const MAX_SIZE_MB = 50
const FILES_URL = '/v1/files'

/* ------------------------------------------------------------------ */
/* Status badges                                                       */
/* ------------------------------------------------------------------ */

const STATUS_META = {
  uploaded: { tone: 'slate' },
  processing: { tone: 'teal', pulse: true },
  ready_for_review: { tone: 'amber' },
  published: { tone: 'emerald' },
  failed: { tone: 'rose' },
}

function StatusBadge({ status, t }) {
  const meta = STATUS_META[status] ?? { tone: 'slate' }
  return (
    <Badge tone={meta.tone}>
      {meta.pulse && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-teal-500" aria-hidden="true" />
      )}
      {t.library.status[status] ?? status}
    </Badge>
  )
}

/* ------------------------------------------------------------------ */
/* Upload dropzone                                                     */
/* ------------------------------------------------------------------ */

function acceptsFile(name, size) {
  const lower = String(name).toLowerCase()
  const allowed = ALLOWED_EXTENSIONS.some((extension) => lower.endsWith(extension))
  if (!allowed) return 'wrongType'
  if (size > MAX_SIZE_MB * 1024 * 1024) return 'tooBig'
  return null
}

function Dropzone({ onFile, uploading, uploadingName, t }) {
  const inputRef = useRef(null)
  const dragDepth = useRef(0)
  const [dragging, setDragging] = useState(false)

  const openPicker = () => inputRef.current?.click()

  const handleDrop = (event) => {
    event.preventDefault()
    dragDepth.current = 0
    setDragging(false)
    const file = event.dataTransfer?.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-disabled={uploading}
      onClick={() => !uploading && openPicker()}
      onKeyDown={(event) => {
        if (!uploading && (event.key === 'Enter' || event.key === ' ')) openPicker()
      }}
      onDragOver={(event) => {
        event.preventDefault()
        if (!uploading) setDragging(true)
      }}
      onDragEnter={(event) => {
        event.preventDefault()
        if (!uploading) {
          dragDepth.current += 1
          setDragging(true)
        }
      }}
      onDragLeave={() => {
        dragDepth.current = Math.max(0, dragDepth.current - 1)
        if (dragDepth.current === 0) setDragging(false)
      }}
      onDrop={handleDrop}
      className={[
        'flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors',
        dragging ? 'border-teal-500 bg-teal-50' : 'border-slate-300 bg-white hover:border-teal-400',
        uploading && 'pointer-events-none opacity-70',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_EXTENSIONS.join(',')}
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) onFile(file)
        }}
      />
      {uploading ? (
        <>
          <Spinner />
          <p className="text-sm font-semibold text-teal-700">
            {fill(t.library.drop.uploading)}{' '}
            <span className="ltr">{uploadingName}</span>
          </p>
        </>
      ) : (
        <>
          <span className="rounded-full bg-teal-50 p-3">
            <Upload className="h-6 w-6 text-teal-600" aria-hidden="true" />
          </span>
          <p className="font-semibold text-slate-700">{t.library.drop.title}</p>
          <p className="text-xs text-slate-500">{fill(t.library.drop.hint, { mb: MAX_SIZE_MB })}</p>
        </>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Review modal                                                        */
/* ------------------------------------------------------------------ */

function StatChip({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-center">
      <p className="text-lg font-extrabold tabular-nums text-slate-900">{value}</p>
      <p className="text-[11px] font-medium text-slate-500">{label}</p>
    </div>
  )
}

/** Compact view of the staged draft (topics + objectives + counts). */
function DraftSection({ draft, t, lang }) {
  if (!draft) return null

  return (
    <section>
      <h4 className="mb-1 text-sm font-bold text-slate-800">
        {fill(t.library.review.draftTitle, { count: draft.topic_count })}
      </h4>
      {(draft.model || draft.generated_at) && (
        <p className="mb-3 text-[11px] text-slate-500">
          {fill(t.library.review.draftMeta, {
            model: draft.model,
            when: formatDateTime(draft.generated_at, lang),
          })}
        </p>
      )}
      <ul className="space-y-2">
        {draft.topics.map((topic, index) => (
          <li key={`${topic.title_en}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <details>
              <summary className="flex items-center justify-between gap-2 text-sm font-semibold text-slate-800">
                <span className="truncate">
                  <span className="ltr">{topic.title_en}</span>
                  {topic.title_ar && <span className="text-slate-400"> — {topic.title_ar}</span>}
                </span>
                <span className="shrink-0 text-[11px] font-medium text-slate-500 tabular-nums">
                  {topic.question_count} {t.library.review.questions} ·{' '}
                  {topic.flashcard_count} {t.library.review.cards}
                </span>
              </summary>
              <div className="mt-2 space-y-1.5 text-xs text-slate-600">
                {topic.objectives.length > 0 && (
                  <ul className="list-inside list-disc space-y-1">
                    {topic.objectives.map((objective, objectiveIndex) => (
                      <li key={objectiveIndex}>{objective}</li>
                    ))}
                  </ul>
                )}
                {topic.summary && (
                  <p className="rounded-lg bg-white p-2 leading-relaxed text-slate-600">
                    {topic.summary}
                  </p>
                )}
              </div>
            </details>
          </li>
        ))}
      </ul>
    </section>
  )
}

function ReviewModal({ file, onClose, onActionDone }) {
  const { t, lang } = useLanguage()
  const [preview, setPreview] = useState(null)
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState(null)
  const [publishResult, setPublishResult] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [status, setStatus] = useState(file.status)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [previewData, draftData] = await Promise.all([
          api.get(`${FILES_URL}/${file.id}/preview`),
          api.get(`${FILES_URL}/${file.id}/draft`),
        ])
        if (!cancelled) {
          setPreview(previewData)
          setDraft(draftData?.has_draft ? draftData : null)
        }
      } catch (loadError) {
        if (!cancelled) setError(loadError.message)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [file.id])

  const alreadyPublished = status === 'published'

  const generate = async () => {
    setGenerating(true)
    setError(null)
    try {
      await api.post(`${FILES_URL}/${file.id}/generate`, {})
      const draftData = await api.get(`${FILES_URL}/${file.id}/draft`)
      setDraft(draftData?.has_draft ? draftData : null)
      onActionDone?.()
    } catch (generateError) {
      setError(generateError.message)
    } finally {
      setGenerating(false)
    }
  }

  const publish = async () => {
    setPublishing(true)
    setError(null)
    try {
      const response = await api.post(`${FILES_URL}/${file.id}/publish`, {})
      setPublishResult(
        fill(t.library.review.publishedOk, {
          topics: response.topics_created + response.topics_matched,
          questions: response.questions_created,
          cards: response.flashcards_created,
        }),
      )
      setStatus('published')
      onActionDone?.()
    } catch (publishError) {
      setError(publishError.message)
    } finally {
      setPublishing(false)
    }
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={`${t.library.review.title} — ${file.filename}`}
      footer={
        <>
          {alreadyPublished && (
            <Badge tone="emerald">{t.library.status.published}</Badge>
          )}
          {!alreadyPublished && (
            <Button variant="secondary" loading={generating} onClick={generate} icon={Sparkles}>
              {t.library.actions.generate}
            </Button>
          )}
          {draft && (
            <Button loading={publishing} onClick={publish} icon={Send}>
              {alreadyPublished ? t.library.review.republish : t.library.review.publish}
            </Button>
          )}
          <Button variant="ghost" onClick={onClose}>
            {t.common.close}
          </Button>
        </>
      }
    >
      {(publishResult || error) && (
        <div className="mb-4 space-y-2">
          {publishResult && <Banner tone="success">{publishResult}</Banner>}
          {error && <Banner tone="error">{error}</Banner>}
        </div>
      )}

      {!preview ? (
        <div className="flex items-center gap-2 py-8 text-slate-500">
          <Spinner />
          {t.common.loading}
        </div>
      ) : (
        <div className="space-y-5">
          {/* ------------------------- stats ------------------------- */}
          <div className="grid grid-cols-3 gap-2">
            <StatChip
              label={t.library.review.stats.pages}
              value={preview.total_pages}
            />
            <StatChip
              label={t.library.review.stats.chunks}
              value={preview.total_chunks}
            />
            <StatChip
              label={t.library.review.stats.words}
              value={preview.total_words}
            />
          </div>

          {/* ------------------------- draft ------------------------- */}
          <DraftSection draft={draft} t={t} lang={lang} />
          {!draft && (
            <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
              {t.library.review.draftEmpty}
            </p>
          )}

          {/* ------------------------- pages ------------------------- */}
          <section>
            <h4 className="mb-2 text-sm font-bold text-slate-800">
              {fill(t.library.review.pagesTitle, { count: preview.total_pages })}
            </h4>
            <ul className="space-y-2">
              {preview.pages.map((page) => (
                <li key={page.page_number} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <details>
                    <summary className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-teal-700">
                        {t.library.review.page} <span className="tabular-nums">{page.page_number}</span>
                      </span>
                      <span className="text-[11px] text-slate-500 tabular-nums">
                        {page.word_count} {t.library.review.stats.words}
                      </span>
                    </summary>
                    <p className="mt-2 whitespace-pre-wrap rounded-lg bg-white p-2 text-xs leading-relaxed text-slate-600">
                      {page.full_text}
                    </p>
                  </details>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </Modal>
  )
}

/* ------------------------------------------------------------------ */
/* Delete confirmation                                                 */
/* ------------------------------------------------------------------ */

function DeleteConfirmation({ file, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const confirm = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.delete(`${FILES_URL}/${file.id}`)
      onDeleted(file)
    } catch (deleteError) {
      setError(deleteError.message)
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={t.library.confirmDelete.title}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            {t.common.cancel}
          </Button>
          <Button variant="danger" loading={busy} onClick={confirm} icon={Trash2}>
            {t.common.confirm}
          </Button>
        </>
      }
    >
      <p className="text-sm leading-relaxed text-slate-600">
        {fill(t.library.confirmDelete.body, { name: file.filename })}
      </p>
      {error && (
        <div className="mt-3">
          <Banner tone="error">{error}</Banner>
        </div>
      )}
    </Modal>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Library() {
  const { t, lang } = useLanguage()
  const [list, setList] = useState(null)
  const [error, setError] = useState(null)
  const [uploadingName, setUploadingName] = useState(null)
  const [uploadError, setUploadError] = useState(null)
  const [banner, setBanner] = useState(null)
  const [reviewFile, setReviewFile] = useState(null)
  const [deleteFile, setDeleteFile] = useState(null)
  const [rowBusy, setRowBusy] = useState({})

  const uploading = uploadingName !== null

  const load = useCallback(async ({ silent } = {}) => {
    if (!silent) setError(null)
    try {
      const data = await api.get(`${FILES_URL}?limit=50&offset=0`)
      setList(data)
    } catch (loadError) {
      if (!silent) setError(loadError)
    }
  }, [])

  useEffect(() => {
    // Deferred one tick so the fetch never runs synchronously inside the effect.
    const timer = setTimeout(() => load({ silent: true }), 0)
    return () => clearTimeout(timer)
  }, [load])

  // Poll while any file is mid-pipeline so status badges move on their own.
  useEffect(() => {
    if (!list?.items?.some((file) => file.status === 'processing')) return undefined
    const timer = setInterval(() => load({ silent: true }), 5000)
    return () => clearInterval(timer)
  }, [list, load])

  /* ------------------------------ upload ------------------------------ */

  const uploadFile = async (file) => {
    setUploadError(null)
    setBanner(null)

    const validation = acceptsFile(file.name, file.size)
    if (validation) {
      setUploadError(
        fill(validation === 'wrongType' ? t.library.drop.wrongType : t.library.drop.tooBig, {
          name: file.name,
          mb: MAX_SIZE_MB,
        }),
      )
      return
    }

    setUploadingName(file.name)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await api.upload(`${FILES_URL}/upload`, formData)
      setBanner({
        tone: 'success',
        message: fill(t.library.banner.uploaded, { name: file.name }),
      })
      await load({ silent: true })
      refreshSummary()
    } catch (uploadFailure) {
      setUploadError(uploadFailure.message)
    } finally {
      setUploadingName(null)
    }
  }

  /* --------------------------- row actions --------------------------- */

  const runAction = async (file, action) => {
    setRowBusy((previous) => ({ ...previous, [file.id]: action }))
    setBanner(null)
    try {
      const response = await api.post(`${FILES_URL}/${file.id}/${action}`, {})
      await load({ silent: true })
      return response
    } catch (actionError) {
      setBanner({ tone: 'error', message: actionError.message })
      await load({ silent: true })
      return null
    } finally {
      setRowBusy((previous) => ({ ...previous, [file.id]: null }))
    }
  }

  const generateFile = async (file) => {
    const response = await runAction(file, 'generate')
    if (response) {
      setBanner({
        tone: 'success',
        message: fill(t.library.banner.generated, {
          topics: response.topic_count,
          new: response.new_topics,
        }),
      })
    }
  }

  const publishFile = async (file) => {
    const response = await runAction(file, 'publish')
    if (response) {
      setBanner({
        tone: 'success',
        message: fill(t.library.banner.published, {
          name: file.filename,
          topics: response.topics_created + response.topics_matched,
          questions: response.questions_created,
          cards: response.flashcards_created,
        }),
      })
      refreshSummary()
    }
  }

  const retryFile = (file) => runAction(file, 'retry')

  const deleteDone = async (file) => {
    setDeleteFile(null)
    setBanner({ tone: 'success', message: fill(t.library.banner.deleted, { name: file.filename }) })
    await load({ silent: true })
    refreshSummary()
  }

  const reviewDone = async () => {
    await load({ silent: true })
    refreshSummary()
  }

  const rows = list?.items ?? []
  const sortedRows = useMemo(
    () =>
      [...(list?.items ?? [])].sort(
        (a, b) => new Date(b.upload_date) - new Date(a.upload_date),
      ),
    [list],
  )

  return (
    <main className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-extrabold text-slate-900">
          <FileText className="h-6 w-6 text-teal-600" aria-hidden="true" />
          {t.library.title}
        </h1>
        <p className="mt-1 text-sm text-slate-500">{t.library.subtitle}</p>
      </div>

      {banner && (
        <Banner tone={banner.tone} onDismiss={() => setBanner(null)}>
          {banner.message}
        </Banner>
      )}

      {uploadError && (
        <Banner tone="error" onDismiss={() => setUploadError(null)}>
          {uploadError}
        </Banner>
      )}

      {/* ------------------------------ dropzone ------------------------------ */}
      <Dropzone
        onFile={uploadFile}
        uploading={uploading}
        uploadingName={uploadingName}
        t={t}
      />

      {/* -------------------------------- table -------------------------------- */}
      <Card
        icon={FileText}
        title={list ? fill(t.library.table.total, { total: list.total }) : t.common.loading}
      >
        {error ? (
          <div className="space-y-3">
            <Banner tone="error">{t.common.offline}</Banner>
            <button
          type="button"
          onClick={() => load()}
          className={buttonClasses({ variant: 'secondary', size: 'sm' })}
        >
              {t.dashboard.retry}
            </button>
          </div>
        ) : !list ? (
          <div className="flex items-center gap-2 py-8 text-slate-500">
            <Spinner />
            {t.common.loading}
          </div>
        ) : rows.length === 0 ? (
          <EmptyState
            icon={FileText}
            title={t.library.table.empty}
            hint={t.library.table.emptyHint}
          />
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-start text-xs font-semibold text-slate-500">
                  <th className="pb-2 text-start">{t.library.table.name}</th>
                  <th className="pb-2 text-start">{t.library.table.status}</th>
                  <th className="pb-2 text-start">{t.library.table.pages}</th>
                  <th className="pb-2 text-start">{t.library.table.chunks}</th>
                  <th className="pb-2 text-start">{t.library.table.size}</th>
                  <th className="pb-2 text-start">{t.library.table.uploaded}</th>
                  <th className="pb-2 text-start">{t.library.table.actions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sortedRows.map((file) => {
                  const busy = rowBusy[file.id]
                  const showGenerate =
                    file.status === 'ready_for_review' || file.status === 'published'
                  const showPublish = Boolean(file.has_draft) && file.status === 'ready_for_review'
                  const showRetry = file.status === 'failed'

                  return (
                    <tr key={file.id} className="group">
                      <td className="py-3 pe-3">
                        <span className="ltr block max-w-[16rem] truncate font-medium text-slate-800" title={file.filename}>
                          {file.filename}
                        </span>
                        {file.error_message && (
                          <span className="mt-0.5 flex items-center gap-1 text-[11px] text-red-600">
                            <TriangleAlert className="h-3 w-3" aria-hidden="true" />
                            <span className="truncate">{file.error_message}</span>
                          </span>
                        )}
                      </td>
                      <td className="py-3 pe-3">
                        <StatusBadge status={file.status} t={t} />
                      </td>
                      <td className="py-3 pe-3 tabular-nums text-slate-600">
                        {file.page_count}
                      </td>
                      <td className="py-3 pe-3 tabular-nums text-slate-600">
                        {file.chunk_count}
                      </td>
                      <td className="py-3 pe-3 whitespace-nowrap text-slate-600">
                        {formatBytes(file.file_size)}
                      </td>
                      <td className="py-3 pe-3 whitespace-nowrap text-slate-500">
                        {formatDateTime(file.upload_date, lang)}
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setReviewFile(file)}
                            title={t.library.actions.preview}
                            className="rounded-lg p-2 text-slate-500 hover:bg-teal-50 hover:text-teal-700"
                          >
                            <Eye className="h-4 w-4" aria-hidden="true" />
                          </button>
                          {showGenerate && (
                            <button
                              type="button"
                              onClick={() => generateFile(file)}
                              disabled={Boolean(busy)}
                              title={t.library.actions.generate}
                              className="rounded-lg p-2 text-slate-500 hover:bg-teal-50 hover:text-teal-700 disabled:opacity-50"
                            >
                              {busy === 'generate' ? (
                                <Spinner className="h-4 w-4" />
                              ) : (
                                <Sparkles className="h-4 w-4" aria-hidden="true" />
                              )}
                            </button>
                          )}
                          {showPublish && (
                            <button
                              type="button"
                              onClick={() => publishFile(file)}
                              disabled={Boolean(busy)}
                              title={t.library.actions.publish}
                              className="rounded-lg p-2 text-slate-500 hover:bg-teal-50 hover:text-teal-700 disabled:opacity-50"
                            >
                              {busy === 'publish' ? (
                                <Spinner className="h-4 w-4" />
                              ) : (
                                <Send className="h-4 w-4" aria-hidden="true" />
                              )}
                            </button>
                          )}
                          {showRetry && (
                            <button
                              type="button"
                              onClick={() => retryFile(file)}
                              disabled={Boolean(busy)}
                              title={t.library.actions.retry}
                              className="rounded-lg p-2 text-slate-500 hover:bg-teal-50 hover:text-teal-700 disabled:opacity-50"
                            >
                              {busy === 'retry' ? (
                                <Spinner className="h-4 w-4" />
                              ) : (
                                <RefreshCcw className="h-4 w-4" aria-hidden="true" />
                              )}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => setDeleteFile(file)}
                            title={t.library.actions.del}
                            className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ------------------------------- modals ------------------------------- */}
      {reviewFile && (
        <ReviewModal
          file={reviewFile}
          onClose={() => setReviewFile(null)}
          onActionDone={reviewDone}
        />
      )}
      {deleteFile && (
        <DeleteConfirmation
          file={deleteFile}
          onClose={() => setDeleteFile(null)}
          onDeleted={deleteDone}
        />
      )}
    </main>
  )
}
