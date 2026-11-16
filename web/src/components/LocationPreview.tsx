import { useState } from 'react'
import { getConfig } from '../config/config'
import { useLanguage } from '../i18n/LanguageContext'
import { staticMapUrl } from '../lib/geo'
import { DirectionsButton } from './DirectionsButton'
import { CENTER_PIN_PATH } from './useMapLibre'

function mapKey(): string {
  try {
    return getConfig().locationApiKey
  } catch {
    return ''
  }
}

/**
 * View-only map of a restaurant's spot (one Amazon Location static image, so nothing to drag or zoom) with a
 * solid "Go" button on its bottom corner. `className` sizes the box; `wide` asks for a wider picture on
 * bigger screens. If the map can't load, only the Go button shows.
 */
export function LocationPreview({
  lat,
  lng,
  name,
  wide = false,
  className = 'h-40',
}: {
  lat: number
  lng: number
  name: string
  wide?: boolean
  className?: string
}) {
  const { t, lang } = useLanguage()
  const key = mapKey()
  const [failed, setFailed] = useState(false)

  if (!key || failed) {
    return (
      <div className="flex justify-end">
        <DirectionsButton lat={lat} lng={lng} name={name} />
      </div>
    )
  }

  const img = (w: number, h: number) => staticMapUrl(lat, lng, lang, key, w, h)
  return (
    <div className={`relative overflow-hidden rounded-box border border-base-300 bg-base-200 ${className}`}>
      <picture>
        {/* Phones: 400x180; wider screens: 600x200 (wide) — the API allows at most 700 wide. */}
        {wide && <source media="(min-width: 640px)" srcSet={img(600, 200)} />}
        <img
          src={wide ? img(400, 180) : img(400, 200)}
          alt={t('map.previewAlt', { name })}
          loading="lazy"
          className="absolute inset-0 h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      </picture>
      {/* The image is centred on the restaurant: the pin's tip marks the centre. */}
      <svg
        viewBox="0 0 24 36"
        className="pointer-events-none absolute left-1/2 top-1/2 h-9 w-6 -translate-x-1/2 -translate-y-full drop-shadow"
        aria-hidden="true"
      >
        <path d={CENTER_PIN_PATH} fill="#FF5722" stroke="#fff" strokeWidth="1.5" />
        <circle cx="12" cy="12" r="4" fill="#fff" />
      </svg>
      <div className="absolute bottom-2 end-2">
        <DirectionsButton lat={lat} lng={lng} name={name} />
      </div>
    </div>
  )
}
