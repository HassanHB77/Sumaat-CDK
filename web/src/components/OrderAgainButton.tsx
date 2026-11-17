import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { getRestaurant } from '../api/endpoints'
import type { Order } from '../api/types'
import { useCart } from '../cart/CartContext'
import { draftFromOrder, isEmpty } from '../cart/cartLogic'
import { useLanguage } from '../i18n/LanguageContext'
import { pickName } from '../lib/format'
import { ConfirmDialog } from './ConfirmDialog'
import { useToast } from './Toast'

/**
 * "Order again": the cart becomes this order's dishes at today's prices (hidden/removed dishes are skipped and named
 * in a toast). If the cart already has dishes, ask first. Then go to the cart, where the customer can still change it.
 */
export function OrderAgainButton({ order, className = 'btn btn-sm btn-outline' }: { order: Order; className?: string }) {
  const { t, lang } = useLanguage()
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { cart, replaceWith } = useCart()
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState(false)

  async function run() {
    setConfirm(false)
    setBusy(true)
    try {
      const restaurant = await queryClient.fetchQuery({
        queryKey: ['restaurant', order.restaurantId],
        queryFn: ({ signal }) => getRestaurant(order.restaurantId, signal),
        staleTime: 30_000,
      })
      const { draft, skipped } = draftFromOrder(order, restaurant)
      if (!draft) {
        toast.show(t('order.againNothing'), 'error', 6000)
        return
      }
      replaceWith(draft)
      if (skipped.length) {
        toast.show(t('order.againSkipped', { names: skipped.map((s) => pickName(s, lang)).join(lang === 'ar' ? '، ' : ', ') }), 'info', 7000)
      }
      navigate('/cart')
    } catch {
      toast.show(t('auth.err.generic'), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        type="button"
        className={className}
        disabled={busy}
        onClick={(e) => {
          e.preventDefault() // also used inside a link row
          e.stopPropagation()
          if (isEmpty(cart)) void run()
          else setConfirm(true)
        }}
      >
        {busy ? <span className="loading loading-spinner loading-xs" /> : (
          <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M4 12a8 8 0 1 0 2.3-5.7M4 4v4h4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
        {t('order.again')}
      </button>
      <ConfirmDialog
        open={confirm}
        title={t('order.againTitle')}
        confirmLabel={t('order.againConfirm')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => void run()}
        onCancel={() => setConfirm(false)}
      >
        {t('order.againBody')}
      </ConfirmDialog>
    </>
  )
}
