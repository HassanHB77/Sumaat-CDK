import type { ReactNode } from 'react'
import { useLanguage } from '../i18n/LanguageContext'

export function LoadingState({ rows = 3 }: { rows?: number }) {
  const { t } = useLanguage()
  return (
    <div className="flex flex-col gap-3" aria-busy="true" aria-label={t('state.loading')}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton h-28 w-full" />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  const { t } = useLanguage()
  return (
    <div role="alert" className="alert alert-error">
      <span>{message ?? t('state.error')}</span>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>
          {t('state.retry')}
        </button>
      )}
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="rounded-box bg-base-100 p-8 text-center text-muted shadow-sm">{children}</div>
}
