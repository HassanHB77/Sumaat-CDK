import { Link, NavLink } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
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
          <NavLink to="/orders" className={({ isActive }) => `btn btn-sm btn-ghost ${isActive ? 'btn-active' : ''}`}>
            {t('nav.orders')}
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
