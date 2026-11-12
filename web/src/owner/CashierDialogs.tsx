import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import type { CashierInput } from '../api/endpoints'
import { FormField, isEmail, PasswordChecklist, PasswordInput, PhoneInput } from '../components/FormParts'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { generatePassword, isStrongPassword } from '../lib/password'
import { isValidSaudiMobile, toE164 } from '../lib/phone'

type Fields = 'name' | 'email' | 'phone' | 'password'

export function validateCashier(v: Record<Fields, string>): Partial<Record<Fields, MessageKey>> {
  const e: Partial<Record<Fields, MessageKey>> = {}
  if (!v.name.trim()) e.name = 'auth.err.required'
  if (!isEmail(v.email)) e.email = 'auth.err.email'
  if (!isValidSaudiMobile(v.phone)) e.phone = 'auth.err.phone'
  if (!isStrongPassword(v.password)) e.password = 'auth.err.password'
  return e
}

/** <dialog> wrapper: opens/closes with `open`, Esc/backdrop call onClose. */
function Modal({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog ref={ref} className="modal modal-bottom sm:modal-middle" onClose={onClose}>
      {children}
      <form method="dialog" className="modal-backdrop">
        <button type="submit" aria-label="close" />
      </form>
    </dialog>
  )
}

function PasswordWithGenerate({ value, onChange, invalid }: { value: string; onChange: (v: string) => void; invalid: boolean }) {
  const { t } = useLanguage()
  return (
    <>
      <div className="flex gap-2">
        <div className="flex-1">
          <PasswordInput value={value} onChange={onChange} autoComplete="new-password" invalid={invalid} />
        </div>
        <button type="button" className="btn" onClick={() => onChange(generatePassword())}>
          {t('cashiers.generate')}
        </button>
      </div>
      <PasswordChecklist password={value} />
    </>
  )
}

/** Add a cashier: name, email, phone, password (owner shares it; no email is sent). */
export function AddCashierDialog({
  open,
  busy,
  serverError,
  onCancel,
  onSave,
}: {
  open: boolean
  busy: boolean
  serverError: string | null
  onCancel: () => void
  onSave: (input: CashierInput) => void
}) {
  const { t } = useLanguage()
  const empty = { name: '', email: '', phone: '', password: '' }
  const [v, setV] = useState(empty)
  const [errors, setErrors] = useState<Partial<Record<Fields, MessageKey>>>({})

  useEffect(() => {
    if (open) {
      setV({ ...empty, password: generatePassword() })
      setErrors({})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const set = (k: Fields, value: string) => setV((old) => ({ ...old, [k]: value }))
  const err = (k: Fields) => (errors[k] ? t(errors[k]!) : null)

  function submit(e: FormEvent) {
    e.preventDefault()
    const found = validateCashier(v)
    setErrors(found)
    if (Object.keys(found).length) return
    onSave({ name: v.name.trim(), email: v.email.trim().toLowerCase(), phone: toE164(v.phone), password: v.password })
  }

  return (
    <Modal open={open} onClose={onCancel}>
      <form onSubmit={submit} noValidate className="modal-box flex flex-col gap-1">
        <h3 className="text-lg font-bold">{t('cashiers.add')}</h3>
        <FormField label={t('auth.name')} error={err('name')}>
          <input className="input w-full" maxLength={80} value={v.name} onChange={(e) => set('name', e.target.value)} />
        </FormField>
        <FormField label={t('auth.email')} error={err('email')}>
          <input className="input w-full" type="email" dir="ltr" value={v.email} onChange={(e) => set('email', e.target.value)} />
        </FormField>
        <FormField label={t('auth.phone')} error={err('phone')} hint={t('auth.phoneHint')}>
          <PhoneInput value={v.phone} onChange={(x) => set('phone', x)} invalid={Boolean(errors.phone)} />
        </FormField>
        <FormField label={t('auth.password')} error={err('password')}>
          <PasswordWithGenerate value={v.password} onChange={(x) => set('password', x)} invalid={Boolean(errors.password)} />
        </FormField>
        {serverError && (
          <p role="alert" className="alert alert-error mt-2">
            {serverError}
          </p>
        )}
        <div className="modal-action">
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy && <span className="loading loading-spinner loading-sm" />}
            {t('cashiers.create')}
          </button>
        </div>
      </form>
    </Modal>
  )
}

/** Owner sets a new password for a cashier (forgotten password); their old sessions end. */
export function ResetPasswordDialog({
  name,
  busy,
  onCancel,
  onSave,
}: {
  name: string | null // null = closed
  busy: boolean
  onCancel: () => void
  onSave: (password: string) => void
}) {
  const { t } = useLanguage()
  const [password, setPassword] = useState('')
  const [invalid, setInvalid] = useState(false)

  useEffect(() => {
    if (name !== null) {
      setPassword(generatePassword())
      setInvalid(false)
    }
  }, [name])

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!isStrongPassword(password)) return setInvalid(true)
    onSave(password)
  }

  return (
    <Modal open={name !== null} onClose={onCancel}>
      <form onSubmit={submit} noValidate className="modal-box flex flex-col gap-2">
        <h3 className="text-lg font-bold">{t('cashiers.resetTitle', { name: name ?? '' })}</h3>
        <FormField label={t('auth.newPassword')} error={invalid ? t('auth.err.password') : null}>
          <PasswordWithGenerate value={password} onChange={setPassword} invalid={invalid} />
        </FormField>
        <div className="modal-action">
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy && <span className="loading loading-spinner loading-sm" />}
            {t('cashiers.resetSave')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
