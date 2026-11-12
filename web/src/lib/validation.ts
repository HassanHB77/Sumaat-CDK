import type { MessageKey } from '../i18n/en'
import { isStrongPassword } from './password'
import { isValidSaudiMobile } from './phone'

/*
 * Person fields (sign-up + cashier form). SAME rules as api/validation.py and functions/pre_sign_up/handler.py,
 * so a warning here matches what the server would refuse.
 */

// Arabic letters + harakat + tatweel (no Arabic-Indic digits, no Arabic punctuation).
const ARABIC = 'ء-ٰٟ-ۓ'
const ARABIC_LETTERS = 'ء-غف-يٱ-ۓ'
// Emoji + zero-width joiner + variation selector. Keycap emoji (1️⃣) are digits, so not included.
const EMOJI =
  '©®‼⁉™ℹ↔-↙↩↪⌚-⏿Ⓜ▪-◾' +
  '☀-➿⤴⤵⬅-⭕〰〽㊗㊙\u{1F000}-\u{1FAFF}‍️'
const NAME_RE = new RegExp(`^[A-Za-z${ARABIC}${EMOJI} '’.\\-]+$`, 'u')
const LETTER_RE = new RegExp(`[A-Za-z${ARABIC_LETTERS}]`, 'u')
const NAME_MAX = 80

/** Arabic or English letters, spaces, - ' . and emoji; at least one letter; up to 80 characters. */
export function isValidPersonName(value: string): boolean {
  const v = value.trim()
  const length = [...v].length // code points, like Python's len()
  return length > 0 && length <= NAME_MAX && NAME_RE.test(v) && LETTER_RE.test(v)
}

/** name@domain.tld; no spaces, commas, semicolons or brackets. Same rule as the API. */
export const isEmail = (v: string) => /^[^@\s,;<>()[\]]+@[^@\s,;<>()[\]]+\.[A-Za-z]{2,}$/.test(v.trim())

export type PersonField = 'name' | 'email' | 'phone' | 'password'
export const PERSON_FIELDS: PersonField[] = ['name', 'email', 'phone', 'password']
export type PersonErrors = Partial<Record<PersonField, MessageKey>>

/** One warning per field (or none). */
export function validatePerson(v: Record<PersonField, string>): PersonErrors {
  const e: PersonErrors = {}
  if (!v.name.trim()) e.name = 'auth.err.required'
  else if (!isValidPersonName(v.name)) e.name = 'auth.err.name'
  if (!v.email.trim()) e.email = 'auth.err.required'
  else if (!isEmail(v.email)) e.email = 'auth.err.email'
  if (!v.phone.trim()) e.phone = 'auth.err.required'
  else if (!isValidSaudiMobile(v.phone)) e.phone = 'auth.err.phone'
  if (!isStrongPassword(v.password)) e.password = 'auth.err.password'
  return e
}
