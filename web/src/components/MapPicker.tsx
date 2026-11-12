import { useEffect, useRef, useState } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { getConfig } from '../config/config'
import { useLanguage } from '../i18n/LanguageContext'
import { isInAlAhsa, PRESETS } from '../lib/geo'
import { useToast } from './Toast'

export type LatLng = { lat: number; lng: number }

const round5 = (n: number) => Math.round(n * 1e5) / 1e5

function styleUrl(key: string): string {
  // Amazon Location Service, Maps v2. The key is public by design and only works from our site + localhost.
  return `https://maps.geo.us-east-1.amazonaws.com/v2/styles/Standard/descriptor?key=${encodeURIComponent(key)}`
}

/**
 * Pick a spot: drag the map, the pin stays in the middle. MapLibre (~200 KB) is loaded only when this component
 * is shown. If the map can't load, the shortcuts + number fields still work.
 */
export function MapPicker({ value, onChange }: { value: LatLng; onChange: (v: LatLng) => void }) {
  const { t } = useLanguage()
  const toast = useToast()
  const box = useRef<HTMLDivElement>(null)
  const map = useRef<MapLibreMap | null>(null)
  const onChangeRef = useRef(onChange)
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading')

  useEffect(() => {
    onChangeRef.current = onChange
  })

  // Create the map once.
  useEffect(() => {
    let cancelled = false
    let key = ''
    try {
      key = getConfig().locationApiKey
    } catch {
      key = ''
    }
    if (!key) {
      setState('failed')
      return
    }
    ;(async () => {
      try {
        const [ml] = await Promise.all([import('maplibre-gl'), import('maplibre-gl/dist/maplibre-gl.css')])
        if (cancelled || !box.current) return
        const m = new ml.Map({
          container: box.current,
          style: styleUrl(key),
          center: [value.lng, value.lat],
          zoom: 15,
          attributionControl: { compact: true }, // attribution must stay visible
        })
        m.addControl(new ml.NavigationControl({ showCompass: false }), 'top-right')
        m.on('load', () => !cancelled && setState('ready'))
        m.on('error', () => {
          if (!m.isStyleLoaded() && !cancelled) setState('failed') // style/key problem; tile hiccups are ignored
        })
        m.on('moveend', () => {
          const c = m.getCenter()
          onChangeRef.current({ lat: round5(c.lat), lng: round5(c.lng) })
        })
        map.current = m
      } catch {
        if (!cancelled) setState('failed')
      }
    })()
    return () => {
      cancelled = true
      map.current?.remove()
      map.current = null
    }
    // the starting point only matters once; later changes are handled below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Shortcut buttons / number fields move the map.
  useEffect(() => {
    const m = map.current
    if (!m) return
    const c = m.getCenter()
    if (Math.abs(c.lat - value.lat) > 1e-5 || Math.abs(c.lng - value.lng) > 1e-5) m.jumpTo({ center: [value.lng, value.lat] })
  }, [value.lat, value.lng])

  function useMyLocation() {
    if (!('geolocation' in navigator)) return toast.show(t('loc.failed'), 'error')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords
        if (!isInAlAhsa(lat, lng)) return toast.show(t('loc.outside'), 'info', 6000)
        onChange({ lat: round5(lat), lng: round5(lng) })
      },
      () => toast.show(t('loc.failed'), 'error'),
      { timeout: 10_000, maximumAge: 300_000 },
    )
  }

  const chip = 'btn btn-sm rounded-full btn-outline'
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        <button type="button" className={chip} onClick={() => onChange({ lat: PRESETS.hofuf.lat, lng: PRESETS.hofuf.lng })}>
          {t('loc.hofuf')}
        </button>
        <button type="button" className={chip} onClick={() => onChange({ lat: PRESETS.mubarraz.lat, lng: PRESETS.mubarraz.lng })}>
          {t('loc.mubarraz')}
        </button>
        <button type="button" className={chip} onClick={useMyLocation}>
          {t('loc.me')}
        </button>
      </div>

      {state !== 'failed' ? (
        <div className="relative h-72 overflow-hidden rounded-box border border-base-300 bg-base-200" dir="ltr">
          <div ref={box} className="absolute inset-0" />
          {/* Fixed pin: its tip marks the centre of the map. */}
          <svg viewBox="0 0 24 36" className="pointer-events-none absolute left-1/2 top-1/2 z-10 h-10 w-7 -translate-x-1/2 -translate-y-full" aria-hidden="true">
            <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24C24 5.4 18.6 0 12 0z" fill="#FF5722" />
            <circle cx="12" cy="12" r="4.5" fill="#fff" />
          </svg>
          {state === 'loading' && (
            <div className="absolute inset-0 z-20 grid place-items-center text-sm text-muted">{t('map.loading')}</div>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">{t('map.failed')}</p>
          <div className="grid grid-cols-2 gap-2" dir="ltr">
            <label className="input">
              <span className="label">{t('map.lat')}</span>
              <input type="number" step="0.00001" value={value.lat} onChange={(e) => onChange({ ...value, lat: Number(e.target.value) })} />
            </label>
            <label className="input">
              <span className="label">{t('map.lng')}</span>
              <input type="number" step="0.00001" value={value.lng} onChange={(e) => onChange({ ...value, lng: Number(e.target.value) })} />
            </label>
          </div>
        </div>
      )}
      <p className="text-xs text-muted" dir="ltr">
        {value.lat.toFixed(5)}, {value.lng.toFixed(5)}
      </p>
    </div>
  )
}
