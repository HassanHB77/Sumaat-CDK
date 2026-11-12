import { describe, expect, it } from 'vitest'
import { cognitoErrorKey } from '../auth/cognitoErrors'
import { cleanMobileInput } from './phone'
import { isValidPersonName, validatePerson } from './validation'

// Same examples as tests/unit/functions/test_pre_sign_up.py (server rules), so both sides agree.
const GOOD_NAMES = [
  'Sara',
  'Sara Al-Ahmad',
  "O'Brien",
  'O’Brien',
  'Abdullah Jr.',
  'سارة',
  'مُحَمَّد الحَسَاوي',
  'سارة 🌸',
  'Omar 👨‍🍳',
  'Reem ❤️',
  '  Sara  ',
  'a'.repeat(80),
]
const BAD_NAMES = [
  '',
  '   ',
  'Sara2',
  'سارة٣',
  'سارة۳',
  'a@b',
  'Sara_Q',
  '!!',
  'Sara!',
  'Sara #1',
  '🌸',
  "-.'",
  'Omar 1️⃣',
  'سارة؟',
  '<script>',
  'a'.repeat(81),
]

describe('isValidPersonName', () => {
  it.each(GOOD_NAMES)('%s is valid', (n) => expect(isValidPersonName(n)).toBe(true))
  it.each(BAD_NAMES)('%s is invalid', (n) => expect(isValidPersonName(n)).toBe(false))
})

describe('validatePerson', () => {
  const good = { name: 'Sara Al-Ahmad', email: 'sara@example.com', phone: '501234567', password: 'Sumaat#1' }
  it('good input has no warnings', () => expect(validatePerson(good)).toEqual({}))
  it('says which field is wrong', () => {
    expect(validatePerson({ name: 'Sara2', email: 'sara@', phone: '501628333999', password: 'weak' })).toEqual({
      name: 'auth.err.name',
      email: 'auth.err.email',
      phone: 'auth.err.phone',
      password: 'auth.err.password',
    })
  })
  it('empty fields are "required"', () => {
    const e = validatePerson({ name: ' ', email: '', phone: '', password: '' })
    expect([e.name, e.email, e.phone]).toEqual(['auth.err.required', 'auth.err.required', 'auth.err.required'])
  })
})

describe('cleanMobileInput (phone box)', () => {
  it.each([
    ['5016283339999', '501628333'], // capped at 9 digits
    ['0501234567', '501234567'], // leading 0 dropped
    ['+966 50 123 4567', '501234567'], // pasted with country code and spaces
    ['00966501234567', '501234567'],
    ['50-123-4567', '501234567'],
    ['٥٠١٢٣٤٥٦٧', '501234567'], // Arabic-Indic digits from an Arabic keyboard
    ['۵۰۱۲۳۴۵۶۷', '501234567'], // Persian digits
    ['5abc0', '50'],
    ['', ''],
  ])('%s -> %s', (raw, out) => expect(cleanMobileInput(raw)).toBe(out))
})

describe('cognitoErrorKey: pre sign-up refusals', () => {
  it.each([
    ['PreSignUp failed with error invalid_name.', 'auth.err.name'],
    ['PreSignUp failed with error invalid_email.', 'auth.err.email'],
    ['PreSignUp failed with error invalid_phone.', 'auth.err.phone'],
    ['PreSignUp failed with error something else.', 'auth.err.generic'],
  ])('%s -> %s', (message, key) =>
    expect(cognitoErrorKey({ name: 'UserLambdaValidationException', message })).toBe(key),
  )
})
