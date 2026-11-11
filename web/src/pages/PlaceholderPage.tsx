import { useLocation } from 'react-router'
import { PageContainer } from '../components/PageContainer'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'

/** Stand-in for pages built in later milestones; shows the title, the path and when it arrives. */
export function PlaceholderPage({ titleKey, milestone }: { titleKey: MessageKey; milestone: string }) {
  const { t } = useLanguage()
  const { pathname } = useLocation()
  return (
    <PageContainer title={t(titleKey)}>
      <div className="card bg-base-100 shadow-sm">
        <div className="card-body">
          <p className="text-muted">{t('placeholder.comingIn', { milestone })}</p>
          <code className="text-sm" dir="ltr">
            {pathname}
          </code>
        </div>
      </div>
    </PageContainer>
  )
}
