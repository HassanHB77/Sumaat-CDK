/**
 * Saudi mobile numbers. The user types the part after +966 ("5XXXXXXXX"); a leading 0 ("05XXXXXXXX")
 * is accepted and dropped. Spaces and dashes are ignored. Cognito stores E.164: "+9665XXXXXXXX".
 */
export function normalizeSaudiMobile(input: string): string {
  let digits = (input ?? '').replace(/[\s\-()]/g, '')
  if (digits.startsWith('+966')) digits = digits.slice(4)
  else if (digits.startsWith('00966')) digits = digits.slice(5)
  if (digits.startsWith('0')) digits = digits.slice(1)
  return digits
}

export function isValidSaudiMobile(input: string): boolean {
  return /^5\d{8}$/.test(normalizeSaudiMobile(input))
}

export function toE164(input: string): string {
  return `+966${normalizeSaudiMobile(input)}`
}
