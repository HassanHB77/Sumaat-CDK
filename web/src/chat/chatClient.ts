/**
 * Send one chat message to the AI assistant: POST /agent/chat on the site's own address (CloudFront ->
 * Bedrock AgentCore). AgentCore checks the Cognito ACCESS token (the /api routes use the ID token instead).
 */
import { fetchAuthSession } from 'aws-amplify/auth'
import type { Lang } from '../i18n/LanguageContext'
import { parseSse, type ChatEvent } from './chatStream'

export const SESSION_HEADER = 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'

export type ChatRequest = {
  path: string // config.chatPath, "/agent/chat"
  message: string
  sessionId: string
  lang: Lang
  spot: { lat: number; lng: number }
  signal?: AbortSignal
}

type Deps = {
  getAccessToken: (forceRefresh: boolean) => Promise<string | undefined>
  fetchImpl: typeof fetch
}

const defaultDeps: Deps = {
  getAccessToken: async (forceRefresh) => (await fetchAuthSession({ forceRefresh })).tokens?.accessToken?.toString(),
  fetchImpl: (...args) => fetch(...args),
}

/** Streams events to onEvent. Throws only on a network failure (the caller shows "No connection"). */
export async function sendChat(req: ChatRequest, onEvent: (e: ChatEvent) => void, deps: Deps = defaultDeps): Promise<void> {
  const post = async (token: string | undefined) =>
    deps.fetchImpl(req.path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        [SESSION_HEADER]: req.sessionId,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message: req.message, lang: req.lang, lat: req.spot.lat, lng: req.spot.lng }),
      signal: req.signal,
    })

  let res = await post(await deps.getAccessToken(false))
  if (res.status === 401) res = await post(await deps.getAccessToken(true)) // expired token: refresh once
  if (res.status === 401 || res.status === 403) return onEvent({ type: 'error', code: 'not_customer' })
  if (!res.ok || !res.body) return onEvent({ type: 'error', code: res.status === 429 ? 'busy' : 'failed' })

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finished = false
  for (;;) {
    const { value, done } = await reader.read()
    if (value) buffer += decoder.decode(value, { stream: true })
    const { events, rest } = parseSse(done ? buffer + '\n\n' : buffer)
    buffer = rest
    for (const e of events) {
      if (e.type === 'done' || e.type === 'error') finished = true
      onEvent(e)
    }
    if (done) break
  }
  if (!finished) onEvent({ type: 'error', code: 'failed' }) // stream cut short
}
