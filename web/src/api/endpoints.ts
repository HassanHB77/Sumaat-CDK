import { apiFetch } from './client'
import type { Categories, NearbyRestaurant, Order, PlaceOrderBody, Restaurant, RestaurantDetail } from './types'

// --- public (no login) ---

export function getNearby(lat: number, lng: number, radiusKm: number, signal?: AbortSignal) {
  const q = new URLSearchParams({ lat: lat.toFixed(5), lng: lng.toFixed(5), radiusKm: String(radiusKm) })
  return apiFetch<NearbyRestaurant[]>(`/restaurants?${q}`, { signal })
}

export function getRestaurant(id: string, signal?: AbortSignal) {
  return apiFetch<RestaurantDetail>(`/restaurants/${encodeURIComponent(id)}`, { signal })
}

export function getCategories(signal?: AbortSignal) {
  return apiFetch<Categories>('/categories', { signal })
}

// --- customer ---

export function placeOrder(body: PlaceOrderBody) {
  return apiFetch<Order>('/orders', { method: 'POST', body, auth: true })
}

export function getOrder(id: string, signal?: AbortSignal) {
  return apiFetch<Order>(`/orders/${encodeURIComponent(id)}`, { auth: true, signal })
}

export function getMyOrders(signal?: AbortSignal) {
  return apiFetch<Order[]>('/orders/mine', { auth: true, signal })
}

export function cancelOrder(id: string) {
  return apiFetch<Order>(`/orders/${encodeURIComponent(id)}/cancel`, { method: 'POST', auth: true })
}

// --- staff (owner or active cashier of the restaurant) ---

export function getRestaurantOrders(restaurantId: string, signal?: AbortSignal) {
  return apiFetch<Order[]>(`/restaurants/${encodeURIComponent(restaurantId)}/orders`, { auth: true, signal })
}

export type StaffAction = 'accept' | 'ready' | 'served' | 'reject'

export function changeOrderStatus(orderId: string, action: StaffAction, reason?: string) {
  return apiFetch<Order>(`/orders/${encodeURIComponent(orderId)}/${action}`, {
    method: 'POST',
    auth: true,
    body: action === 'reject' ? { reason: reason || null } : undefined,
  })
}

export function setPaused(restaurantId: string, paused: boolean) {
  return apiFetch<Restaurant>(`/restaurants/${encodeURIComponent(restaurantId)}/${paused ? 'pause' : 'resume'}`, {
    method: 'POST',
    auth: true,
  })
}
