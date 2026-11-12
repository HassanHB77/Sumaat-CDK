import { Link, NavLink } from 'react-router'
import { useLanguage } from '../i18n/LanguageContext'
import { LanguageToggle } from './LanguageToggle'
import { Logo } from './Logo'

/** Header for visitors and customers (fixed 56 px high: sticky bars below rely on it). Cart badge, My orders and real login state arrive in M2/M3. */
export function PublicHeader() {
  const { t } = useLanguage()
  return (
    <header className="sticky top-0 z-30 bg-secondary text-secondary-content shadow">
      <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-4">
        <Link to="/" className="me-auto" aria-label={t('app.name')}>
          <Logo light />
        </Link>
        <NavLink
          to="/restaurants"
          className={({ isActive }) => `btn btn-sm btn-ghost hidden sm:inline-flex ${isActive ? 'btn-active' : ''}`}
        >
          {t('nav.restaurants')}
        </NavLink>
        <LanguageToggle className="text-secondary-content" />
        <Link to="/login" className="btn btn-sm btn-primary">
          {t('nav.login')}
        </Link>
      </div>
    </header>
  )
}
