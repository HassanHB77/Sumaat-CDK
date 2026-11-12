/** Same rules as the Cognito pool (infra/auth_stack.py) and the API (api/models.py). */
export type PasswordCheck = 'length' | 'upper' | 'lower' | 'digit' | 'symbol'

export function passwordChecks(pw: string): Record<PasswordCheck, boolean> {
  return {
    length: pw.length >= 8,
    upper: /[A-Z]/.test(pw),
    lower: /[a-z]/.test(pw),
    digit: /\d/.test(pw),
    symbol: /[^A-Za-z0-9\s]/.test(pw),
  }
}

export function isStrongPassword(pw: string): boolean {
  return Object.values(passwordChecks(pw)).every(Boolean)
}

// No look-alike characters (0/O, 1/l/I) so a password read aloud or copied by hand works.
const UPPER = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
const LOWER = 'abcdefghijkmnopqrstuvwxyz'
const DIGITS = '23456789'
const SYMBOLS = '#!@$%&*?'
const ALL = UPPER + LOWER + DIGITS + SYMBOLS

function pick(chars: string, rnd: Uint32Array, i: number): string {
  return chars[rnd[i] % chars.length]
}

/** A random password that meets the pool rules (one of each kind), e.g. "kT7#mQ2xPa9r". */
export function generatePassword(length = 12): string {
  const rnd = new Uint32Array(length * 2)
  crypto.getRandomValues(rnd)
  const chars = [pick(UPPER, rnd, 0), pick(LOWER, rnd, 1), pick(DIGITS, rnd, 2), pick(SYMBOLS, rnd, 3)]
  for (let i = 4; i < length; i++) chars.push(pick(ALL, rnd, i))
  // shuffle so the first four aren't always upper, lower, digit, symbol
  for (let i = chars.length - 1; i > 0; i--) {
    const j = rnd[length + i] % (i + 1)
    ;[chars[i], chars[j]] = [chars[j], chars[i]]
  }
  return chars.join('')
}
