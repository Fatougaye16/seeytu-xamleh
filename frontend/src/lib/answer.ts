/**
 * Turns the model's answer (light markdown + [n] citations) into blocks Vue can render
 * without v-html, so model output can never inject markup.
 */
export type Segment =
  | { kind: 'text'; text: string }
  | { kind: 'bold'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'cite'; n: number }

export type Block =
  | { type: 'heading'; segments: Segment[] }
  | { type: 'paragraph'; segments: Segment[] }
  | { type: 'list'; ordered: boolean; items: Segment[][] }

// **bold** | `code` | [1] / [1, 2] / [1][2]
const INLINE = /\*\*(.+?)\*\*|`([^`]+)`|\[(\d+(?:\s*,\s*\d+)*)\]/g

export function parseInline(text: string): Segment[] {
  const out: Segment[] = []
  let last = 0
  for (const m of text.matchAll(INLINE)) {
    const idx = m.index ?? 0
    if (idx > last) out.push({ kind: 'text', text: text.slice(last, idx) })
    if (m[1] !== undefined) out.push({ kind: 'bold', text: m[1] })
    else if (m[2] !== undefined) out.push({ kind: 'code', text: m[2] })
    else if (m[3] !== undefined) {
      for (const n of m[3].split(',')) out.push({ kind: 'cite', n: Number(n.trim()) })
    }
    last = idx + m[0].length
  }
  if (last < text.length) out.push({ kind: 'text', text: text.slice(last) })
  return out
}

const HEADING = /^#{1,6}\s+(.*)$/
const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/

export function parseAnswer(answer: string): Block[] {
  const blocks: Block[] = []
  let paragraph: string[] = []
  let list: { ordered: boolean; items: string[] } | null = null

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', segments: parseInline(paragraph.join(' ')) })
    paragraph = []
  }
  const flushList = () => {
    if (list) blocks.push({ type: 'list', ordered: list.ordered, items: list.items.map(parseInline) })
    list = null
  }

  for (const rawLine of answer.replace(/\r\n/g, '\n').split('\n')) {
    const line = rawLine.trimEnd()
    if (!line.trim()) {
      flushParagraph()
      flushList()
      continue
    }
    const heading = line.match(HEADING)
    const bullet = line.match(BULLET)
    const numbered = line.match(NUMBERED)

    if (heading) {
      flushParagraph()
      flushList()
      blocks.push({ type: 'heading', segments: parseInline(heading[1]) })
    } else if (bullet || numbered) {
      flushParagraph()
      const ordered = Boolean(numbered)
      if (list && list.ordered !== ordered) flushList()
      list ??= { ordered, items: [] }
      list.items.push((bullet ?? numbered)![1])
    } else if (list && /^\s{2,}/.test(rawLine)) {
      list.items[list.items.length - 1] += ` ${line.trim()}` // continuation of a list item
    } else {
      flushList()
      paragraph.push(line.trim())
    }
  }
  flushParagraph()
  flushList()
  return blocks
}

/** Plain text with a numbered source list, for "Copy with sources". */
export function answerToPlainText(
  answer: string,
  sources: { number: number; title: string | null; url?: string | null; doi?: string | null }[],
): string {
  const refs = sources
    .map((s) => `[${s.number}] ${s.title ?? 'Untitled'}${s.doi || s.url ? ` — ${s.doi ?? s.url}` : ''}`)
    .join('\n')
  return refs ? `${answer.trim()}\n\nSources\n${refs}` : answer.trim()
}
