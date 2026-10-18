/**
 * A deliberately small Markdown renderer for lesson bodies.
 *
 * Lesson content is Arabic Markdown written by the LLM and the project ships
 * no Markdown dependency — so this module covers the subset the generator
 * actually emits and returns **React elements, never raw HTML** (no
 * `dangerouslySetInnerHTML`, nothing to sanitise): headings, paragraphs,
 * blockquotes, bullet/numbered lists (nested by indentation), fenced code,
 * tables, horizontal rules, and inline bold / italic / code / links.
 *
 * Anything unrecognised degrades to plain readable text instead of breaking
 * the page.
 */

import { useMemo } from 'react'

const HEADING = /^(#{1,6})\s+(.*)$/
const HORIZONTAL_RULE = /^(-{3,}|\*{3,}|_{3,})$/
const FENCE = /^```/
const BULLET = /^(\s*)[-*+]\s+(.*)$/
const NUMBERED = /^(\s*)(\d+)[.)]\s+(.*)$/
const QUOTE = /^\s*>\s?(.*)$/
const TABLE_ROW = /^\s*\|(.+)\|\s*$/
const TABLE_DIVIDER = /^\s*\|?[\s:|-]+\|?\s*$/
const LINK = /^\[([^\]]+)\]\(([^)\s]+)\)$/
const INLINE =
  /(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\)|\*[^*\n]+\*)/g

/** A table needs a `|---|` divider under its header row. */
function isTableDivider(line) {
  return TABLE_DIVIDER.test(line) && line.includes('-')
}

function splitRow(line) {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim())
}

function isBlockStart(line) {
  return (
    HEADING.test(line) ||
    FENCE.test(line.trim()) ||
    HORIZONTAL_RULE.test(line.trim()) ||
    TABLE_ROW.test(line)
  )
}

function parseBlocks(source) {
  const lines = String(source ?? '').replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]

    if (!line.trim()) {
      index += 1
      continue
    }

    // ---- fenced code -------------------------------------------------
    if (FENCE.test(line.trim())) {
      const language = line.trim().slice(3).trim()
      const body = []
      index += 1
      while (index < lines.length && !FENCE.test(lines[index].trim())) {
        body.push(lines[index])
        index += 1
      }
      index += 1 // closing fence (or end of input)
      blocks.push({ type: 'code', language, text: body.join('\n') })
      continue
    }

    // ---- heading -----------------------------------------------------
    const heading = HEADING.exec(line)
    if (heading) {
      blocks.push({
        type: 'heading',
        level: heading[1].length,
        text: heading[2].trim(),
      })
      index += 1
      continue
    }

    // ---- horizontal rule ---------------------------------------------
    if (HORIZONTAL_RULE.test(line.trim())) {
      blocks.push({ type: 'rule' })
      index += 1
      continue
    }

    // ---- table -------------------------------------------------------
    if (
      TABLE_ROW.test(line) &&
      index + 1 < lines.length &&
      isTableDivider(lines[index + 1])
    ) {
      const header = splitRow(line)
      index += 2
      const rows = []
      while (index < lines.length && TABLE_ROW.test(lines[index])) {
        rows.push(splitRow(lines[index]))
        index += 1
      }
      blocks.push({ type: 'table', header, rows })
      continue
    }

    // ---- blockquote --------------------------------------------------
    if (QUOTE.test(line)) {
      const quoted = []
      while (index < lines.length && QUOTE.test(lines[index])) {
        quoted.push(QUOTE.exec(lines[index])[1])
        index += 1
      }
      blocks.push({ type: 'quote', text: quoted.join(' ').trim() })
      continue
    }

    // ---- list --------------------------------------------------------
    if (BULLET.test(line) || NUMBERED.test(line)) {
      const ordered = NUMBERED.test(line)
      const items = []
      while (index < lines.length) {
        const match = ordered ? NUMBERED.exec(lines[index]) : BULLET.exec(lines[index])
        if (!match) break
        const indent = match[1].replace(/\t/g, '  ').length
        items.push({
          depth: Math.min(2, Math.floor(indent / 2)),
          text: (ordered ? match[3] : match[2]).trim(),
        })
        index += 1
      }
      blocks.push({ type: 'list', ordered, items })
      continue
    }

    // ---- paragraph ---------------------------------------------------
    const paragraph = []
    while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index])) {
      paragraph.push(lines[index].trim())
      index += 1
    }
    blocks.push({ type: 'paragraph', text: paragraph.join(' ') })
  }

  return blocks
}

/* ------------------------------------------------------------------ */
/* Inline rendering                                                    */
/* ------------------------------------------------------------------ */

const CODE_CLASS =
  'rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-700'

function renderInline(text) {
  const nodes = []
  let cursor = 0
  let match

  INLINE.lastIndex = 0

  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > cursor) nodes.push(text.slice(cursor, match.index))

    const token = match[0]
    const key = `inline-${match.index}`

    if (token.startsWith('`')) {
      nodes.push(
        <code key={key} dir="ltr" className={CODE_CLASS}>
          {token.slice(1, -1)}
        </code>,
      )
    } else if (token.startsWith('**') || token.startsWith('__')) {
      nodes.push(<strong key={key} className="font-bold">{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('[')) {
      const link = LINK.exec(token)
      if (link && /^https?:\/\//i.test(link[2])) {
        nodes.push(
          <a
            key={key}
            href={link[2]}
            target="_blank"
            rel="noreferrer noopener"
            className="font-semibold text-teal-700 underline"
          >
            {link[1]}
          </a>,
        )
      } else {
        // Unknown or unsafe target: keep the raw text, never a live link.
        nodes.push(token)
      }
    } else {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    }

    cursor = match.index + token.length
  }

  if (cursor < text.length) nodes.push(text.slice(cursor))

  return nodes
}

