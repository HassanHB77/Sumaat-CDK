/** Owner forms: pure helpers (hours, SAR prices, changed fields, validation). */
import { MAX_CUISINES, type Cuisine } from '../api/types'
import type { MessageKey } from '../i18n/en'
import { isInAlAhsa } from '../lib/geo'

// --- hours -------------------------------------------------------------------------------

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

export type HoursParts = { open: string; close: string; allDay: boolean }

/** "13:00-01:00" -> {open, close}; "00:00-00:00" -> allDay. */
export function splitHours(hours: string): HoursParts {
  const [open = '12:00', close = '23:00'] = (hours ?? '').split('-')
  return { open, close, allDay: open === close }
}

/** Back to the API format. Open 24 h = "00:00-00:00". null if a time is invalid. */
export function composeHours(open: string, close: string, allDay: boolean): string | null {
  if (allDay) return '00:00-00:00'
  if (!HHMM.test(open) || !HHMM.test(close) || open === close) return null
  return `${open}-${close}`
}

// --- money -------------------------------------------------------------------------------

/** Owners type prices in SAR ("48" or "48.50"); the API stores whole halalas. Max 2 decimals, up to 10,000 SAR. */
export function parseSar(text: string): number | null {
  const t = (text ?? '').trim()
  if (!/^\d{1,5}(\.\d{1,2})?$/.test(t)) return null
  const halalas = Math.round(Number(t) * 100)
  return halalas >= 1 && halalas <= 1_000_000 ? halalas : null
}

export function halalasToSar(halalas: number): string {
  return (halalas / 100).toFixed(2)
}

// --- changed fields (PATCH sends only what changed) ---------------------------------------

export function changedFields<T extends Record<string, unknown>>(original: T, edited: T): Partial<T> {
  const out: Partial<T> = {}
  for (const key of Object.keys(edited) as (keyof T)[]) {
    const a = original[key]
    const b = edited[key]
    const same = Array.isArray(a) && Array.isArray(b) ? a.length === b.length && a.every((x, i) => x === b[i]) : a === b
    if (!same) out[key] = b
  }
  return out
}

// --- validation --------------------------------------------------------------------------

export type RestaurantValues = {
  name: string
  nameAr: string
  description: string
  descriptionAr: string
  cuisines: Cuisine[]
  city: string
  district: string
  lat: number
  lng: number
  hours: string
}

export type Errors<K extends string> = Partial<Record<K, MessageKey>>

export function validateRestaurant(v: RestaurantValues): Errors<keyof RestaurantValues> {
  const e: Errors<keyof RestaurantValues> = {}
  if (!v.name.trim()) e.name = 'auth.err.required'
  if (!v.nameAr.trim()) e.nameAr = 'auth.err.required'
  if (v.description.length > 500) e.description = 'owner.err.tooLong'
  if (v.descriptionAr.length > 500) e.descriptionAr = 'owner.err.tooLong'
  if (v.cuisines.length < 1 || v.cuisines.length > MAX_CUISINES) e.cuisines = 'owner.err.cuisines'
  if (!v.city.trim()) e.city = 'auth.err.required'
  if (!v.district.trim()) e.district = 'auth.err.required'
  if (!v.hours) e.hours = 'owner.err.hours'
  if (!isInAlAhsa(v.lat, v.lng)) e.lat = 'owner.err.location'
  return e
}

export type ItemValues = {
  name: string
  nameAr: string
  category: string
  price: string // SAR text as typed
  calories: string
  dietTags: string[]
  isAvailable: boolean
}

export function validateItem(v: ItemValues): Errors<keyof ItemValues> {
  const e: Errors<keyof ItemValues> = {}
  if (!v.name.trim()) e.name = 'auth.err.required'
  if (!v.nameAr.trim()) e.nameAr = 'auth.err.required'
  if (!v.category) e.category = 'auth.err.required'
  if (parseSar(v.price) === null) e.price = 'owner.err.price'
  if (v.calories.trim() && !/^\d{1,5}$/.test(v.calories.trim())) e.calories = 'owner.err.calories'
  return e
}
