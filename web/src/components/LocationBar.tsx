import { useState } from 'react'
import { useLanguage } from '../i18n/LanguageContext'
import { isInAlAhsa, PRESETS, RADII, type Radius, type Spot } from '../lib/geo'
import { formatKm } from '../lib/format'
import { useToast } from './Toast'

type Props = {
  spot: Spot
  onSpot: (spot: Spot) => void
  radius: Radius
  onRadius: (radius: Radius) => void
}

/** Where to search: Al-Hofuf / Al-Mubarraz / my location, plus the radius. (The map picker replaces this in M7.) */
export function LocationBar({ spot, onSpot, radius, onRadius }: Props) {
  const { t, lang } = useLanguage()
  const toast = useToast()
  const [locating, setLocating] = useState(false)

  function useMyLocation() {
    if (!('geolocation' in navigator)) {
      toast.show(t('loc.failed'), 'error')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        const { latitude: lat, longitude: lng } = pos.coords
        if (!isInAlAhsa(lat, lng)) {
          toast.show(t('loc.outside'), 'info', 6000)
          return
        }
        onSpot({ lat, lng, label: 'me' })
      },
      () => {
        setLocating(false)
        toast.show(t('loc.failed'), 'error')
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    )
  }

  const chip = (active: boolean) => `btn btn-sm rounded-full ${active ? 'btn-secondary' : 'btn-outline'}`

  return (
    <section className="flex flex-col gap-3 rounded-box bg-base-100 p-4 shadow-sm">
      <h2 className="text-sm font-medium text-muted">{t('loc.where')}</h2>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={chip(spot.label === 'hofuf')} onClick={() => onSpot(PRESETS.hofuf)}>
          {t('loc.hofuf')}
        </button>
        <button type="button" className={chip(spot.label === 'mubarraz')} onClick={() => onSpot(PRESETS.mubarraz)}>
          {t('loc.mubarraz')}
        </button>
        <button type="button" className={chip(spot.label === 'me')} onClick={useMyLocation} disabled={locating}>
          {locating ? (
            <>
              <span className="loading loading-spinner loading-xs" />
              {t('loc.locating')}
            </>
          ) : spot.label === 'me' ? (
            t('loc.meActive')
          ) : (
            t('loc.me')
          )}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">{t('radius.label')}</span>
        {RADII.map((r) => (
          <button key={r} type="button" className={chip(radius === r)} onClick={() => onRadius(r)}>
            <span dir="ltr">{formatKm(r, lang)}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
