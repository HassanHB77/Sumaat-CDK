import { confirmResetPassword, resetPassword } from 'aws-amplify/auth'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { cognitoErrorKey } from '../auth/cognitoErrors'
import { FormField, isEmail, PasswordChecklist, PasswordInput } from '../components/FormParts'
import { PageContainer } from '../components/PageContainer'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { isStrongPassword } from '../lib/password'
import { usePageTitle } from '../lib/usePageTitle'

/** Step 1: email -> Cognito emails a code. Step 2: code + new password -> back to login. */
export function ForgotPasswordPage() {
  const { t } = useLanguage()
  usePageTitle(t('page.forgot'))
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [step, setStep] = useState<'email' | 'code'>('email')
  const [email, setEmail] = useState(params.get('email') ?? '')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<MessageKey | null>(null)
  const [busy, setBusy] = useState(false)

  async function sendCode(e: FormEvent) {
    e.preventDefault()
    if (!isEmail(email)) return setError('auth.err.email')
    setBusy(true)
    setError(null)
    try {
      await resetPassword({ username: email.trim().toLowerCase() })
      setStep('code')
    } catch (err) {
      const key = cognitoErrorKey(err)
      // Don't reveal whether the email has an account: unknown users go to step 2 like everyone else.
      if (key === 'auth.err.wrongCredentials') setStep('code')
      else setError(key)
    } finally {
      setBusy(false)
    }
  }

  async function setNew(e: FormEvent) {
    e.preventDefault()
    if (!/^\d{6}$/.test(code.trim())) return setError('auth.err.code')
    if (!isStrongPassword(password)) return setError('auth.err.password')
    setBusy(true)
    setError(null)
    try {
      await confirmResetPassword({ username: email.trim().toLowerCase(), confirmationCode: code.trim(), newPassword: password })
      navigate(`/login?${new URLSearchParams({ email: email.trim().toLowerCase(), reset: '1' })}`, { replace: true })
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
          <div className="card-body gap-2">
            <h1 className="card-title text-2xl">{t('page.forgot')}</h1>
            {step === 'email' ? (
              <form onSubmit={sendCode} noValidate className="flex flex-col gap-2">
                <p className="text-sm text-muted">{t('forgot.intro')}</p>
                <FormField label={t('auth.email')}>
                  <input className="input w-full" type="email" autoComplete="email" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} />
                </FormField>
                {error && (
                  <p role="alert" className="alert alert-error">
                    {t(error)}
                  </p>
                )}
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy && <span className="loading loading-spinner loading-sm" />}
                  {t('forgot.send')}
                </button>
              </form>
            ) : (
              <form onSubmit={setNew} noValidate className="flex flex-col gap-2">
                <p className="text-sm">{t('forgot.sent')}</p>
                <FormField label={t('auth.confirm.code')}>
                  <input
                    className="input w-full text-center text-2xl tracking-[0.5em]"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    dir="ltr"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                    autoFocus
                  />
                </FormField>
                <FormField label={t('auth.newPassword')}>
                  <PasswordInput value={password} onChange={setPassword} autoComplete="new-password" />
                  <PasswordChecklist password={password} />
                </FormField>
                {error && (
                  <p role="alert" className="alert alert-error">
                    {t(error)}
                  </p>
                )}
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  {busy && <span className="loading loading-spinner loading-sm" />}
                  {t('forgot.save')}
                </button>
                <p className="text-center text-sm text-muted">{t('auth.confirm.spam')}</p>
              </form>
            )}
          </div>
        </div>
        <p className="mt-4 text-center text-sm">
          <Link to="/login" className="link">
            {t('auth.login.submit')}
          </Link>
        </p>
      </div>
    </PageContainer>
  )
}
