import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'

const KEY = 'sumaat.verifyEmailNote'

/** Remember to show the note once (called after a customer confirms their account). */
export function rememberVerifyEmailNote(): void {
  try {
    localStorage.setItem(KEY, '1')
  } catch {
    /* ignore */
  }
}

/**
 * SES sandbox: a new customer gets a second email from AWS; clicking its link lets pickup emails reach them.
 * Shown once after sign-up until dismissed.
 */
export function VerifyEmailNote() {
  const { t } = useLanguage()
  const { role } = useAuth()
  const [show, setShow] = useState(() => {
    try {
      return localStorage.getItem(KEY) === '1'
    } catch {
      return false
    }
  })
  if (!show || role !== 'customer') return null

  function dismiss() {
    try {
      localStorage.removeItem(KEY)
    } catch {
      /* ignore */
    }
    setShow(false)
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 pt-4">
      <div role="status" className="alert alert-info grid-cols-[1fr_auto]">
        <span>📧 {t('verify.note')}</span>
        <button type="button" className="btn btn-sm shrink-0 whitespace-nowrap" onClick={dismiss}>
          {t('verify.ok')}
        </button>
      </div>
    </div>
  )
}
