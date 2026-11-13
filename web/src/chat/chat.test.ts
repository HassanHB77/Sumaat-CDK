import { describe, expect, it, vi } from 'vitest'
import { sendChat, SESSION_HEADER } from './chatClient'
import { chatReducer, emptyChat, IDLE_MS, newSessionId, restoreChat, type ChatState } from './chatState'
import { parseSse, type ChatEvent } from './chatStream'

const DRAFT = {
  restaurant: { id: 'r2', name: 'Mubarraz Dates & Coffee', nameAr: 'تمر وقهوة المبرز' },
  lines: [{ itemId: 'k', name: 'Kleija', nameAr: 'كليجا', priceHalalas: 1500, qty: 2 }],
  totalHalalas: 3000,
}

describe('parseSse', () => {
  it('reads complete events and keeps the unfinished tail', () => {
    const { events, rest } = parseSse('data: {"type":"quota","left":9}\n\ndata: {"type":"text","delta":"Hi"}\n\ndata: {"ty')
    expect(events).toEqual([{ type: 'quota', left: 9 }, { type: 'text', delta: 'Hi' }])
    expect(rest).toBe('data: {"ty')
  })

  it('joins chunks split anywhere', () => {
    const full = 'data: {"type":"text","delta":"مرحبا"}\n\ndata: {"type":"done"}\n\n'
    let buf = ''
    const got: ChatEvent[] = []
    for (const ch of full) {
      const r = parseSse(buf + ch)
      got.push(...r.events)
      buf = r.rest
    }
    expect(got).toEqual([{ type: 'text', delta: 'مرحبا' }, { type: 'done' }])
  })

  it('ignores junk, unknown types and handles CRLF', () => {
    const { events } = parseSse(': ping\r\n\r\ndata: not json\n\ndata: {"type":"weird"}\n\ndata: {"type":"blocked"}\r\n\r\n')
    expect(events).toEqual([{ type: 'blocked' }])
  })
})

describe('chatReducer', () => {
  const sent = (): ChatState => chatReducer(emptyChat(1000, 's1'), { type: 'send', text: 'veg?', now: 2000 })
  const run = (events: ChatEvent[], s = sent()) => events.reduce((st, event) => chatReducer(st, { type: 'event', event }), s)

  it('send adds the question and a waiting reply', () => {
    const s = sent()
    expect(s.sending).toBe(true)
    expect(s.lastActive).toBe(2000)
    expect(s.messages).toEqual([{ role: 'user', text: 'veg?' }, { role: 'assistant', text: '', done: false }])
  })

  it('quota, status, text, draft, done', () => {
    const s = run([
      { type: 'quota', left: 7 },
      { type: 'status', tool: 'search_dishes' },
      { type: 'text', delta: 'Here ' },
      { type: 'text', delta: 'you go' },
      { type: 'draft', ...DRAFT },
      { type: 'done' },
    ])
    expect(s.left).toBe(7)
    expect(s.sending).toBe(false)
    expect(s.messages[1]).toEqual({ role: 'assistant', text: 'Here you go', status: undefined, draft: DRAFT, done: true })
  })

  it('status shows while waiting, text clears it', () => {
    const waiting = run([{ type: 'status', tool: 'search_dishes' }])
    expect(waiting.messages[1]).toMatchObject({ status: 'search_dishes', done: false })
    expect(run([{ type: 'text', delta: 'x' }], waiting).messages[1]).toMatchObject({ status: undefined })
  })

  it('blocked hides any text and draft', () => {
    const s = run([{ type: 'text', delta: 'partial' }, { type: 'draft', ...DRAFT }, { type: 'blocked' }, { type: 'done' }])
    expect(s.messages[1]).toMatchObject({ text: '', blocked: true, done: true })
    expect((s.messages[1] as any).draft).toBeUndefined()
  })

  it('quota_exceeded sets 0 left; other errors keep the count', () => {
    expect(run([{ type: 'quota', left: 0 }, { type: 'error', code: 'quota_exceeded' }]).left).toBe(0)
    const busy = run([{ type: 'quota', left: 4 }, { type: 'error', code: 'busy' }])
    expect(busy.left).toBe(4)
    expect(busy.sending).toBe(false)
    expect(busy.messages[1]).toMatchObject({ error: 'busy', done: true })
  })

  it('network error ends the reply', () => {
    const s = chatReducer(sent(), { type: 'networkError' })
    expect(s.sending).toBe(false)
    expect(s.messages[1]).toMatchObject({ error: 'network', done: true })
  })

  it('draftAdded marks only that reply', () => {
    const s = chatReducer(run([{ type: 'draft', ...DRAFT }, { type: 'done' }]), { type: 'draftAdded', index: 1 })
    expect(s.messages[1]).toMatchObject({ added: true })
    expect(chatReducer(s, { type: 'draftAdded', index: 0 })).toBe(s) // a user message: no change
  })

  it('reset starts a new chat', () => {
    const s = chatReducer(run([{ type: 'done' }]), { type: 'reset', sessionId: 's2', now: 5000 })
    expect(s).toEqual(emptyChat(5000, 's2'))
  })
})

