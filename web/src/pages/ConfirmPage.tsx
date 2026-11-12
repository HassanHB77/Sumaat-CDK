import { autoSignIn, confirmSignUp, resendSignUpCode } from 'aws-amplify/auth'
import { useEffect, useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { cognitoErrorKey } from '../auth/cognitoErrors'
import { roleHome } from '../auth/session'
import { FormField } from '../components/FormParts'
import { rememberVerifyEmailNote } from '../components/VerifyEmailNote'
import { PageContainer } from '../components/PageContainer'
import { useToast } from '../components/Toast'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'

const RESEND_COOLDOWN_S = 30

export function ConfirmPage() {
  const { t } = useLanguage()
  const { refresh } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const email = params.get('email') ?? ''
  const next = params.get('next')
  usePageTitle(t('page.confirm'))

  const [code, setCode] = useState('')
  const [error, setError] = useState<MessageKey | null>(null)
  const [busy, setBusy] = useState(false)
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_S)

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000)
    return () => clearTimeout(timer)
  }, [cooldown])

  if (!email) return <Navigate to="/signup" replace />

  const toLogin = () => navigate(`/login?${new URLSearchParams({ email, confirmed: '1', ...(next ? { next } : {}) })}`, { replace: true })

  async function onConfirm(e: FormEvent) {
    e.preventDefault()
    if (!/^\d{6}$/.test(code.trim())) return setError('auth.err.code')
    setBusy(true)
    setError(null)
    try {
      const { nextStep } = await confirmSignUp({ username: email, confirmationCode: code.trim() })
      if (nextStep.signUpStep !== 'COMPLETE_AUTO_SIGN_IN') return toLogin()
      try {
        await autoSignIn()
      } catch {
        return toLogin() // e.g. the page was reloaded between sign-up and confirm
      }
      let user = await refresh(true)
      if (user && !user.role) user = await refresh(true) // the sign-up trigger adds the group a moment later
      if (user?.role === 'customer') rememberVerifyEmailNote()
      navigate(roleHome(user?.role ?? null, next), { replace: true })
    } catch (err) {
      setError(cognitoErrorKey(err))
    } finally {
      setBusy(false)
    }
  }

  async function onResend() {
    setError(null)
    try {
      await resendSignUpCode({ username: email })
      toast.show(t('auth.confirm.resent'), 'success')
      setCooldown(RESEND_COOLDOWN_S)
    } catch (err) {
      setError(cognitoErrorKey(err))
    }
  }

  return (
    <PageContainer>
      <div className="mx-auto w-full max-w-sm">
        <form onSubmit={onConfirm} noValidate className="card bg-base-100 shadow-sm">
          <div className="card-body gap-2">
            <h1 className="card-title text-2xl">{t('page.confirm')}</h1>
            <p>
              {t('auth.confirm.intro')}{' '}
              <span dir="ltr" className="font-medium">
                {email}
              </span>
            </p>
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
            {error && (
              <p className="alert alert-error" role="alert">
                {t(error)}
              </p>
            )}
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy && <span className="loading loading-spinner loading-sm" />}
              {t('auth.confirm.submit')}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" disabled={cooldown > 0} onClick={onResend}>
              {cooldown > 0 ? t('auth.confirm.resendIn', { s: cooldown }) : t('auth.confirm.resend')}
            </button>
            <p className="text-center text-sm text-muted">{t('auth.confirm.spam')}</p>
          </div>
        </form>
      </div>
    </PageContainer>
  )
}
