import { apiFetch } from './client'
import type { Categories, NearbyRestaurant, Order, PlaceOrderBody, RestaurantDetail } from './types'

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
