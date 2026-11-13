/**
 * Chat panel state (pure reducer + sessionStorage). Replies are checked by the guardrail before they are shown,
 * so text usually arrives in one piece; "status" events fill the wait ("Searching dishes...").
 */
import type { CartDraft } from '../cart/cartLogic'
import type { ChatErrorCode, ChatEvent } from './chatStream'

export const MAX_MESSAGE = 500
export const IDLE_MS = 15 * 60 * 1000 // the server forgets a chat after 15 idle minutes, so do we
const STORAGE_KEY = 'sumaat.chat'

export type ChatMessage =
  | { role: 'user'; text: string }
  | {
      role: 'assistant'
      text: string
      status?: string // tool currently working (while waiting)
      draft?: CartDraft
      added?: boolean // the draft was added to the cart
      blocked?: boolean
      error?: ChatErrorCode
      done: boolean
    }

export type ChatState = {
  sessionId: string
  messages: ChatMessage[]
  left: number | null // messages left today (null = not known yet)
  sending: boolean
  lastActive: number // ms since epoch
}

export type ChatAction =
  | { type: 'send'; text: string; now: number }
  | { type: 'event'; event: ChatEvent }
  | { type: 'networkError' }
  | { type: 'quotaLoaded'; left: number }
  | { type: 'draftAdded'; index: number }
  | { type: 'reset'; sessionId: string; now: number }

/** AgentCore wants a session id of at least 33 characters. */
export function newSessionId(): string {
  const uuid = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`
  return `chat-${uuid}-${Date.now().toString(36)}`
}

export function emptyChat(now: number, sessionId = newSessionId()): ChatState {
  return { sessionId, messages: [], left: null, sending: false, lastActive: now }
}

function updateLast(state: ChatState, change: (m: Extract<ChatMessage, { role: 'assistant' }>) => ChatMessage): ChatState {
  const i = state.messages.length - 1
  const last = state.messages[i]
  if (!last || last.role !== 'assistant') return state
  const messages = state.messages.slice()
  messages[i] = change(last)
  return { ...state, messages }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'send':
      return {
        ...state,
        sending: true,
        lastActive: action.now,
        messages: [...state.messages, { role: 'user', text: action.text }, { role: 'assistant', text: '', done: false }],
      }
    case 'quotaLoaded':
      return { ...state, left: action.left }
    case 'reset':
      return emptyChat(action.now, action.sessionId)
    case 'draftAdded': {
      const m = state.messages[action.index]
      if (!m || m.role !== 'assistant' || !m.draft) return state
      const messages = state.messages.slice()
      messages[action.index] = { ...m, added: true }
      return { ...state, messages }
    }
    case 'networkError':
      return { ...updateLast(state, (m) => ({ ...m, status: undefined, error: 'network', done: true })), sending: false }
    case 'event': {
      const e = action.event
      switch (e.type) {
        case 'quota':
          return { ...state, left: e.left }
        case 'status':
          return updateLast(state, (m) => ({ ...m, status: e.tool }))
        case 'text':
          return updateLast(state, (m) => ({ ...m, status: undefined, text: m.text + e.delta }))
        case 'draft': {
          const { type: _t, ...draft } = e
          return updateLast(state, (m) => ({ ...m, draft }))
        }
        case 'blocked':
          return updateLast(state, (m) => ({ ...m, status: undefined, text: '', draft: undefined, blocked: true }))
        case 'error':
          return {
            ...updateLast(state, (m) => ({ ...m, status: undefined, error: e.code, done: true })),
            sending: false,
            left: e.code === 'quota_exceeded' ? 0 : state.left,
          }
        case 'done':
          return { ...updateLast(state, (m) => ({ ...m, status: undefined, done: true })), sending: false }
      }
    }
  }
  return state
}

/** Restore the chat after a reload; a chat idle for 15+ minutes (or broken storage) starts fresh. */
export function restoreChat(raw: string | null, now: number): ChatState {
  try {
    const s = raw ? JSON.parse(raw) : null
    if (s && typeof s.sessionId === 'string' && Array.isArray(s.messages) && typeof s.lastActive === 'number') {
      if (now - s.lastActive < IDLE_MS) {
        // A reply that was still loading when the page closed can't continue: mark it finished.
        const messages = s.messages.map((m: ChatMessage) =>
          m.role === 'assistant' && !m.done ? { ...m, status: undefined, error: m.text ? undefined : 'network', done: true } : m,
        )
        return { sessionId: s.sessionId, messages, left: null, sending: false, lastActive: s.lastActive }
      }
    }
  } catch {
    /* fall through */
  }
  return emptyChat(now)
}

export function loadChat(now = Date.now()): ChatState {
  try {
    return restoreChat(sessionStorage.getItem(STORAGE_KEY), now)
  } catch {
    return emptyChat(now)
  }
}

export function saveChat(state: ChatState): void {
  try {
    const { sessionId, messages, lastActive } = state
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ sessionId, messages, lastActive }))
  } catch {
    /* private mode: the chat just won't survive a reload */
  }
}
