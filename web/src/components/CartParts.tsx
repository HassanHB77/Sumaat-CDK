import { Link, useLocation } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { useCart } from '../cart/CartContext'
import { MAX_QTY } from '../cart/cartLogic'
import { useLanguage } from '../i18n/LanguageContext'
import { formatMoney } from '../lib/format'

/** − n + (always left-to-right so the buttons don't swap sides in Arabic). */
export function QtyStepper({
  qty,
  onChange,
  disabled = false,
  size = 'sm',
}: {
  qty: number
  onChange: (qty: number) => void
  disabled?: boolean
  size?: 'xs' | 'sm'
}) {
  const btn = `btn btn-${size} btn-square`
  return (
    <div className="join" dir="ltr">
      <button type="button" className={`${btn} join-item`} onClick={() => onChange(qty - 1)} disabled={disabled} aria-label="−">
        −
      </button>
      <span className={`join-item grid min-w-9 place-items-center border-y border-base-300 bg-base-100 px-2 font-bold`} aria-live="polite">
        {qty}
      </span>
      <button
        type="button"
        className={`${btn} join-item btn-primary`}
        onClick={() => onChange(qty + 1)}
        disabled={disabled || qty >= MAX_QTY}
        aria-label="+"
      >
        +
      </button>
    </div>
  )
}

/** Floating "View cart · 3 items · 45.00 SAR" at the bottom of browse pages. Hidden on /cart and for staff. */
export function CartBar() {
  const { cart, count, total } = useCart()
  const { role } = useAuth()
  const { t, lang } = useLanguage()
  const { pathname } = useLocation()
  if (!count || pathname === '/cart' || role === 'owner' || role === 'cashier') return null
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-30 p-4">
      <Link
        to="/cart"
        className="btn btn-primary btn-lg pointer-events-auto mx-auto flex w-full max-w-xl justify-between shadow-lg"
      >
        <span>{t('cart.view')}</span>
        <span className="text-base font-normal">
          {t('cart.items', { count })} · <span dir="ltr">{formatMoney(total, lang)}</span>
        </span>
      </Link>
      {cart.restaurantId && <span className="sr-only">{cart.restaurantName}</span>}
    </div>
  )
}

/** Cart icon with a count badge (header). */
export function CartIcon() {
  const { count } = useCart()
  const { t } = useLanguage()
  return (
    <Link to="/cart" className="btn btn-sm btn-ghost btn-square relative" aria-label={t('nav.cart')}>
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="10" cy="20" r="1.4" />
        <circle cx="17" cy="20" r="1.4" />
      </svg>
      {count > 0 && <span className="badge badge-primary badge-xs absolute -end-1 -top-1">{count}</span>}
    </Link>
  )
}
