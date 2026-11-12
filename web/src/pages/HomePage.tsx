import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getNearby } from '../api/endpoints'
import { LogoMark } from '../components/Logo'
import { useLanguage } from '../i18n/LanguageContext'
import { DEFAULT_RADIUS, loadSpot } from '../lib/geo'
import { usePageTitle } from '../lib/usePageTitle'

export function HomePage() {
  const { t } = useLanguage()
  usePageTitle(null)
  // "3 open near you now": one cheap query around the customer's last spot (default Al-Hofuf).
  const nearby = useQuery({
    queryKey: ['home-open-count'],
    queryFn: ({ signal }) => {
      const s = loadSpot()
      return getNearby(s.lat, s.lng, DEFAULT_RADIUS, signal)
    },
    staleTime: 60_000,
  })
  const openCount = nearby.data?.filter((r) => r.openNow).length ?? 0
  const steps = [t('home.step1'), t('home.step2'), t('home.step3')]
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col items-center gap-8 px-4 py-12 text-center">
      <LogoMark className="size-20" />
      <div>
        <h1 className="text-4xl font-bold">{t('app.name')}</h1>
        <p className="mt-2 text-lg text-muted">{t('app.tagline')}</p>
      </div>
      <div className="flex flex-col items-center gap-2">
        <Link to="/restaurants" className="btn btn-primary btn-lg">
          {t('home.find')}
        </Link>
        {openCount > 0 && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <span className="status status-success" aria-hidden="true" />
            {t('home.openNearby', { count: openCount })}
          </p>
        )}
      </div>
      <ol className="steps w-full max-w-xl">
        {steps.map((s) => (
          <li key={s} className="step step-primary">
            {s}
          </li>
        ))}
      </ol>
      <Link to="/owner/signup" className="link link-hover text-muted">
        {t('home.owner')}
      </Link>
    </main>
  )
}
