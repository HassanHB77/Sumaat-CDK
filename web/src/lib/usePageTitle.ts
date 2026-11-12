import { useEffect } from 'react'
import { useLanguage } from '../i18n/LanguageContext'

/** Browser tab title: "<page> · Sumaat" (or just "Sumaat"). Follows the chosen language. */
export function usePageTitle(page?: string | null): void {
  const { t } = useLanguage()
  const app = t('app.name')
  useEffect(() => {
    document.title = page ? `${page} · ${app}` : app
  }, [page, app])
}
