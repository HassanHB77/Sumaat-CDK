import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router'
import { useAuth } from './AuthContext'
import { roleHome, type Role } from './session'

function Spinner() {
  return (
    <div className="grid flex-1 place-items-center p-12">
      <span className="loading loading-spinner loading-lg text-primary" />
    </div>
  )
}

/** Only these roles. Signed out -> /login?next=here. Another role -> that role's home. */
export function RequireRole({ roles, children }: { roles: Role[]; children?: ReactNode }) {
  const { status, role } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <Spinner />
  if (status === 'signedOut') {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (!role || !roles.includes(role)) return <Navigate to={roleHome(role)} replace />
  return children ?? <Outlet />
}

/** Public/customer pages: owners and cashiers go to their own area (one role per account). */
export function StaffRedirect({ children }: { children?: ReactNode }) {
  const { status, role } = useAuth()
  if (status === 'signedIn' && (role === 'owner' || role === 'cashier')) return <Navigate to={roleHome(role)} replace />
  return children ?? <Outlet />
}

/** Login / sign-up pages: already signed in -> your home (or ?next for customers). */
export function GuestOnly({ children }: { children?: ReactNode }) {
  const { status, role } = useAuth()
  const [params] = useSearchParams()
  if (status === 'loading') return <Spinner />
  if (status === 'signedIn') return <Navigate to={roleHome(role, params.get('next'))} replace />
  return children ?? <Outlet />
}
