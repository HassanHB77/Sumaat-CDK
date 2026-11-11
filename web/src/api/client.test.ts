import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, configureApi, toApiError } from './client'

function json(status: number, body: unknown): Response {
  return new Response(body === null ? null : JSON.stringify(body), { status })
}

describe('toApiError', () => {
  it('reads backend {detail: string}', () => {
    const e = toApiError(409, { detail: 'Restaurant is closed' })
    expect(e.status).toBe(409)
    expect(e.message).toBe('Restaurant is closed')
  })

  it('reads API Gateway {message}', () => {
    expect(toApiError(401, { message: 'Unauthorized' }).message).toBe('Unauthorized')
  })

  it('maps 422 validation lists to field errors', () => {
    const e = toApiError(422, {
      detail: [
        { loc: ['body', 'priceHalalas'], msg: 'Input should be a valid integer' },
        { loc: ['body', 'name'], msg: 'String should have at least 1 character' },
      ],
    })
    expect(e.fieldErrors).toEqual({
      priceHalalas: 'Input should be a valid integer',
      name: 'String should have at least 1 character',
    })
    expect(e.message).toBe('Input should be a valid integer')
  })

  it('falls back for unknown bodies', () => {
    expect(toApiError(500, null).message).toBe('Request failed (HTTP 500)')
  })
})

describe('apiFetch', () => {
  const fetchImpl = vi.fn()
  const getIdToken = vi.fn()
  const onSignedOut = vi.fn()

  beforeEach(() => {
    fetchImpl.mockReset()
    getIdToken.mockReset()
    onSignedOut.mockReset()
    configureApi({ base: '/api', fetchImpl, getIdToken, onSignedOut })
  })

  it('public GET: no Authorization header', async () => {
    fetchImpl.mockResolvedValue(json(200, { status: 'ok' }))
    await expect(apiFetch('/health')).resolves.toEqual({ status: 'ok' })
    const [url, init] = fetchImpl.mock.calls[0]
    expect(url).toBe('/api/health')
    expect(init.headers.Authorization).toBeUndefined()
    expect(getIdToken).not.toHaveBeenCalled()
  })

  it('auth call: raw ID token, JSON body', async () => {
    getIdToken.mockResolvedValue('eyJ.token')
    fetchImpl.mockResolvedValue(json(201, { id: 'o1' }))
    await apiFetch('/orders', { method: 'POST', auth: true, body: { a: 1 } })
    const [, init] = fetchImpl.mock.calls[0]
    expect(init.headers.Authorization).toBe('eyJ.token') // no "Bearer "
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"a":1}')
  })

  it('401 -> refresh once and retry', async () => {
    getIdToken.mockResolvedValueOnce('old').mockResolvedValueOnce('new')
    fetchImpl.mockResolvedValueOnce(json(401, { message: 'Unauthorized' })).mockResolvedValueOnce(json(200, []))
    await expect(apiFetch('/orders/mine', { auth: true })).resolves.toEqual([])
    expect(getIdToken).toHaveBeenLastCalledWith(true)
    expect(fetchImpl.mock.calls[1][1].headers.Authorization).toBe('new')
    expect(onSignedOut).not.toHaveBeenCalled()
  })

  it('401 twice -> signed out', async () => {
    getIdToken.mockResolvedValue('t')
    fetchImpl.mockResolvedValue(json(401, { message: 'Unauthorized' }))
    await expect(apiFetch('/orders/mine', { auth: true })).rejects.toMatchObject({ status: 401 })
    expect(onSignedOut).toHaveBeenCalledOnce()
  })

  it('no session -> 401 without calling the API', async () => {
    getIdToken.mockResolvedValue(undefined)
    await expect(apiFetch('/orders/mine', { auth: true })).rejects.toBeInstanceOf(ApiError)
    expect(fetchImpl).not.toHaveBeenCalled()
    expect(onSignedOut).toHaveBeenCalledOnce()
  })

  it('204 -> null', async () => {
    getIdToken.mockResolvedValue('t')
    fetchImpl.mockResolvedValue(json(204, null))
    await expect(apiFetch('/x', { method: 'POST', auth: true })).resolves.toBeNull()
  })

  it('network failure -> ApiError status 0', async () => {
    fetchImpl.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(apiFetch('/health')).rejects.toMatchObject({ status: 0, message: 'No connection' })
  })

  it('409 keeps the backend message', async () => {
    getIdToken.mockResolvedValue('t')
    fetchImpl.mockResolvedValue(json(409, { detail: 'You already have an open order here (#3)' }))
    await expect(apiFetch('/orders', { method: 'POST', auth: true, body: {} })).rejects.toMatchObject({
      status: 409,
      message: 'You already have an open order here (#3)',
    })
  })
})
