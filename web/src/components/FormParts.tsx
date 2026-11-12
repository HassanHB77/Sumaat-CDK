import { useState, type ReactNode } from 'react'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { passwordChecks, type PasswordCheck } from '../lib/password'
import { cleanMobileInput } from '../lib/phone'

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
        <p className="label whitespace-normal text-error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="label whitespace-normal">{hint}</p>
      ) : null}
    </fieldset>
  )
}

/**
 * "+966" fixed box + the rest of the number. Always left-to-right, also in Arabic.
 * Keeps digits only (max 9; a pasted +966 / 00966 / leading 0 is dropped), see cleanMobileInput.
 */
export function PhoneInput({
  value,
  onChange,
  onBlur,
  invalid,
}: {
  value: string
  onChange: (v: string) => void
  onBlur?: () => void
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
        aria-invalid={invalid || undefined}
        value={value}
        onChange={(e) => onChange(cleanMobileInput(e.target.value))}
        onBlur={onBlur}
      />
    </div>
  )
}

export function PasswordInput({
  value,
  onChange,
  autoComplete,
  onBlur,
  invalid,
}: {
  value: string
  onChange: (v: string) => void
  autoComplete: 'current-password' | 'new-password'
  onBlur?: () => void
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
        aria-invalid={invalid || undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
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
