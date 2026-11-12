import { signUp } from 'aws-amplify/auth'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { cognitoErrorKey } from '../auth/cognitoErrors'
import { FormField, PasswordChecklist, PasswordInput, PhoneInput } from '../components/FormParts'
import { PageContainer } from '../components/PageContainer'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'
import { toE164 } from '../lib/phone'
import { useTouched } from '../lib/useTouched'
import { PERSON_FIELDS, validatePerson, type PersonField } from '../lib/validation'

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
  const [formError, setFormError] = useState<MessageKey | null>(null)
  const [busy, setBusy] = useState(false)
  // Warnings show for a field once it was left (blur) or after submit, and update live from then on.
  const { isTouched, touch, touchAll } = useTouched<PersonField>()
  const found = validatePerson({ name, email, phone, password })
  const shown = (k: PersonField) => (isTouched(k) ? found[k] : undefined)

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault()
    touchAll(PERSON_FIELDS)
    if (Object.keys(found).length) return
    setFormError(null)
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
      setFormError(cognitoErrorKey(err))
    } finally {
      setBusy(false)
    }
  }

  const err = (k: PersonField) => (shown(k) ? t(shown(k)!) : null)

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
                className={`input w-full ${shown('name') ? 'input-error' : ''}`}
                autoComplete="name"
                maxLength={80}
                aria-invalid={Boolean(shown('name')) || undefined}
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={() => touch('name')}
              />
            </FormField>
            <FormField label={t('auth.email')} error={err('email')}>
              <input
                className={`input w-full ${shown('email') ? 'input-error' : ''}`}
                type="email"
                autoComplete="email"
                dir="ltr"
                aria-invalid={Boolean(shown('email')) || undefined}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onBlur={() => touch('email')}
              />
            </FormField>
            <FormField label={t('auth.phone')} error={err('phone')} hint={t('auth.phoneHint')}>
              <PhoneInput value={phone} onChange={setPhone} onBlur={() => touch('phone')} invalid={Boolean(shown('phone'))} />
            </FormField>
            <FormField label={t('auth.password')} error={err('password')}>
              <PasswordInput
                value={password}
                onChange={setPassword}
                autoComplete="new-password"
                onBlur={() => touch('password')}
                invalid={Boolean(shown('password'))}
              />
              <PasswordChecklist password={password} />
            </FormField>
            {formError && (
              <p className="alert alert-error mt-2" role="alert">
                {t(formError)}
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
