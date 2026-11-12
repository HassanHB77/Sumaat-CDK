import { useState, type ReactNode } from 'react'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { passwordChecks, type PasswordCheck } from '../lib/password'

export function FormField({
  label,
  error,
  hint,
  children,
}: {
  label: string
  error?: string | null
  hint?: string
  children: ReactNode
}) {
  return (
    <fieldset className="fieldset">
      <legend className="fieldset-legend">{label}</legend>
      {children}
      {error ? (
        <p className="label text-error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="label">{hint}</p>
      ) : null}
    </fieldset>
  )
}

/** "+966" fixed box + the rest of the number. Always left-to-right, also in Arabic. */
export function PhoneInput({
  value,
  onChange,
  invalid,
}: {
  value: string
  onChange: (v: string) => void
  invalid?: boolean
}) {
  return (
    <div className="join w-full" dir="ltr">
      <span className="join-item btn btn-disabled pointer-events-none !text-base-content">+966</span>
      <input
        className={`input join-item w-full ${invalid ? 'input-error' : ''}`}
        type="tel"
        inputMode="numeric"
        autoComplete="tel-national"
        placeholder="5XXXXXXXX"
        maxLength={13}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}

export function PasswordInput({
  value,
  onChange,
  autoComplete,
  invalid,
}: {
  value: string
  onChange: (v: string) => void
  autoComplete: 'current-password' | 'new-password'
  invalid?: boolean
}) {
  const { t } = useLanguage()
  const [show, setShow] = useState(false)
  return (
    <div className="join w-full" dir="ltr">
      <input
        className={`input join-item w-full ${invalid ? 'input-error' : ''}`}
        type={show ? 'text' : 'password'}
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <button type="button" className="btn join-item" onClick={() => setShow((s) => !s)} aria-pressed={show}>
        {show ? t('auth.hide') : t('auth.show')}
      </button>
    </div>
  )
}

const CHECKS: PasswordCheck[] = ['length', 'upper', 'lower', 'digit', 'symbol']

/** Live checklist of the pool's password rules. */
export function PasswordChecklist({ password }: { password: string }) {
  const { t } = useLanguage()
  const checks = passwordChecks(password)
  return (
    <ul className="mt-1 grid grid-cols-1 gap-x-4 gap-y-0.5 text-sm sm:grid-cols-2">
      {CHECKS.map((c) => (
        <li key={c} className={checks[c] ? 'text-success' : 'text-muted'}>
          <span aria-hidden="true">{checks[c] ? '✓' : '○'}</span> {t(`auth.pw.${c}` as MessageKey)}
        </li>
      ))}
    </ul>
  )
}

/** name@domain.tld; no spaces, commas, semicolons or brackets. Same rule as the API (api/models.py). */
export const isEmail = (v: string) => /^[^@\s,;<>()[\]]+@[^@\s,;<>()[\]]+\.[A-Za-z]{2,}$/.test(v.trim())
