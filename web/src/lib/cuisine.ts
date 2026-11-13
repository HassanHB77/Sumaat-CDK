import { CUISINES, type Cuisine } from '../api/types'

type HasCuisines = { cuisines?: Cuisine[] }

/** Cuisines that at least one listed restaurant has, in the fixed order (so the filter only offers useful chips). */
export function availableCuisines(restaurants: HasCuisines[]): Cuisine[] {
  const present = new Set(restaurants.flatMap((r) => r.cuisines ?? []))
  return CUISINES.filter((c) => present.has(c))
}

/** Restaurants with ANY of the selected cuisines; nothing selected = all of them. */
export function filterByCuisine<T extends HasCuisines>(restaurants: T[], selected: Cuisine[]): T[] {
  if (!selected.length) return restaurants
  return restaurants.filter((r) => r.cuisines?.some((c) => selected.includes(c)))
}
