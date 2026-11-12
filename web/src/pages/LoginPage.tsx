import { confirmSignIn, signIn } from 'aws-amplify/auth'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { cognitoErrorKey } from '../auth/cognitoErrors'
import { roleHome } from '../auth/session'
import { FormField, isEmail, PasswordChecklist, PasswordInput } from '../components/FormParts'
import { PageContainer } from '../components/PageContainer'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { isStrongPassword } from '../lib/password'

export function LoginPage() {
  const { t } = useLanguage()
  const { refresh } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next')

  const [email, setEmail] = useState(params.get('email') ?? '')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [step, setStep] = useState<'login' | 'newPassword'>('login')
  const [error, setError] = useState<MessageKey | null>(null)
  const [busy, setBusy] = useState(false)

  async function finish() {
    let user = await refresh(true)
    if (user && !user.role) user = await refresh(true) // group added a moment ago
    navigate(roleHome(user?.role ?? null, next), { replace: true })
  }

  async function onLogin(e: FormEvent) {
    e.preventDefault()
    if (!isEmail(email) || !password) {
      setError(!isEmail(email) ? 'auth.err.email' : 'auth.err.required')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const { nextStep } = await signIn({ username: email.trim(), password })
      if (nextStep.signInStep === 'DONE') return await finish()
      if (nextStep.signInStep === 'CONFIRM_SIGN_UP') {
        return navigate(`/confirm?email=${encodeURIComponent(email.trim())}${next ? `&next=${encodeURIComponent(next)}` : ''}`)
      }
      if (nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') return setStep('newPassword')
      setError('auth.err.generic')
    } catch (err) {
      const key = cognitoErrorKey(err)
      if (key === 'auth.err.notConfirmed') {
        return navigate(`/confirm?email=${encodeURIComponent(email.trim())}`)
      }
      setError(key)
    } finally {
      setBusy(false)
    }
  }

  async function onNewPassword(e: FormEvent) {
    e.preventDefault()
    if (!isStrongPassword(newPassword)) return setError('auth.err.password')
    setBusy(true)
    setError(null)
    try {
      const { nextStep } = await confirmSignIn({ challengeResponse: newPassword })
      if (nextStep.signInStep === 'DONE') return await finish()
      setError('auth.err.generic')
    } catch (err) {
      setError(cognitoErrorKey(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <PageContainer>
      <div className="mx-auto w-full max-w-sm">
        <div className="card bg-base-100 shadow-sm">
          <div className="card-body">
            {step === 'login' ? (
              <form onSubmit={onLogin} noValidate className="flex flex-col gap-1">
                <h1 className="card-title mb-2 text-2xl">{t('page.login')}</h1>
                {params.get('confirmed') && <p className="alert alert-success mb-2">{t('auth.login.confirmed')}</p>}
                <FormField label={t('auth.email')}>
                  <input
                    className="input w-full"
                    type="email"
                    autoComplete="email"
                    dir="ltr"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </FormField>
                <FormField label={t('auth.password')}>
                  <PasswordInput value={password} onChange={setPassword} autoComplete="current-password" />
                </FormField>
                {error && (
                  <p className="alert alert-error mt-2" role="alert">
                    {t(error)}
                  </p>
                )}
                <button type="submit" className="btn btn-primary mt-4" disabled={busy}>
                  {busy && <span className="loading loading-spinner loading-sm" />}
                  {t('auth.login.submit')}
                </button>
              </form>
            ) : (
              <form onSubmit={onNewPassword} noValidate className="flex flex-col gap-1">
                <h1 className="card-title mb-2 text-2xl">{t('auth.newpw.title')}</h1>
                <FormField label={t('auth.newPassword')}>
                  <PasswordInput value={newPassword} onChange={setNewPassword} autoComplete="new-password" />
                  <PasswordChecklist password={newPassword} />
                </FormField>
                {error && (
                  <p className="alert alert-error mt-2" role="alert">
                    {t(error)}
                  </p>
                )}
                <button type="submit" className="btn btn-primary mt-4" disabled={busy}>
                  {t('auth.newpw.submit')}
                </button>
              </form>
            )}
          </div>
        </div>
        <p className="mt-4 text-center text-sm">
          {t('auth.login.noAccount')}{' '}
          <Link className="link link-primary" to={`/signup${next ? `?next=${encodeURIComponent(next)}` : ''}`}>
            {t('nav.signup')}
          </Link>
        </p>
        <p className="mt-1 text-center text-sm text-muted">
          {t('auth.login.ownerQ')}{' '}
          <Link className="link" to="/owner/signup">
            {t('home.owner')}
          </Link>
        </p>
      </div>
    </PageContainer>
  )
}
