import { apiFetch } from './client'
import type { Categories, NearbyRestaurant, RestaurantDetail } from './types'

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
