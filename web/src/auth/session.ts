/** Pure helpers for the signed-in user (no Amplify here, so they're easy to test). */

export type Role = 'customer' | 'owner' | 'cashier'

export type SessionUser = {
  sub: string
  name: string
  email: string
  role: Role | null // exactly one group per account; null = not assigned yet (just confirmed)
  restaurantId: string | null // owner (after creating a restaurant) and cashier
}

const ROLES: Role[] = ['customer', 'owner', 'cashier']

/** Build the user from the Cognito ID token payload. */
export function userFromPayload(payload: Record<string, unknown>): SessionUser {
  const raw = payload['cognito:groups']
  const groups = Array.isArray(raw) ? raw.map(String) : typeof raw === 'string' ? [raw] : []
  const role = (ROLES.find((r) => groups.includes(r)) ?? null) as Role | null
  return {
    sub: String(payload.sub ?? ''),
    name: String(payload.name ?? ''),
    email: String(payload.email ?? ''),
    role,
    restaurantId: payload['custom:restaurantId'] ? String(payload['custom:restaurantId']) : null,
  }
}

/** Only same-site paths are allowed as ?next= (so a link can't send people to another website). */
export function safeNext(next: string | null | undefined): string | null {
  if (!next) return null
  if (!next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) return null
  if (next.startsWith('/login') || next.startsWith('/signup') || next.startsWith('/confirm')) return null
  return next
}

/** Where each role lands after login. Customers may continue to `next` (e.g. /cart); staff always go home. */
export function roleHome(role: Role | null, next?: string | null): string {
  if (role === 'owner') return '/owner'
  if (role === 'cashier') return '/counter'
  if (role === 'customer') {
    const target = safeNext(next)
    // a customer never needs staff pages
    if (target && !target.startsWith('/owner') && !target.startsWith('/counter')) return target
    return '/restaurants'
  }
  return '/'
}
