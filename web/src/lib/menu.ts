import type { DietTag, MenuItem, NearbyRestaurant } from '../api/types'

export type MenuSection = { category: string; items: MenuItem[] }

/**
 * Customer menu: hide unavailable items, keep items that have ALL selected diet tags, group by category in the
 * API's menu order (/categories), skip empty categories. Categories not in the list (e.g. added later) go last, A-Z.
 * Items inside a category keep a stable A-Z order by English name.
 */
export function groupMenu(
  items: MenuItem[],
  categoryOrder: string[],
  dietFilter: DietTag[] = [],
  options: { includeHidden?: boolean } = {},
): MenuSection[] {
  const visible = items.filter(
    (i) => (options.includeHidden || i.isAvailable) && dietFilter.every((tag) => i.dietTags?.includes(tag)),
  )
  const byCategory = new Map<string, MenuItem[]>()
  for (const item of visible) {
    const list = byCategory.get(item.category) ?? []
    list.push(item)
    byCategory.set(item.category, list)
  }
  const known = categoryOrder.filter((c) => byCategory.has(c))
  const unknown = [...byCategory.keys()].filter((c) => !categoryOrder.includes(c)).sort()
  return [...known, ...unknown].map((category) => ({
    category,
    items: byCategory.get(category)!.sort((a, b) => a.name.localeCompare(b.name)),
  }))
}

/** Restaurant list: open ones first (nearest first), then closed/paused ones (nearest first). */
export function sortRestaurants(list: NearbyRestaurant[]): NearbyRestaurant[] {
  return [...list].sort((a, b) => Number(b.openNow) - Number(a.openNow) || a.distanceKm - b.distanceKm)
}

/** Diet tags that actually appear on visible items (so the filter only offers useful chips). */
export function availableDietTags(items: MenuItem[], allTags: DietTag[]): DietTag[] {
  const present = new Set(items.filter((i) => i.isAvailable).flatMap((i) => i.dietTags ?? []))
  return allTags.filter((t) => present.has(t))
}
