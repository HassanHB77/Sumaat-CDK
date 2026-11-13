/**
 * The cart: one restaurant at a time, kept on this device. Pure functions (easy to test); CartContext wraps them.
 * Prices here are for display only: the API always charges its own current prices.
 */
import type { MenuItem } from '../api/types'

export const MAX_QTY = 20 // per dish, same as the API
export const MAX_LINES = 20 // dishes per order, same as the API
export const MAX_NOTE = 200

export type CartLine = { itemId: string; name: string; nameAr: string; priceHalalas: number; qty: number }

export type Cart = {
  restaurantId: string
  restaurantName: string
  restaurantNameAr: string
  lines: CartLine[]
  note: string
}

export type CartRestaurant = { id: string; name: string; nameAr: string }

export const EMPTY_CART: Cart = { restaurantId: '', restaurantName: '', restaurantNameAr: '', lines: [], note: '' }

export const isEmpty = (cart: Cart) => cart.lines.length === 0
export const itemCount = (cart: Cart) => cart.lines.reduce((n, l) => n + l.qty, 0)
export const totalHalalas = (cart: Cart) => cart.lines.reduce((sum, l) => sum + l.priceHalalas * l.qty, 0)
export const qtyOf = (cart: Cart, itemId: string) => cart.lines.find((l) => l.itemId === itemId)?.qty ?? 0

/** Adding from another restaurant needs the user's OK first (the old cart is cleared). */
export function needsReplace(cart: Cart, restaurantId: string): boolean {
  return !isEmpty(cart) && cart.restaurantId !== restaurantId
}

/** Add one of `item`. Starts a new cart if it belongs to another restaurant (ask with needsReplace first). */
export function addItem(cart: Cart, restaurant: CartRestaurant, item: MenuItem): Cart {
  const base: Cart =
    cart.restaurantId === restaurant.id && !isEmpty(cart)
      ? cart
      : { ...EMPTY_CART, restaurantId: restaurant.id, restaurantName: restaurant.name, restaurantNameAr: restaurant.nameAr }
  const existing = base.lines.find((l) => l.itemId === item.id)
  if (existing) return setQty(base, item.id, existing.qty + 1)
  if (base.lines.length >= MAX_LINES) return base
  const line: CartLine = { itemId: item.id, name: item.name, nameAr: item.nameAr, priceHalalas: item.priceHalalas, qty: 1 }
  return { ...base, lines: [...base.lines, line] }
}

/** qty <= 0 removes the dish; above the limit is capped. Emptying the cart forgets the restaurant. */
export function setQty(cart: Cart, itemId: string, qty: number): Cart {
  const lines =
    qty <= 0
      ? cart.lines.filter((l) => l.itemId !== itemId)
      : cart.lines.map((l) => (l.itemId === itemId ? { ...l, qty: Math.min(qty, MAX_QTY) } : l))
  return lines.length ? { ...cart, lines } : { ...EMPTY_CART }
}

export function setNote(cart: Cart, note: string): Cart {
  return { ...cart, note: note.slice(0, MAX_NOTE) }
}

/**
 * Bring the cart in line with the latest menu of its restaurant: drop dishes that are gone or hidden,
 * update names and prices. `changed` tells the page to show "Your cart was updated".
 */
export function reconcile(cart: Cart, restaurantId: string, menu: MenuItem[]): { cart: Cart; changed: boolean } {
  if (isEmpty(cart) || cart.restaurantId !== restaurantId) return { cart, changed: false }
  const byId = new Map(menu.map((m) => [m.id, m]))
  let changed = false
  const lines: CartLine[] = []
  for (const line of cart.lines) {
    const item = byId.get(line.itemId)
    if (!item || !item.isAvailable) {
      changed = true
      continue
    }
    if (item.priceHalalas !== line.priceHalalas) changed = true
    lines.push({ ...line, name: item.name, nameAr: item.nameAr, priceHalalas: item.priceHalalas })
  }
  if (!changed) return { cart, changed: false }
  return { cart: lines.length ? { ...cart, lines } : { ...EMPTY_CART }, changed: true }
}

/** A cart drafted by the AI assistant (agent/catalog.py draft_cart): prices come from the database. */
export type CartDraft = {
  restaurant: CartRestaurant
  lines: CartLine[]
  totalHalalas: number
}

/**
 * "Add to cart" on an assistant draft: the cart BECOMES the draft (the chat shows a note saying so when the cart
 * isn't empty). The cart's note is kept only for the same restaurant. Limits are re-applied defensively.
 */
export function fromDraft(cart: Cart, draft: CartDraft): Cart {
  const lines = draft.lines
    .filter((l) => l.qty > 0)
    .slice(0, MAX_LINES)
    .map((l) => ({ itemId: l.itemId, name: l.name, nameAr: l.nameAr, priceHalalas: l.priceHalalas, qty: Math.min(l.qty, MAX_QTY) }))
  if (!lines.length) return cart
  const sameRestaurant = cart.restaurantId === draft.restaurant.id
  return {
    restaurantId: draft.restaurant.id,
    restaurantName: draft.restaurant.name,
    restaurantNameAr: draft.restaurant.nameAr,
    lines,
    note: sameRestaurant ? cart.note : '',
  }
}

/** Read a saved cart; anything broken -> empty cart. */
export function parseCart(raw: string | null): Cart {
  if (!raw) return { ...EMPTY_CART }
  try {
    const c = JSON.parse(raw)
    if (typeof c?.restaurantId !== 'string' || !Array.isArray(c?.lines)) return { ...EMPTY_CART }
    const lines: CartLine[] = c.lines
      .filter((l: any) => typeof l?.itemId === 'string' && Number.isInteger(l?.qty) && l.qty > 0 && Number.isInteger(l?.priceHalalas))
      .slice(0, MAX_LINES)
      .map((l: any) => ({
        itemId: l.itemId,
        name: String(l.name ?? ''),
        nameAr: String(l.nameAr ?? ''),
        priceHalalas: l.priceHalalas,
        qty: Math.min(l.qty, MAX_QTY),
      }))
    if (!lines.length) return { ...EMPTY_CART }
    return {
      restaurantId: c.restaurantId,
      restaurantName: String(c.restaurantName ?? ''),
      restaurantNameAr: String(c.restaurantNameAr ?? ''),
      lines,
      note: String(c.note ?? '').slice(0, MAX_NOTE),
    }
  } catch {
    return { ...EMPTY_CART }
  }
}

/** What POST /api/orders receives: ids and quantities only. */
export function toOrderBody(cart: Cart) {
  const note = cart.note.trim()
  return {
    restaurantId: cart.restaurantId,
    items: cart.lines.map((l) => ({ itemId: l.itemId, qty: l.qty })),
    ...(note ? { note } : {}),
  }
}
