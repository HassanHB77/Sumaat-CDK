import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { changeOrderStatus } from '../api/endpoints'
import type { Order } from '../api/types'
import { useToast } from '../components/Toast'
import { useLanguage } from '../i18n/LanguageContext'
import { beep } from '../lib/sound'
import { createPendingController, newOrderIds, type Pending } from './boardLogic'

export const boardKey = (restaurantId: string) => ['board', restaurantId] as const

/** Staff actions with a 3-second Undo. Nothing reaches the API before the countdown ends. */
export function usePendingActions(restaurantId: string, onNoAccess: () => void) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { t } = useLanguage()
  const [pending, setPending] = useState<Pending[]>([])

  // Keep the latest callbacks without recreating the controller (its timers must survive re-renders).
  const latest = useRef({ toast, t, onNoAccess })
  useEffect(() => {
    latest.current = { toast, t, onNoAccess }
  })

  const controller = useMemo(
    () =>
      createPendingController({
        commit: (p) => changeOrderStatus(p.orderId, p.action, p.reason),
        onChange: setPending,
        onCommitted: () => queryClient.invalidateQueries({ queryKey: boardKey(restaurantId) }),
        onError: (p, error) => {
          const { toast, t, onNoAccess } = latest.current
          queryClient.invalidateQueries({ queryKey: boardKey(restaurantId) })
          if (error instanceof ApiError && (error.status === 403 || error.status === 404)) return onNoAccess()
          const reason = error instanceof ApiError ? error.message : t('auth.err.generic')
          toast.show(t('counter.failed', { n: p.orderNumber, reason }), 'error', 6000)
        },
      }),
    [queryClient, restaurantId],
  )
  useEffect(() => () => controller.dispose(), [controller])

  // Warn before leaving the page while something is still waiting to be sent.
  useEffect(() => {
    if (!pending.length) return
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [pending.length])

  return { pending, start: controller.start, undo: controller.undo }
}

/** Beep + pulse when a new order arrives (not for the ones already there on load), and the tab title count. */
export function useNewOrderAlert(orders: Order[] | undefined, soundOn: boolean) {
  const { t } = useLanguage()
  const seen = useRef<Set<string> | null>(null)
  const [pulse, setPulse] = useState(false)

  useEffect(() => {
    if (!orders) return
    const fresh = newOrderIds(seen.current, orders)
    seen.current = new Set(orders.map((o) => o.id))
    if (!fresh.length) return
    if (soundOn) beep()
    setPulse(true)
    const timer = setTimeout(() => setPulse(false), 3000)
    return () => clearTimeout(timer)
  }, [orders, soundOn])

  const waiting = orders?.filter((o) => o.status === 'PLACED').length ?? 0
  useEffect(() => {
    const before = document.title
    document.title = waiting > 0 ? t('counter.newOrdersTitle', { count: waiting }) : t('app.name')
    return () => {
      document.title = before
    }
  }, [waiting, t])

  return { pulse }
}

/** Re-render every `ms` (for "4 min" labels and Undo countdowns). */
export function useNow(ms: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}
