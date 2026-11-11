import { useLanguage } from '../i18n/LanguageContext'

/** Palm-over-plate mark + "Sumaat · سماط" wordmark. Same mark as public/favicon.svg. */
export function LogoMark({ className = 'size-9' }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="#1E1E24" />
      <path d="M32 14c-2 6-2 12 0 18" stroke="#2ECC71" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M32 18c-6-4-12-3-15 1 5-1 10 0 15 3" fill="#2ECC71" />
      <path d="M32 18c6-4 12-3 15 1-5-1-10 0-15 3" fill="#2ECC71" />
      <path d="M12 38h40a20 14 0 0 1-40 0z" fill="#FF5722" />
      <rect x="10" y="35" width="44" height="4" rx="2" fill="#FF5722" />
    </svg>
  )
}

export function Logo({ light = false }: { light?: boolean }) {
  const { lang } = useLanguage()
  return (
    <span className="inline-flex items-center gap-2">
      <LogoMark />
      <span className={`text-xl font-bold leading-none ${light ? 'text-white' : ''}`}>
        {lang === 'ar' ? (
          <>
            سماط <span className="opacity-60">·</span> <span lang="en">Sumaat</span>
          </>
        ) : (
          <>
            Sumaat <span className="opacity-60">·</span> <span lang="ar">سماط</span>
          </>
        )}
      </span>
    </span>
  )
}
