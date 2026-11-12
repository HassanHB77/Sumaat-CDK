import { useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'
import { ON_DARK } from './onDark'

/** Name + Log out (DaisyUI dropdown). */
export function UserMenu() {
  const { user, logout } = useAuth()
  const { t } = useLanguage()
  const navigate = useNavigate()
  if (!user) return null
  const first = user.name.split(' ')[0] || user.email

  async function onLogout() {
    await logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="dropdown dropdown-end">
      <div tabIndex={0} role="button" className={`btn btn-sm btn-ghost max-w-40 truncate ${ON_DARK}`}>
        {t('auth.hello', { name: first })}
      </div>
      <ul tabIndex={0} className="menu dropdown-content z-40 mt-2 w-60 flex-nowrap rounded-box bg-base-100 p-2 text-base-content shadow">
        {/* DaisyUI .menu wraps (rows grow to their content): flex-nowrap above + this row capped, span clips with "…". */}
        <li className="menu-title min-w-0 max-w-full">
          <span className="block truncate text-start" dir="ltr" title={user.email}>
            {user.email}
          </span>
        </li>
        <li>
          <button type="button" onClick={onLogout}>
            {t('auth.logout')}
          </button>
        </li>
      </ul>
    </div>
  )
}
