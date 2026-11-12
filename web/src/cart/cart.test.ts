import { describe, expect, it } from 'vitest'
import type { MenuItem, Order } from '../api/types'
import { formatOrderLabel, formatTime } from '../lib/format'
import { findOpenOrderAt, isFinal, rejectReason, stepIndex, timeOf } from '../lib/orders'
import {
  addItem,
  EMPTY_CART,
  itemCount,
  MAX_LINES,
  MAX_QTY,
  needsReplace,
  parseCart,
  qtyOf,
  reconcile,
  setNote,
  setQty,
  toOrderBody,
  totalHalalas,
} from './cartLogic'

const NAKHLA = { id: 'r1', name: 'Nakhla Kitchen', nameAr: 'مطبخ النخلة' }
const QAIS = { id: 'r2', name: 'Qaisariya Grill', nameAr: 'مشويات القيصرية' }
const dish = (id: string, price = 1000, over: Partial<MenuItem> = {}): MenuItem => ({
  id,
  restaurantId: 'r1',
  name: `Dish ${id}`,
  nameAr: `طبق ${id}`,
  category: 'Mains',
  priceHalalas: price,
  calories: 100,
  dietTags: [],
  isAvailable: true,
  ...over,
})

describe('cart', () => {
  it('add, increase, totals', () => {
    let c = addItem(EMPTY_CART, NAKHLA, dish('a', 2500))
    c = addItem(c, NAKHLA, dish('a', 2500))
    c = addItem(c, NAKHLA, dish('b', 900))
    expect([c.restaurantId, qtyOf(c, 'a'), itemCount(c), totalHalalas(c)]).toEqual(['r1', 2, 3, 5900])
  })

  it('decrease to 0 removes; empty cart forgets the restaurant', () => {
    let c = addItem(EMPTY_CART, NAKHLA, dish('a'))
    c = setQty(c, 'a', 0)
    expect(c).toEqual(EMPTY_CART)
  })

  it('limits: 20 per dish, 20 dishes', () => {
    let c = setQty(addItem(EMPTY_CART, NAKHLA, dish('a')), 'a', 99)
    expect(qtyOf(c, 'a')).toBe(MAX_QTY)
    for (let i = 0; i < MAX_LINES + 3; i++) c = addItem(c, NAKHLA, dish(`x${i}`))
    expect(c.lines.length).toBe(MAX_LINES)
  })

  it('other restaurant needs replace; adding then starts a fresh cart', () => {
    const c = setNote(addItem(EMPTY_CART, NAKHLA, dish('a')), 'no onions')
    expect(needsReplace(c, 'r2')).toBe(true)
    expect(needsReplace(c, 'r1')).toBe(false)
    const fresh = addItem(c, QAIS, dish('q', 3000, { restaurantId: 'r2' }))
    expect([fresh.restaurantId, fresh.lines.length, fresh.note]).toEqual(['r2', 1, ''])
  })

  it('note is capped at 200', () => {
    expect(setNote(EMPTY_CART, 'x'.repeat(250)).note.length).toBe(200)
  })

  it('reconcile drops hidden/removed dishes and updates prices', () => {
    let c = addItem(EMPTY_CART, NAKHLA, dish('a', 1000))
    c = addItem(c, NAKHLA, dish('b', 1000))
    c = addItem(c, NAKHLA, dish('gone', 1000))
    const menu = [dish('a', 1200), dish('b', 1000, { isAvailable: false })]
    const r = reconcile(c, 'r1', menu)
    expect(r.changed).toBe(true)
    expect(r.cart.lines.map((l) => [l.itemId, l.priceHalalas])).toEqual([['a', 1200]])
    expect(reconcile(r.cart, 'r1', menu).changed).toBe(false)
    expect(reconcile(r.cart, 'other', menu).changed).toBe(false) // another restaurant's menu: leave it
  })

  it('parseCart survives broken storage', () => {
    expect(parseCart(null)).toEqual(EMPTY_CART)
    expect(parseCart('{oops')).toEqual(EMPTY_CART)
    expect(parseCart(JSON.stringify({ restaurantId: 'r1', lines: [{ itemId: 'a', qty: -1, priceHalalas: 1 }] }))).toEqual(EMPTY_CART)
    const saved = addItem(EMPTY_CART, NAKHLA, dish('a'))
    expect(parseCart(JSON.stringify(saved))).toEqual(saved)
  })

  it('order body has ids and quantities only', () => {
    const c = setNote(setQty(addItem(EMPTY_CART, NAKHLA, dish('a', 999)), 'a', 3), '  extra lemon ')
    expect(toOrderBody(c)).toEqual({ restaurantId: 'r1', items: [{ itemId: 'a', qty: 3 }], note: 'extra lemon' })
    expect(toOrderBody(setNote(c, '   '))).not.toHaveProperty('note')
  })
})

const order = (over: Partial<Order>): Order =>
  ({
    id: 'o1',
    orderNumber: 7,
    businessDate: '2026-11-12',
    restaurantId: 'r1',
    status: 'PLACED',
    statusHistory: [
      { status: 'PLACED', at: '2026-11-12T11:05:00Z', by: 'c', role: 'customer' },
      { status: 'ACCEPTED', at: '2026-11-12T11:07:00Z', by: 'k', role: 'cashier' },
    ],
    ...over,
  }) as Order

describe('orders', () => {
  it('final / step / times', () => {
    expect(['SERVED', 'REJECTED', 'CANCELLED'].every((s) => isFinal(s as any))).toBe(true)
    expect(isFinal('READY_FOR_PICKUP')).toBe(false)
    expect([stepIndex('PLACED'), stepIndex('READY_FOR_PICKUP'), stepIndex('REJECTED')]).toEqual([0, 2, -1])
    expect(timeOf(order({}), 'ACCEPTED')).toBe('2026-11-12T11:07:00Z')
    expect(timeOf(order({}), 'SERVED')).toBeNull()
  })

  it('reject reason and open order lookup', () => {
    const rejected = order({
      status: 'REJECTED',
      statusHistory: [{ status: 'REJECTED', at: 'x', by: 'k', role: 'cashier', reason: 'Sold out' }],
    })
    expect(rejectReason(rejected)).toBe('Sold out')
    const list = [order({ id: 'old', status: 'SERVED' }), order({ id: 'open', status: 'ACCEPTED' }), order({ id: 'else', restaurantId: 'r2' })]
    expect(findOpenOrderAt(list, 'r1')?.id).toBe('open')
    expect(findOpenOrderAt(list, 'r3')).toBeNull()
  })

  it('order label and Riyadh time', () => {
    expect(formatOrderLabel(7, '2026-11-12', 'en')).toBe('#7 · Thu 12 Nov')
    expect(formatOrderLabel(7, '2026-11-12', 'ar')).toMatch(/^#7 · .*12.*نوفمبر/)
    expect(formatOrderLabel(7, '2026-11-12', 'ar')).not.toMatch(/[٠-٩]/) // Western digits only
    expect(formatTime('2026-11-12T11:05:00Z', 'en')).toBe('14:05') // UTC+3
    expect(formatTime('2026-11-12T21:30:00Z', 'en')).toBe('00:30')
  })
})
