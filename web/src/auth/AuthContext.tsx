import { useQueryClient } from '@tanstack/react-query'
import { fetchAuthSession, signOut } from 'aws-amplify/auth'
import { Hub } from 'aws-amplify/utils'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { configureApi } from '../api/client'
import { userFromPayload, type Role, type SessionUser } from './session'

type Status = 'loading' | 'signedOut' | 'signedIn'

type AuthValue = {
  status: Status
  user: SessionUser | null
  role: Role | null
  restaurantId: string | null
  /** Re-read the session. force = ask Cognito for fresh tokens (new groups / custom:restaurantId). */
  refresh: (force?: boolean) => Promise<SessionUser | null>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

async function readUser(force: boolean): Promise<SessionUser | null> {
  try {
    const { tokens } = await fetchAuthSession({ forceRefresh: force })
    const payload = tokens?.idToken?.payload
    return payload ? userFromPayload(payload as Record<string, unknown>) : null
  } catch {
    return null // no session / refresh token expired
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<Status>('loading')
  const [user, setUser] = useState<SessionUser | null>(null)

  const refresh = useCallback(async (force = false) => {
    const next = await readUser(force)
    setUser(next)
    setStatus(next ? 'signedIn' : 'signedOut')
    return next
  }, [])

  const logout = useCallback(async () => {
    try {
      await signOut()
    } finally {
      queryClient.clear() // never show the previous user's orders to the next one
      setUser(null)
      setStatus('signedOut')
    }
  }, [queryClient])

  useEffect(() => {
    refresh()
    // Keep every page in sync with Amplify (login, logout, token refresh, other tabs).
    const stop = Hub.listen('auth', ({ payload }) => {
      if (['signedIn', 'signedOut', 'tokenRefresh', 'tokenRefresh_failure'].includes(payload.event)) refresh()
    })
    return stop
  }, [refresh])

  useEffect(() => {
    // The API client calls this when the token is rejected even after a refresh.
    configureApi({
      onSignedOut: () => {
        const here = window.location.pathname + window.location.search
        logout().finally(() => window.location.assign(`/login?next=${encodeURIComponent(here)}`))
      },
    })
  }, [logout])

  const value = useMemo<AuthValue>(
    () => ({
      status,
      user,
      role: user?.role ?? null,
      restaurantId: user?.restaurantId ?? null,
      refresh,
      logout,
    }),
    [status, user, refresh, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