describe('session', () => {
  it('session ids are long enough for AgentCore and unique', () => {
    const a = newSessionId()
    expect(a.length).toBeGreaterThanOrEqual(33)
    expect(newSessionId()).not.toBe(a)
  })

  it('restores a recent chat and finishes an interrupted reply', () => {
    const saved = JSON.stringify({
      sessionId: 's1',
      lastActive: 1000,
      messages: [{ role: 'user', text: 'hi' }, { role: 'assistant', text: '', done: false }],
    })
    const s = restoreChat(saved, 1000 + IDLE_MS - 1)
    expect(s.sessionId).toBe('s1')
    expect(s.sending).toBe(false)
    expect(s.messages[1]).toMatchObject({ error: 'network', done: true })
  })

  it('starts fresh after 15 idle minutes or broken storage', () => {
    const saved = JSON.stringify({ sessionId: 's1', lastActive: 1000, messages: [{ role: 'user', text: 'hi' }] })
    expect(restoreChat(saved, 1000 + IDLE_MS).messages).toEqual([])
    expect(restoreChat('{nope', 5).messages).toEqual([])
    expect(restoreChat(null, 5).sessionId).not.toBe('s1')
  })
})

describe('sendChat', () => {
  const stream = (text: string, status = 200) => {
    const bytes = new TextEncoder().encode(text)
    const body = new ReadableStream({
      start(c) {
        c.enqueue(bytes.slice(0, 10)) // split mid-event
        c.enqueue(bytes.slice(10))
        c.close()
      },
    })
    return new Response(body, { status })
  }
  const req = { path: '/agent/chat', message: 'hi', sessionId: 'sess-123', lang: 'ar' as const, spot: { lat: 25.38, lng: 49.588 } }

  it('posts with the access token and session id, and streams events', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(stream('data: {"type":"quota","left":9}\n\ndata: {"type":"done"}\n\n'))
    const events: ChatEvent[] = []
    await sendChat(req, (e) => events.push(e), { fetchImpl, getAccessToken: async () => 'tok' })
    const [url, init] = fetchImpl.mock.calls[0]
    expect(url).toBe('/agent/chat')
    expect(init.headers.Authorization).toBe('Bearer tok')
    expect(init.headers[SESSION_HEADER]).toBe('sess-123')
    expect(JSON.parse(init.body)).toEqual({ message: 'hi', lang: 'ar', lat: 25.38, lng: 49.588 })
    expect(events).toEqual([{ type: 'quota', left: 9 }, { type: 'done' }])
  })

  it('refreshes the token once on 401', async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(new Response('', { status: 401 })).mockResolvedValueOnce(stream('data: {"type":"done"}\n\n'))
    const getAccessToken = vi.fn().mockResolvedValueOnce('old').mockResolvedValueOnce('new')
    const events: ChatEvent[] = []
    await sendChat(req, (e) => events.push(e), { fetchImpl, getAccessToken })
    expect(getAccessToken).toHaveBeenLastCalledWith(true)
    expect(fetchImpl.mock.calls[1][1].headers.Authorization).toBe('Bearer new')
    expect(events).toEqual([{ type: 'done' }])
  })

  it('maps HTTP failures to error events', async () => {
    for (const [status, code] of [[401, 'not_customer'], [500, 'failed'], [429, 'busy']] as const) {
      const events: ChatEvent[] = []
      await sendChat(req, (e) => events.push(e), { fetchImpl: vi.fn().mockResolvedValue(new Response('', { status })), getAccessToken: async () => 't' })
      expect(events).toEqual([{ type: 'error', code }])
    }
  })

  it('a stream cut short ends with failed', async () => {
    const events: ChatEvent[] = []
    await sendChat(req, (e) => events.push(e), { fetchImpl: vi.fn().mockResolvedValue(stream('data: {"type":"quota","left":3}\n\n')), getAccessToken: async () => 't' })
    expect(events).toEqual([{ type: 'quota', left: 3 }, { type: 'error', code: 'failed' }])
  })
})
