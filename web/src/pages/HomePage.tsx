import { Link } from 'react-router'
import { LogoMark } from '../components/Logo'
import { StatusLine } from '../components/StatusLine'
import { useLanguage } from '../i18n/LanguageContext'

export function HomePage() {
  const { t } = useLanguage()
  const steps = [t('home.step1'), t('home.step2'), t('home.step3')]
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col items-center gap-8 px-4 py-12 text-center">
      <LogoMark className="size-20" />
      <div>
        <h1 className="text-4xl font-bold">{t('app.name')}</h1>
        <p className="mt-2 text-lg text-muted">{t('app.tagline')}</p>
      </div>
      <Link to="/restaurants" className="btn btn-primary btn-lg">
        {t('home.find')}
      </Link>
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
      <StatusLine />
    </main>
  )
}
