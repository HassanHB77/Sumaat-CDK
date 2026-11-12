import { useQuery } from '@tanstack/react-query'
import { Link, NavLink } from 'react-router'
import { getMyOrders } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { isOpen } from '../lib/orders'
import { CartIcon } from './CartParts'
import { LanguageToggle } from './LanguageToggle'
import { Logo } from './Logo'
import { UserMenu } from './UserMenu'

/**
 * Header (fixed 56 px high: sticky bars below rely on it).
 * Visitor: Log in. Customer: My orders + name menu. Owner/cashier: name menu only (their own header comes in M4/M5).
 */
export function PublicHeader() {
  const { t } = useLanguage()
  const { status, role } = useAuth()
  const isCustomer = status === 'signedIn' && role === 'customer'
  // Dot on "My orders" while an order is in progress (shares the cache with the My orders page).
  const mine = useQuery({
    queryKey: ['orders', 'mine'],
    queryFn: ({ signal }) => getMyOrders(signal),
    enabled: isCustomer,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })
  const hasActive = isCustomer && Boolean(mine.data?.some((o) => isOpen(o.status)))
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `btn btn-sm btn-ghost hidden sm:inline-flex ${isActive ? 'btn-active' : ''}`

  return (
    <header className="sticky top-0 z-30 bg-secondary text-secondary-content shadow">
      <div className="mx-auto flex h-14 max-w-5xl items-center gap-1 px-4">
        <Link to="/" className="me-auto" aria-label={t('app.name')}>
          <Logo light />
        </Link>
        {(status !== 'signedIn' || role === 'customer') && (
          <NavLink to="/restaurants" className={navClass}>
            {t('nav.restaurants')}
          </NavLink>
        )}
        {status === 'signedIn' && role === 'customer' && (
          <NavLink to="/orders" className={({ isActive }) => `btn btn-sm btn-ghost relative ${isActive ? 'btn-active' : ''}`}>
            {t('nav.orders')}
            {hasActive && (
              <span className="status status-success absolute -end-0.5 top-1 animate-pulse" title={t('nav.activeOrder')} aria-label={t('nav.activeOrder')} />
            )}
          </NavLink>
        )}
        {(status !== 'signedIn' || role === 'customer') && <CartIcon />}
        <LanguageToggle className="text-secondary-content" />
        {status === 'signedIn' ? (
          <UserMenu />
        ) : status === 'signedOut' ? (
          <Link to="/login" className="btn btn-sm btn-primary">
            {t('nav.login')}
          </Link>
        ) : null}
      </div>
    </header>
  )
}
