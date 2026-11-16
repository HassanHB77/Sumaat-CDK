import { useId } from 'react'
import { useLanguage } from '../i18n/LanguageContext'

/**
 * Woven-mat mark (a sumaat is the cloth spread for a meal) + "Sumaat · سماط" wordmark.
 * Same drawing as public/favicon.svg and the tile in assets/weave.svg — keep them in sync.
 * White outer edge so the mark stays visible on the dark header.
 */
export function LogoMark({ className = 'size-9' }: { className?: string }) {
  // Unique ids: the mark can appear twice on a page. useId may contain characters not valid in url(#...).
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const weave = `weave-${uid}`
  const clip = `clip-${uid}`
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <pattern id={weave} width="32" height="32" patternUnits="userSpaceOnUse" patternTransform="rotate(45 32 32)">
          <rect x="1" y="1" width="14" height="6.5" rx="1.5" fill="#FF5722" />
          <rect x="1" y="8.5" width="14" height="6.5" rx="1.5" fill="#FF5722" />
          <rect x="17" y="1" width="6.5" height="14" rx="1.5" fill="#1E1E24" />
          <rect x="24.5" y="1" width="6.5" height="14" rx="1.5" fill="#1E1E24" />
          <rect x="1" y="17" width="6.5" height="14" rx="1.5" fill="#1E1E24" />
          <rect x="8.5" y="17" width="6.5" height="14" rx="1.5" fill="#1E1E24" />
          <rect x="17" y="17" width="14" height="6.5" rx="1.5" fill="#FF5722" />
          <rect x="17" y="24.5" width="14" height="6.5" rx="1.5" fill="#FF5722" />
        </pattern>
        <clipPath id={clip}>
          <circle cx="32" cy="32" r="23" />
        </clipPath>
      </defs>
      <circle cx="32" cy="32" r="32" fill="#FFFFFF" />
      <circle cx="32" cy="32" r="28" fill="none" stroke="#1E1E24" strokeWidth="4.5" />
      <rect width="64" height="64" fill={`url(#${weave})`} clipPath={`url(#${clip})`} />
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
