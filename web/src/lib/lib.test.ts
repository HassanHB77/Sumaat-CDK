import { describe, expect, it } from 'vitest'
import type { MenuItem, NearbyRestaurant } from '../api/types'
import { DIET_TAGS } from '../api/types'
import { formatCalories, formatDayShort, formatKm, formatMoney, formatMoneyWhole, opensAt, parseHours, pickName } from './format'
import { DEFAULT_SPOT, isInAlAhsa, parseSpot } from './geo'
import { availableDietTags, groupMenu, normalizeSearch, sortRestaurants } from './menu'

describe('format', () => {
  it.each([
    [0, '0.00 SAR', '0.00 ر.س'],
    [50, '0.50 SAR', '0.50 ر.س'],
    [4800, '48.00 SAR', '48.00 ر.س'],
    [123456, '1234.56 SAR', '1234.56 ر.س'],
  ])('money %i', (halalas, en, ar) => {
    expect(formatMoney(halalas, 'en')).toBe(en)
    expect(formatMoney(halalas, 'ar')).toBe(ar)
  })

  it('km and calories', () => {
    expect(formatKm(1.234, 'en')).toBe('1.2 km')
    expect(formatKm(0.05, 'ar')).toBe('0.1 كم')
    expect(formatKm(1, 'en')).toBe('1 km')
    expect(formatKm(4.4, 'en')).toBe('4.4 km')
    expect(formatCalories(520, 'ar')).toBe('520 سعرة')
  })

  it('hours', () => {
    expect(parseHours('12:00-23:30')).toEqual({ open: '12:00', close: '23:30', pastMidnight: false, allDay: false })
    expect(parseHours('13:00-01:00').pastMidnight).toBe(true)
    expect(parseHours('00:00-00:00').allDay).toBe(true)
    expect(opensAt('13:00-01:00')).toBe('13:00')
  })

  it('pickName falls back when one name is empty', () => {
    expect(pickName({ name: 'Hummus', nameAr: 'حمص' }, 'ar')).toBe('حمص')
    expect(pickName({ name: 'Hummus', nameAr: 'حمص' }, 'en')).toBe('Hummus')
    expect(pickName({ name: 'Hummus', nameAr: '' }, 'ar')).toBe('Hummus')
    expect(pickName({ name: '', nameAr: 'حمص' }, 'en')).toBe('حمص')
  })
})

describe('geo', () => {
  it('Al-Ahsa box', () => {
    expect(isInAlAhsa(25.38, 49.588)).toBe(true)
    expect(isInAlAhsa(24.71, 46.67)).toBe(false) // Riyadh
  })

  it('saved spot: round trip, broken values and outside Al-Ahsa fall back to default', () => {
    expect(parseSpot(JSON.stringify({ lat: 25.41, lng: 49.58, label: 'mubarraz' }))).toEqual({
      lat: 25.41,
      lng: 49.58,
      label: 'mubarraz',
    })
    expect(parseSpot(null)).toBe(DEFAULT_SPOT)
    expect(parseSpot('{not json')).toBe(DEFAULT_SPOT)
    expect(parseSpot(JSON.stringify({ lat: 24.71, lng: 46.67, label: 'me' }))).toBe(DEFAULT_SPOT)
  })
})

const item = (over: Partial<MenuItem>): MenuItem => ({
  id: over.name ?? 'x',
  restaurantId: 'r',
  name: 'x',
  nameAr: 'x',
  category: 'Mains',
  priceHalalas: 1000,
  calories: 100,
  dietTags: [],
  isAvailable: true,
  ...over,
})

describe('menu', () => {
  const order = ['Breakfast', 'Mains', 'Sides', 'Drinks']
  const items = [
    item({ name: 'Laban', category: 'Drinks', dietTags: ['vegetarian', 'gluten_free'] }),
    item({ name: 'Kabsa', category: 'Mains', dietTags: ['gluten_free', 'high_protein'] }),
    item({ name: 'Harees', category: 'Mains', dietTags: ['high_protein'] }),
    item({ name: 'Hidden dish', category: 'Sides', isAvailable: false }),
    item({ name: 'Soup', category: 'Soups' }), // added later via CLI
  ]

  it('groups in menu order, skips empty and hidden, unknown categories last', () => {
    const sections = groupMenu(items, order)
    expect(sections.map((s) => s.category)).toEqual(['Mains', 'Drinks', 'Soups'])
    expect(sections[0].items.map((i) => i.name)).toEqual(['Harees', 'Kabsa'])
  })

  it('owner view can include hidden items', () => {
    expect(groupMenu(items, order, [], { includeHidden: true }).map((s) => s.category)).toContain('Sides')
  })

  it('owner view puts hidden dishes at the bottom of their section (each part A-Z)', () => {
    const mains = [
      item({ name: 'Apple Salad', isAvailable: false }),
      item({ name: 'Zaatar Bread' }),
      item({ name: 'Kabsa' }),
      item({ name: 'Bamia', isAvailable: false }),
    ]
    const [section] = groupMenu(mains, order, [], { includeHidden: true })
    expect(section.items.map((i) => i.name)).toEqual(['Kabsa', 'Zaatar Bread', 'Apple Salad', 'Bamia'])
  })

  it('diet filter needs ALL selected tags', () => {
    const sections = groupMenu(items, order, ['gluten_free', 'high_protein'])
    expect(sections.flatMap((s) => s.items.map((i) => i.name))).toEqual(['Kabsa'])
  })

  it('offers only diet tags that appear on visible items', () => {
    expect(availableDietTags(items, DIET_TAGS)).toEqual(['vegetarian', 'gluten_free', 'high_protein'])
  })

  it('restaurants: open first, then nearest', () => {
    const r = (name: string, openNow: boolean, distanceKm: number) => ({ name, openNow, distanceKm }) as NearbyRestaurant
    const sorted = sortRestaurants([r('far-open', true, 3), r('near-closed', false, 0.5), r('near-open', true, 1)])
    expect(sorted.map((x) => x.name)).toEqual(['near-open', 'far-open', 'near-closed'])
  })
})

describe('dish search', () => {
  const items = [
    item({ name: 'Lamb Kabsa', nameAr: 'كَبْسَة لحم' }),
    item({ name: 'Green Salad', nameAr: 'سلطة خضراء', category: 'Salads' }),
    item({ name: 'Hidden Kabsa', nameAr: 'كبسة', isAvailable: false }),
  ]
  const order = ['Mains', 'Salads']
  const names = (search: string) => groupMenu(items, order, [], { search }).flatMap((s) => s.items.map((i) => i.name))

  it('matches English case-insensitively and Arabic without vowel marks or ة/ه differences', () => {
    expect(names('salad')).toEqual(['Green Salad'])
    expect(names('كبسه')).toEqual(['Lamb Kabsa']) // hidden dish still hidden for customers
    expect(names('  ')).toEqual(['Lamb Kabsa', 'Green Salad'])
    expect(names('pizza')).toEqual([])
  })

  it('normalises alef forms, ya and tatweel', () => {
    expect(normalizeSearch('أإآ ى ـــة')).toBe('ااا ي ه')
  })
})

describe('chart formats', () => {
  it('short day and whole riyals, Western digits in Arabic', () => {
    expect(formatDayShort('2026-11-12', 'en')).toBe('Thu 12')
    expect(formatDayShort('2026-11-12', 'ar')).toMatch(/12/)
    expect(formatMoneyWhole(412_49, 'en')).toBe('412 SAR')
    expect(formatMoneyWhole(1_234_56, 'ar')).toBe('1,235 ر.س')
  })
})
