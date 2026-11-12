/** Counter board: pure logic (columns, pending actions, new-order detection). The hooks/components use these. */
import type { StaffAction } from '../api/endpoints'
import type { Order, OrderStatus } from '../api/types'

export type Column = 'new' | 'preparing' | 'ready' | 'done'

export const COLUMNS: Exclude<Column, 'done'>[] = ['new', 'preparing', 'ready']

export function columnOf(status: OrderStatus): Column {
  switch (status) {
    case 'PLACED':
      return 'new'
    case 'ACCEPTED':
      return 'preparing'
    case 'READY_FOR_PICKUP':
      return 'ready'
    default:
      return 'done'
  }
}

/** The one big button per column. */
export function nextAction(status: OrderStatus): Exclude<StaffAction, 'reject'> | null {
  if (status === 'PLACED') return 'accept'
  if (status === 'ACCEPTED') return 'ready'
  if (status === 'READY_FOR_PICKUP') return 'served'
  return null
}

/** Where an action takes the order (what the board shows while the action is pending). */
export function statusAfter(action: StaffAction): OrderStatus {
  return { accept: 'ACCEPTED', ready: 'READY_FOR_PICKUP', served: 'SERVED', reject: 'REJECTED' }[action] as OrderStatus
}

export type Pending = { orderId: string; orderNumber: number; action: StaffAction; reason?: string; dueAt: number }

export type BoardCard = Order & { shownStatus: OrderStatus; pending: Pending | null }

export type Board = Record<Column, BoardCard[]>

/**
 * Group today's orders into columns. A pending action wins over what the server says (so a 5 s refresh can't
 * flip a card back while its Undo is running). Active columns: oldest first (first come, first served).
 * Done: newest first.
 */
export function buildBoard(orders: Order[], pending: Pending[]): Board {
  const byOrder = new Map(pending.map((p) => [p.orderId, p]))
  const board: Board = { new: [], preparing: [], ready: [], done: [] }
  for (const o of orders) {
    const p = byOrder.get(o.id) ?? null
    const shownStatus = p ? statusAfter(p.action) : o.status
    board[columnOf(shownStatus)].push({ ...o, shownStatus, pending: p })
  }
  const oldestFirst = (a: BoardCard, b: BoardCard) => a.createdAt.localeCompare(b.createdAt)
  board.new.sort(oldestFirst)
  board.preparing.sort(oldestFirst)
  board.ready.sort(oldestFirst)
  board.done.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  return board
}

/** New orders since the last refresh (null `before` = first load: no alert for what was already there). */
export function newOrderIds(before: Set<string> | null, orders: Order[]): string[] {
  if (before === null) return []
  return orders.filter((o) => o.status === 'PLACED' && !before.has(o.id)).map((o) => o.id)
}

export function minutesSince(iso: string, now: number): number {
  return Math.max(0, Math.floor((now - Date.parse(iso)) / 60_000))
}

// --- pending actions with Undo (no React here: testable with fake timers) ---------------------

export const UNDO_MS = 3000

type Controller = {
  /** Start an action; it is sent after UNDO_MS unless undone. */
  start: (p: Omit<Pending, 'dueAt'>) => void
  undo: (orderId: string) => void
  list: () => Pending[]
  dispose: () => void
}

export function createPendingController(opts: {
  commit: (p: Pending) => Promise<unknown>
  onChange: (list: Pending[]) => void
  onCommitted: (p: Pending) => void
  onError: (p: Pending, error: unknown) => void
  delayMs?: number
  now?: () => number
}): Controller {
  const delay = opts.delayMs ?? UNDO_MS
  const now = opts.now ?? Date.now
  const items = new Map<string, Pending>()
  const timers = new Map<string, ReturnType<typeof setTimeout>>()
  const emit = () => opts.onChange([...items.values()])

  async function fire(orderId: string) {
    const p = items.get(orderId)
    timers.delete(orderId)
    if (!p) return
    try {
      await opts.commit(p)
      opts.onCommitted(p)
    } catch (e) {
      opts.onError(p, e)
    } finally {
      // keep showing the target until the caller refreshed the data (onCommitted/onError run first)
      items.delete(orderId)
      emit()
    }
  }

  return {
    start(p) {
      if (items.has(p.orderId)) return // one action per order at a time
      items.set(p.orderId, { ...p, dueAt: now() + delay })
      timers.set(p.orderId, setTimeout(() => fire(p.orderId), delay))
      emit()
    },
    undo(orderId) {
      const timer = timers.get(orderId)
      if (!timer) return // already being sent
      clearTimeout(timer)
      timers.delete(orderId)
      items.delete(orderId)
      emit()
    },
    list: () => [...items.values()],
    dispose() {
      timers.forEach(clearTimeout)
      timers.clear()
      items.clear()
    },
  }
}
