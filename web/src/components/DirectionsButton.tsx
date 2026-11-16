import { useLanguage } from '../i18n/LanguageContext'
import { directionsUrl } from '../lib/geo'

/** "Go": opens Google Maps directions to the restaurant (the app on phones that have it, else the website). */
export function DirectionsButton({
  lat,
  lng,
  name,
  className = '',
}: {
  lat: number
  lng: number
  name: string
  className?: string
}) {
  const { t } = useLanguage()
  return (
    <a
      href={directionsUrl(lat, lng)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={t('common.goAria', { name })}
      className={`btn btn-primary btn-sm gap-1 shadow-md ${className}`}
      onClick={(e) => e.stopPropagation()}
    >
      <svg viewBox="0 0 24 24" className="size-4" aria-hidden="true" fill="currentColor">
        <path d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z" />
      </svg>
      {t('common.go')}
    </a>
  )
}
