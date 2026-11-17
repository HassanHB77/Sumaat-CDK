/**
 * The AI assistant's reply stream (Server-Sent Events from agent/main.py): one JSON event per "data:" line,
 * events separated by a blank line. Network chunks can end anywhere, so parseSse keeps the unfinished tail.
 */
import type { CartDraft } from '../cart/cartLogic'

export type ChatErrorCode = 'quota_exceeded' | 'not_customer' | 'not_owner' | 'invalid_message' | 'busy' | 'failed' | 'network'

export type ChatEvent =
  | { type: 'quota'; left: number }
  | { type: 'status'; tool: string }
  | { type: 'text'; delta: string }
  | ({ type: 'draft' } & CartDraft)
  | { type: 'blocked' }
  | { type: 'error'; code: ChatErrorCode }
  | { type: 'done' }

const KNOWN = new Set(['quota', 'status', 'text', 'draft', 'blocked', 'error', 'done'])

/** Split a buffer into complete events + the unfinished rest (to prepend to the next chunk). */
export function parseSse(buffer: string): { events: ChatEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  const events: ChatEvent[] = []
  for (const block of blocks) {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
    if (!data) continue
    try {
      const e = JSON.parse(data)
      if (e && typeof e === 'object' && KNOWN.has(e.type)) events.push(e as ChatEvent)
    } catch {
      /* not JSON: ignore */
    }
  }
  return { events, rest }
}
