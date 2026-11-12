import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Order, OrderStatus } from '../api/types'
import {
  buildBoard,
  columnOf,
  createPendingController,
  minutesSince,
  newOrderIds,
  nextAction,
  statusAfter,
  type Pending,
} from './boardLogic'

const order = (id: string, status: OrderStatus, createdAt: string, updatedAt = createdAt): Order =>
  ({ id, orderNumber: Number(id.replace(/\D/g, '')) || 1, status, createdAt, updatedAt, statusHistory: [], items: [] }) as unknown as Order

describe('columns and actions', () => {
  it('maps statuses', () => {
    expect(['PLACED', 'ACCEPTED', 'READY_FOR_PICKUP', 'SERVED', 'REJECTED', 'CANCELLED'].map((s) => columnOf(s as OrderStatus))).toEqual([
      'new',
      'preparing',
      'ready',
      'done',
      'done',
      'done',
    ])
    expect([nextAction('PLACED'), nextAction('ACCEPTED'), nextAction('READY_FOR_PICKUP'), nextAction('SERVED')]).toEqual([
      'accept',
      'ready',
      'served',
      null,
    ])
    expect(statusAfter('reject')).toBe('REJECTED')
  })
})

describe('buildBoard', () => {
  const orders = [
    order('o2', 'PLACED', '2026-11-12T10:02:00Z'),
    order('o1', 'PLACED', '2026-11-12T10:01:00Z'),
    order('o3', 'ACCEPTED', '2026-11-12T10:00:00Z'),
    order('o4', 'SERVED', '2026-11-12T09:00:00Z', '2026-11-12T09:30:00Z'),
    order('o5', 'CANCELLED', '2026-11-12T09:10:00Z', '2026-11-12T09:40:00Z'),
  ]

  it('groups by column, oldest first; done newest first', () => {
    const b = buildBoard(orders, [])
    expect(b.new.map((c) => c.id)).toEqual(['o1', 'o2'])
    expect(b.preparing.map((c) => c.id)).toEqual(['o3'])
    expect(b.done.map((c) => c.id)).toEqual(['o5', 'o4'])
  })

  it('a pending action shows the target column, even if the server still says the old status', () => {
    const pending: Pending[] = [{ orderId: 'o1', orderNumber: 1, action: 'accept', dueAt: 0 }]
    const b = buildBoard(orders, pending) // polling data still says PLACED
    expect(b.new.map((c) => c.id)).toEqual(['o2'])
    expect(b.preparing.map((c) => c.id)).toEqual(['o3', 'o1'])
    expect(b.preparing.find((c) => c.id === 'o1')?.pending?.action).toBe('accept')
  })

  it('pending reject goes to done', () => {
    const b = buildBoard(orders, [{ orderId: 'o2', orderNumber: 2, action: 'reject', reason: 'Too busy', dueAt: 0 }])
    expect(b.done.some((c) => c.id === 'o2' && c.shownStatus === 'REJECTED')).toBe(true)
  })
})

describe('new orders', () => {
  it('no alert on first load; only new PLACED ids after', () => {
    const list = [order('a', 'PLACED', 'x'), order('b', 'ACCEPTED', 'x')]
    expect(newOrderIds(null, list)).toEqual([])
    expect(newOrderIds(new Set(['a']), [...list, order('c', 'PLACED', 'x'), order('d', 'ACCEPTED', 'x')])).toEqual(['c'])
  })

  it('minutes since placed', () => {
    expect(minutesSince('2026-11-12T10:00:00Z', Date.parse('2026-11-12T10:04:59Z'))).toBe(4)
    expect(minutesSince('2026-11-12T10:00:00Z', Date.parse('2026-11-12T09:59:00Z'))).toBe(0)
  })
})

describe('pending controller (Undo)', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  function setup(commit = vi.fn().mockResolvedValue({})) {
    const changes: Pending[][] = []
    const onCommitted = vi.fn()
    const onError = vi.fn()
    const c = createPendingController({ commit, onChange: (l) => changes.push(l), onCommitted, onError, delayMs: 3000 })
    return { c, commit, changes, onCommitted, onError }
  }

  it('sends after 3 s', async () => {
    const { c, commit, onCommitted } = setup()
    c.start({ orderId: 'o1', orderNumber: 1, action: 'accept' })
    await vi.advanceTimersByTimeAsync(2999)
    expect(commit).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(commit).toHaveBeenCalledWith(expect.objectContaining({ orderId: 'o1', action: 'accept' }))
    expect(onCommitted).toHaveBeenCalledOnce()
    expect(c.list()).toEqual([])
  })

  it('Undo within 3 s sends nothing', async () => {
    const { c, commit, changes } = setup()
    c.start({ orderId: 'o1', orderNumber: 1, action: 'ready' })
    await vi.advanceTimersByTimeAsync(1500)
    c.undo('o1')
    await vi.advanceTimersByTimeAsync(5000)
    expect(commit).not.toHaveBeenCalled()
    expect(changes.at(-1)).toEqual([])
  })

  it('error (e.g. 409) is reported and the pending card is cleared', async () => {
    const { c, onError, onCommitted } = setup(vi.fn().mockRejectedValue(new Error('Order is ACCEPTED')))
    c.start({ orderId: 'o1', orderNumber: 1, action: 'accept' })
    await vi.advanceTimersByTimeAsync(3000)
    expect(onError).toHaveBeenCalledOnce()
    expect(onCommitted).not.toHaveBeenCalled()
    expect(c.list()).toEqual([])
  })

  it('several at once, one action per order', async () => {
    const { c, commit } = setup()
    c.start({ orderId: 'o1', orderNumber: 1, action: 'accept' })
    c.start({ orderId: 'o1', orderNumber: 1, action: 'reject' }) // ignored: already pending
    c.start({ orderId: 'o2', orderNumber: 2, action: 'served' })
    expect(c.list().map((p) => p.orderId)).toEqual(['o1', 'o2'])
    await vi.advanceTimersByTimeAsync(3000)
    expect(commit).toHaveBeenCalledTimes(2)
  })
})
