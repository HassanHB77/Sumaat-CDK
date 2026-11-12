import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { getMyOrders, getRestaurant, placeOrder } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { useCart } from '../cart/CartContext'
import { MAX_NOTE, toOrderBody } from '../cart/cartLogic'
import { QtyStepper } from '../components/CartParts'
import { PageContainer } from '../components/PageContainer'
import { EmptyState } from '../components/States'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'
import { formatMoney, pickName } from '../lib/format'
import { findOpenOrderAt } from '../lib/orders'

type Problem = { text: string; orderId?: string } | null

export function CartPage() {
  const { t, lang } = useLanguage()
  const { status } = useAuth()
  const { cart, total, setQty, setNote, clear, reconcileWith } = useCart()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [problem, setProblem] = useState<Problem>(null)
  usePageTitle(t('page.cart'))

  const place = useMutation({
    mutationFn: () => placeOrder(toOrderBody(cart)),
    onSuccess: (order) => {
      clear()
      queryClient.invalidateQueries({ queryKey: ['orders'] })
      navigate(`/orders/${order.id}`, { replace: true })
    },
    onError: async (err) => {
      if (!(err instanceof ApiError)) return setProblem({ text: t('auth.err.generic') })
      if (err.status === 409 && /open order/i.test(err.message)) {
        // Link to the order that blocks this one.
        const mine = await getMyOrders().catch(() => [])
        return setProblem({ text: t('cart.openOrder'), orderId: findOpenOrderAt(mine, cart.restaurantId)?.id })
      }
      if (err.status === 409) return setProblem({ text: t('cart.closed') })
      if (err.status === 422) {
        // Usually a dish was hidden meanwhile: reload the menu and fix the cart.
        const fresh = await getRestaurant(cart.restaurantId).catch(() => null)
        if (fresh) reconcileWith(fresh.id, fresh.menu)
        return setProblem({ text: t('cart.itemsChanged') })
      }
      if (err.status === 0) return setProblem({ text: t('error.network') })
      setProblem({ text: err.message })
    },
  })

  if (!cart.lines.length) {
    return (
      <PageContainer title={t('page.cart')}>
        <EmptyState>
          <p className="mb-4">{t('cart.empty')}</p>
          <Link to="/restaurants" className="btn btn-primary">
            {t('cart.browse')}
          </Link>
        </EmptyState>
      </PageContainer>
    )
  }

  const restaurantName = pickName({ name: cart.restaurantName, nameAr: cart.restaurantNameAr }, lang)

  function onPlace() {
    setProblem(null)
    if (status !== 'signedIn') return navigate('/login?next=/cart')
    place.mutate()
  }

  return (
    <PageContainer title={t('page.cart')}>
      <div className="mx-auto flex max-w-xl flex-col gap-4">
        <Link to={`/r/${cart.restaurantId}`} className="link link-hover w-fit font-medium">
          {t('cart.from', { name: restaurantName })}
        </Link>

        <ul className="flex flex-col gap-2">
          {cart.lines.map((l) => (
            <li key={l.itemId} className="flex items-center justify-between gap-3 rounded-box bg-base-100 p-3 shadow-sm">
              <div className="min-w-0">
                <p className="font-medium">{pickName(l, lang)}</p>
                <p className="text-sm text-muted" dir="ltr">
                  {formatMoney(l.priceHalalas * l.qty, lang)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <QtyStepper qty={l.qty} onChange={(n) => setQty(l.itemId, n)} disabled={place.isPending} />
                <button type="button" className="btn btn-ghost btn-xs" onClick={() => setQty(l.itemId, 0)} disabled={place.isPending}>
                  {t('cart.remove')}
                </button>
              </div>
            </li>
          ))}
        </ul>

        <label className="fieldset">
          <span className="fieldset-legend">{t('cart.note')}</span>
          <textarea
            className="textarea w-full"
            rows={2}
            maxLength={MAX_NOTE}
            placeholder={t('cart.notePlaceholder')}
            value={cart.note}
            onChange={(e) => setNote(e.target.value)}
          />
          <span className="label justify-end" dir="ltr">
            {cart.note.length}/{MAX_NOTE}
          </span>
        </label>

        <div className="flex justify-between rounded-box bg-base-100 p-4 text-lg font-bold shadow-sm">
          <span>{t('cart.total')}</span>
          <span dir="ltr">{formatMoney(total, lang)}</span>
        </div>
        <p className="text-center text-sm text-muted">{t('cart.pickupNotice')}</p>

        {problem && (
          <div role="alert" className="alert alert-warning">
            <span>{problem.text}</span>
            {problem.orderId && (
              <Link to={`/orders/${problem.orderId}`} className="btn btn-sm">
                {t('cart.viewOrder')}
              </Link>
            )}
          </div>
        )}

        <button type="button" className="btn btn-primary btn-lg" onClick={onPlace} disabled={place.isPending}>
          {place.isPending && <span className="loading loading-spinner" />}
          {status === 'signedIn' ? t('cart.place') : t('cart.loginToOrder')}
        </button>
      </div>
    </PageContainer>
  )
}
