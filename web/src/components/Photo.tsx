import { useState, type ReactNode } from 'react'

/**
 * A restaurant or dish photo, cropped to fill its box. No photo (or it fails to load) -> `fallback`
 * (the plate icon for restaurants; nothing for dishes, which then look exactly as before).
 */
export function Photo({
  src,
  alt = '',
  className = 'size-14',
  dimmed = false,
  fallback = null,
}: {
  src?: string | null
  alt?: string
  className?: string
  dimmed?: boolean
  fallback?: ReactNode
}) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  if (!src || failedSrc === src) return <>{fallback}</>
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      className={`shrink-0 rounded-box bg-base-200 object-cover ${dimmed ? 'opacity-60 grayscale' : ''} ${className}`}
      onError={() => setFailedSrc(src)}
    />
  )
}
