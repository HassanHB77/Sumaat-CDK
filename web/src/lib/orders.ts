import type { Order, OrderStatus } from '../api/types'

export const FINAL: OrderStatus[] = ['SERVED', 'REJECTED', 'CANCELLED']
export const OPEN: OrderStatus[] = ['PLACED', 'ACCEPTED', 'READY_FOR_PICKUP']
export const STEPS: OrderStatus[] = ['PLACED', 'ACCEPTED', 'READY_FOR_PICKUP', 'SERVED']

export const isFinal = (status: OrderStatus) => FINAL.includes(status)
export const isOpen = (status: OrderStatus) => OPEN.includes(status)

/** Position in Placed -> Accepted -> Ready -> Served (-1 for rejected/cancelled). */
export function stepIndex(status: OrderStatus): number {
  return STEPS.indexOf(status)
}

/** When the order reached `status` (UTC ISO), from its history. */
export function timeOf(order: Pick<Order, 'statusHistory'>, status: OrderStatus): string | null {
  return order.statusHistory?.find((h) => h.status === status)?.at ?? null
}

/** The reason given when an order was rejected (if any). */
export function rejectReason(order: Pick<Order, 'statusHistory'>): string | null {
  return order.statusHistory?.find((h) => h.status === 'REJECTED')?.reason ?? null
}

/** The customer's open order at a restaurant (for the "you already have an open order here" link). */
export function findOpenOrderAt(orders: Order[], restaurantId: string): Order | null {
  return orders.find((o) => o.restaurantId === restaurantId && isOpen(o.status)) ?? null
}
