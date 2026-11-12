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
