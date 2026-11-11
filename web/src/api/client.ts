/**
 * One way to call the Sumaat API.
 *
 * - Paths are relative to config.apiBase ("/api"): apiFetch("/restaurants") -> GET /api/restaurants.
 * - auth: true sends the Cognito ID TOKEN, raw, in "Authorization" (no "Bearer"; not the access token).
 * - 401 -> refresh the session once and retry; still 401 -> onSignedOut() (sign out + go to login, wired in M2).
 * - Errors come in two shapes and are normalised into ApiError:
 *     API Gateway (e.g. bad/missing token): {"message": "..."}
 *     Backend (FastAPI):                    {"detail": "..."} or, for 422, {"detail": [{loc, msg, type}, ...]}
 */
import { fetchAuthSession } from 'aws-amplify/auth'

export class ApiError extends Error {
  status: number // 0 = network error (no answer)
  fieldErrors: Record<string, string>
  body: unknown

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}, body: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
    this.body = body
  }
}

type ValidationItem = { loc?: (string | number)[]; msg?: string }

/** Turn any error body into ApiError (exported for tests). */
export function toApiError(status: number, body: any): ApiError {
  const detail = body?.detail
  if (typeof detail === 'string') return new ApiError(status, detail, {}, body)
  if (Array.isArray(detail)) {
    const fields: Record<string, string> = {}
    for (const item of detail as ValidationItem[]) {
      const field = item.loc?.length ? String(item.loc[item.loc.length - 1]) : '_'
      if (!fields[field]) fields[field] = item.msg ?? 'Invalid value'
    }
    const first = (detail as ValidationItem[])[0]?.msg ?? 'Invalid request'
    return new ApiError(status, first, fields, body)
  }
  if (typeof body?.message === 'string') return new ApiError(status, body.message, {}, body)
  return new ApiError(status, `Request failed (HTTP ${status})`, {}, body)
}

// --- wiring (overridable in tests and by the AuthContext in M2) -----------------------

type ApiDeps = {
  base: string
  getIdToken: (forceRefresh: boolean) => Promise<string | undefined>
  onSignedOut: () => void
  fetchImpl: typeof fetch
}

async function amplifyIdToken(forceRefresh: boolean): Promise<string | undefined> {
  const { tokens } = await fetchAuthSession({ forceRefresh })
  return tokens?.idToken?.toString()
}

const deps: ApiDeps = {
  base: '/api',
  getIdToken: amplifyIdToken,
  onSignedOut: () => {},
  fetchImpl: (...args) => fetch(...args),
}

export function configureApi(overrides: Partial<ApiDeps>): void {
  Object.assign(deps, overrides)
}

// --- the call ---------------------------------------------------------------------------

export type ApiOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
}

async function send(path: string, opts: ApiOptions, token: string | undefined): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = token
  return deps.fetchImpl(`${deps.base}${path}`, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  })
}

export async function apiFetch<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  let res: Response
  try {
    let token = opts.auth ? await deps.getIdToken(false) : undefined
    if (opts.auth && !token) {
      deps.onSignedOut()
      throw new ApiError(401, 'Not signed in')
    }
    res = await send(path, opts, token)
    if (res.status === 401 && opts.auth) {
      token = await deps.getIdToken(true) // expired or stale claims: refresh once
      res = await send(path, opts, token)
      if (res.status === 401) deps.onSignedOut()
    }
  } catch (e) {
    if (e instanceof ApiError) throw e
    if ((e as Error)?.name === 'AbortError') throw e
    throw new ApiError(0, 'No connection', {}, null)
  }

  if (res.status === 204) return null as T
  const text = await res.text()
  let body: any = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }
  if (!res.ok) throw toApiError(res.status, body)
  return body as T
}
