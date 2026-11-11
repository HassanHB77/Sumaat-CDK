import { Link } from 'react-router'
import { PageContainer } from '../components/PageContainer'
import { useLanguage } from '../i18n/LanguageContext'

export function NotFoundPage() {
  const { t } = useLanguage()
  return (
    <PageContainer title={t('notFound.title')}>
      <Link to="/" className="btn btn-primary">
        {t('notFound.home')}
      </Link>
    </PageContainer>
  )
}
