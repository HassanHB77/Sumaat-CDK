import { useLanguage } from '../i18n/LanguageContext'

export function LanguageToggle({ className = '' }: { className?: string }) {
  const { t, toggle, lang } = useLanguage()
  return (
    <button
      type="button"
      className={`btn btn-sm btn-ghost ${className}`}
      onClick={toggle}
      aria-label={t('lang.switchLabel')}
      lang={lang === 'ar' ? 'en' : 'ar'}
    >
      {t('lang.switch')}
    </button>
  )
}
