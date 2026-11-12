import { useEffect, useRef } from 'react'
import { useLanguage } from '../i18n/LanguageContext'
import { isInAlAhsa, PRESETS } from '../lib/geo'
import { useToast } from './Toast'
import { CENTER_PIN_PATH, useMapLibre } from './useMapLibre'

export type LatLng = { lat: number; lng: number }

const round5 = (n: number) => Math.round(n * 1e5) / 1e5

/**
 * Pick a spot (owner restaurant form): drag the map, the pin stays in the middle. If the map can't load,
 * the shortcuts + number fields still work.
 */
export function MapPicker({ value, onChange }: { value: LatLng; onChange: (v: LatLng) => void }) {
  const { t } = useLanguage()
  const toast = useToast()
  const box = useRef<HTMLDivElement>(null)
  const { map, state, reason } = useMapLibre(box, value, 15)
  const onChangeRef = useRef(onChange)

  useEffect(() => {
    onChangeRef.current = onChange
  })

  // Report the centre whenever the map stops moving.
  useEffect(() => {
    const m = map.current
    if (state !== 'ready' || !m) return
    const onMoveEnd = () => {
      const c = m.getCenter()
      onChangeRef.current({ lat: round5(c.lat), lng: round5(c.lng) })
    }
    m.on('moveend', onMoveEnd)
    return () => {
      m.off('moveend', onMoveEnd)
    }
  }, [state, map])

  // Shortcut buttons / number fields move the map.
  useEffect(() => {
    const m = map.current
    if (!m) return
    const c = m.getCenter()
    if (Math.abs(c.lat - value.lat) > 1e-5 || Math.abs(c.lng - value.lng) > 1e-5) m.jumpTo({ center: [value.lng, value.lat] })
  }, [value.lat, value.lng, map, state])

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
          {/* Not "absolute inset-0": MapLibre sets position:relative on this element and would collapse it to 0 px. */}
          <div ref={box} className="h-full w-full" />
          {/* Fixed pin: its tip marks the centre of the map. */}
          <svg viewBox="0 0 24 36" className="pointer-events-none absolute left-1/2 top-1/2 z-10 h-10 w-7 -translate-x-1/2 -translate-y-full" aria-hidden="true">
            <path d={CENTER_PIN_PATH} fill="#FF5722" />
            <circle cx="12" cy="12" r="4.5" fill="#fff" />
          </svg>
          {state === 'loading' && (
            <div className="absolute inset-0 z-20 grid place-items-center text-sm text-muted">{t('map.loading')}</div>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted">{t('map.failed')}</p>
          {reason && (
            <p className="font-mono text-xs text-muted" dir="ltr">
              {reason}
            </p>
          )}
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
