/** Small formatting helpers shared across pages. */

/** Interpolate `{key}` placeholders inside a dictionary string. */
export function fill(template, vars) {
  if (!template) return ''
  return template.replace(/\{(\w+)\}/g, (_, key) => String(vars?.[key] ?? ''))
}

/** Human file size — Latin units regardless of UI language. */
export function formatBytes(bytes) {
  if (bytes === null || bytes === undefined) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = Number(bytes)
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const text = value >= 100 ? Math.round(value).toString() : value.toFixed(1)
  return `${text} ${units[unit]}`
}

/** Compact date-time; Arabic gets Egyptian month names with Latin digits. */
export function formatDateTime(iso, lang = 'ar') {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const locale = lang === 'ar' ? 'ar-EG-u-nu-latn' : 'en-GB'
  return date.toLocaleString(locale, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Integer percentage, or null when there is nothing to divide. */
export function pct(part, total) {
  if (!total || total <= 0) return null
  return Math.round((part / total) * 100)
}
