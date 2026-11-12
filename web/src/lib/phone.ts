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

/**
 * What the phone box keeps while typing/pasting: Western digits only (Arabic-Indic ٠-٩ / ۰-۹ are converted),
 * without +966 / 00966 / a leading 0, at most 9 digits. "+966 50 123 4567" -> "501234567".
 */
export function cleanMobileInput(raw: string): string {
  let d = (raw ?? '')
    .replace(/[٠-٩]/g, (c) => String(c.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (c) => String(c.charCodeAt(0) - 0x06f0))
    .replace(/\D/g, '')
  if (d.startsWith('00966')) d = d.slice(5)
  else if (d.startsWith('966')) d = d.slice(3)
  if (d.startsWith('0')) d = d.slice(1)
  return d.slice(0, 9)
}
