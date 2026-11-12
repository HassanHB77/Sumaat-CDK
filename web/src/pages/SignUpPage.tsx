import { signUp } from 'aws-amplify/auth'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { cognitoErrorKey } from '../auth/cognitoErrors'
import { FormField, isEmail, PasswordChecklist, PasswordInput, PhoneInput } from '../components/FormParts'
import { PageContainer } from '../components/PageContainer'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'
import { isStrongPassword } from '../lib/password'
import { isValidSaudiMobile, toE164 } from '../lib/phone'

type Errors = Partial<Record<'name' | 'email' | 'phone' | 'password' | 'form', MessageKey>>

/** One form for both: /signup (customer) and /owner/signup (owner -> custom:signupRole = "owner"). */
export function SignUpPage({ role }: { role: 'customer' | 'owner' }) {
  const { t } = useLanguage()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next')
  usePageTitle(t(role === 'owner' ? 'page.ownerSignup' : 'page.signup'))

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)

  function validate(): Errors {
    const e: Errors = {}
    if (!name.trim()) e.name = 'auth.err.required'
    if (!isEmail(email)) e.email = 'auth.err.email'
    if (!isValidSaudiMobile(phone)) e.phone = 'auth.err.phone'
    if (!isStrongPassword(password)) e.password = 'auth.err.password'
    return e
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    const username = email.trim().toLowerCase()
    try {
      const userAttributes: Record<string, string> = { email: username, name: name.trim(), phone_number: toE164(phone) }
      if (role === 'owner') userAttributes['custom:signupRole'] = 'owner'
      await signUp({ username, password, options: { userAttributes, autoSignIn: true } })
      const q = new URLSearchParams({ email: username })
      if (next && role === 'customer') q.set('next', next)
      navigate(`/confirm?${q}`)
    } catch (err) {
      setErrors({ form: cognitoErrorKey(err) })
    } finally {
      setBusy(false)
    }
  }

  const err = (k: keyof Errors) => (errors[k] ? t(errors[k]!) : null)

  return (
    <PageContainer>
      <div className="mx-auto w-full max-w-sm">
        <form onSubmit={onSubmit} noValidate className="card bg-base-100 shadow-sm">
          <div className="card-body gap-1">
            <h1 className="card-title mb-1 text-2xl">{t(role === 'owner' ? 'page.ownerSignup' : 'page.signup')}</h1>
            {role === 'owner' && (
              <>
                <p className="text-sm">{t('auth.signup.ownerIntro')}</p>
                <p className="mb-2 text-sm text-muted">{t('auth.signup.ownerNote')}</p>
              </>
            )}
            <FormField label={t('auth.name')} error={err('name')}>
              <input
                className={`input w-full ${errors.name ? 'input-error' : ''}`}
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </FormField>
            <FormField label={t('auth.email')} error={err('email')}>
              <input
                className={`input w-full ${errors.email ? 'input-error' : ''}`}
                type="email"
                autoComplete="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </FormField>
            <FormField label={t('auth.phone')} error={err('phone')} hint={t('auth.phoneHint')}>
              <PhoneInput value={phone} onChange={setPhone} invalid={Boolean(errors.phone)} />
            </FormField>
            <FormField label={t('auth.password')} error={err('password')}>
              <PasswordInput value={password} onChange={setPassword} autoComplete="new-password" invalid={Boolean(errors.password)} />
              <PasswordChecklist password={password} />
            </FormField>
            {errors.form && (
              <p className="alert alert-error mt-2" role="alert">
                {t(errors.form)}
              </p>
            )}
            <button type="submit" className="btn btn-primary mt-4" disabled={busy}>
              {busy && <span className="loading loading-spinner loading-sm" />}
              {t(role === 'owner' ? 'auth.signup.ownerSubmit' : 'auth.signup.submit')}
            </button>
          </div>
        </form>
        <p className="mt-4 text-center text-sm">
          {t('auth.signup.haveAccount')}{' '}
          <Link className="link link-primary" to={`/login${next ? `?next=${encodeURIComponent(next)}` : ''}`}>
            {t('nav.login')}
          </Link>
        </p>
      </div>
    </PageContainer>
  )
}