/* ------------------------------------------------------------------ */
/* Block rendering                                                     */
/* ------------------------------------------------------------------ */

const HEADING_CLASSES = {
  1: 'mt-8 mb-3 text-xl font-extrabold text-slate-900',
  2: 'mt-8 mb-3 text-lg font-bold text-slate-900',
  3: 'mt-6 mb-2 text-base font-bold text-slate-800',
  4: 'mt-5 mb-2 text-sm font-bold text-slate-800',
}

function renderBlock(block, index) {
  const key = `block-${index}`

  switch (block.type) {
    case 'heading': {
      const Tag = `h${Math.min(6, block.level + 1)}`
      return (
        <Tag key={key} className={HEADING_CLASSES[block.level] ?? HEADING_CLASSES[4]}>
          {renderInline(block.text)}
        </Tag>
      )
    }

    case 'code':
      return (
        <div key={key} className="my-4">
          {block.language && (
            <span className="ltr mb-1 inline-block text-[11px] font-semibold text-slate-400">
              {block.language}
            </span>
          )}
          <pre
            dir="ltr"
            className="overflow-x-auto rounded-xl bg-slate-900 px-4 py-3 text-start font-mono text-xs leading-relaxed text-slate-100"
          >
            <code>{block.text}</code>
          </pre>
        </div>
      )

    case 'quote':
      return (
        <blockquote
          key={key}
          className="my-4 rounded-xl border-s-4 border-teal-300 bg-teal-50/70 px-4 py-3 text-sm leading-relaxed text-slate-700"
        >
          {renderInline(block.text)}
        </blockquote>
      )

    case 'list': {
      const Tag = block.ordered ? 'ol' : 'ul'
      return (
        <Tag key={key} className="my-3 space-y-1.5">
          {block.items.map((item, itemIndex) => (
            <li
              key={`${key}-${itemIndex}`}
              className="flex gap-2 text-sm leading-relaxed text-slate-700"
              style={{ marginInlineStart: `${item.depth * 1.25}rem` }}
            >
              <span className="shrink-0 font-bold text-teal-600" aria-hidden="true">
                {block.ordered ? `${itemIndex + 1}.` : '•'}
              </span>
              <span className="min-w-0">{renderInline(item.text)}</span>
            </li>
          ))}
        </Tag>
      )
    }

    case 'table':
      return (
        <div key={key} className="my-4 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {block.header.map((cell, cellIndex) => (
                  <th
                    key={`${key}-h-${cellIndex}`}
                    className="border border-slate-200 bg-slate-50 px-3 py-2 text-start font-bold text-slate-700"
                  >
                    {renderInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={`${key}-r-${rowIndex}`}>
                  {block.header.map((_, cellIndex) => (
                    <td
                      key={`${key}-c-${rowIndex}-${cellIndex}`}
                      className="border border-slate-200 px-3 py-2 align-top text-slate-600"
                    >
                      {renderInline(row[cellIndex] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )

    case 'rule':
      return <hr key={key} className="my-6 border-slate-200" />

    default:
      return (
        <p key={key} className="my-3 text-sm leading-7 text-slate-700">
          {renderInline(block.text)}
        </p>
      )
  }
}

export default function Markdown({ source, className = '' }) {
  const blocks = useMemo(() => parseBlocks(source), [source])

  return <div className={className}>{blocks.map((block, index) => renderBlock(block, index))}</div>
}
