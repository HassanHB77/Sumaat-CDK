import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import { getConfig } from '../config/config'
import { useLanguage } from '../i18n/LanguageContext'

/** M0 only: proves the wiring (config.json loaded, /api reachable). Removed in M1. */
export function StatusLine() {
  const { t } = useLanguage()
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<{ status: string }>('/health'),
    retry: 1,
  })
  let configOk = false
  try {
    configOk = Boolean(getConfig().userPoolId)
  } catch {
    configOk = false
  }
  const api = health.isPending ? '…' : health.data?.status === 'ok' ? '✅' : '❌'

  return (
    <p className="text-sm text-muted" dir="ltr" data-testid="status-line">
      {t('status.api')} {api} · {t('status.config')} {configOk ? '✅' : '❌'} · {t('status.build')}{' '}
      {__BUILD_TIME__.slice(0, 16).replace('T', ' ')} UTC
    </p>
  )
}
