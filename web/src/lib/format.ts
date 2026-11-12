import type { Lang } from '../i18n/LanguageContext'

/** 1250 -> "12.50 SAR" / "12.50 ر.س". Western digits in both languages, always 2 decimals. */
export function formatMoney(halalas: number, lang: Lang): string {
  const sar = (Math.round(halalas) / 100).toFixed(2)
  return lang === 'ar' ? `${sar} ر.س` : `${sar} SAR`
}

/** 1.234 -> "1.2 km" / "1.2 كم"; 1 -> "1 km" (no ".0") */
export function formatKm(km: number, lang: Lang): string {
  const value = km < 10 ? km.toFixed(1).replace(/\.0$/, '') : String(Math.round(km))
  return lang === 'ar' ? `${value} كم` : `${value} km`
}

export function formatCalories(kcal: number, lang: Lang): string {
  return lang === 'ar' ? `${kcal} سعرة` : `${kcal} kcal`
}

export type HoursInfo = { open: string; close: string; pastMidnight: boolean; allDay: boolean }

/** "13:00-01:00" -> {open "13:00", close "01:00", pastMidnight true}. "00:00-00:00" = open 24 h. */
export function parseHours(hours: string): HoursInfo {
  const [open = '', close = ''] = (hours ?? '').split('-')
  return { open, close, pastMidnight: close < open, allDay: open === close }
}

/** Display only; whether a restaurant is open ALWAYS comes from the API (openNow). */
export function opensAt(hours: string): string {
  return parseHours(hours).open
}

/** Arabic name in Arabic, English name in English; falls back to the other if one is empty. */
export function pickName(obj: { name?: string; nameAr?: string }, lang: Lang): string {
  const ar = obj.nameAr?.trim()
  const en = obj.name?.trim()
  return (lang === 'ar' ? ar || en : en || ar) ?? ''
}

const LOCALE: Record<Lang, string> = {
  en: 'en-GB',
  ar: 'ar-SA-u-ca-gregory-nu-latn', // Gregorian calendar + Western digits in Arabic
}

/**
 * "#7 · Thu 12 Nov" / "#7 · الخميس 12 نوفمبر". Numbers restart every business day, so the date always goes with them.
 * businessDate is a plain date: read it at noon UTC so no time zone can shift the day.
 */
export function formatOrderLabel(orderNumber: number, businessDate: string, lang: Lang): string {
  const day = new Date(`${businessDate}T12:00:00Z`)
  const text = new Intl.DateTimeFormat(LOCALE[lang], {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  }).format(day)
  return `#${orderNumber} · ${text.replace(/,/g, '')}`
}

/** UTC ISO -> "14:05" in Riyadh time (24 h). */
export function formatTime(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALE[lang], {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: 'Asia/Riyadh',
  }).format(new Date(iso))
}
