import { useEffect, useRef, useState } from 'react'
import type { Marker } from 'maplibre-gl'
import type { NearbyRestaurant } from '../api/types'
import { useLanguage } from '../i18n/LanguageContext'
import { pickName } from '../lib/format'
import { circleRing, movedEnough, type Point } from '../lib/geo'
import { CENTER_PIN_PATH, useMapLibre, type MapState } from './useMapLibre'

const RADIUS_SOURCE = 'search-radius'

function radiusGeoJson(center: Point, km: number) {
  return {
    type: 'Feature' as const,
    properties: {},
    geometry: { type: 'Polygon' as const, coordinates: [circleRing(center, km)] },
  }
}

/**
 * Customer map on /restaurants: markers for the restaurants found (coral = open, grey = closed), a faint circle for
 * the search radius, a fixed centre pin, and "Search this area" after the map is moved.
 * Reports `failed` so the page can just show the list (the chips keep working).
 */
export function RestaurantsMap({
  center,
  radiusKm,
  restaurants,
  onSearchHere,
  onOpen,
  onState,
}: {
  center: Point
  radiusKm: number
  restaurants: NearbyRestaurant[]
  onSearchHere: (p: Point) => void
  onOpen: (restaurantId: string) => void
  onState?: (s: MapState) => void
}) {
  const { t, lang } = useLanguage()
  const box = useRef<HTMLDivElement>(null)
  const { map, lib, state, reason } = useMapLibre(box, center, 13)
  const markers = useRef<Marker[]>([])
  const [moved, setMoved] = useState<Point | null>(null) // map centre after a real move
  const latest = useRef({ onOpen, center })

  useEffect(() => {
    latest.current = { onOpen, center }
  })
  useEffect(() => onState?.(state), [state, onState])

  // Radius circle: add once, then keep it in sync.
  useEffect(() => {
    const m = map.current
    if (state !== 'ready' || !m) return
    const data = radiusGeoJson(center, radiusKm)
    const source = m.getSource(RADIUS_SOURCE) as { setData?: (d: unknown) => void } | undefined
    if (source?.setData) {
      source.setData(data)
      return
    }
    m.addSource(RADIUS_SOURCE, { type: 'geojson', data })
    m.addLayer({ id: 'radius-fill', type: 'fill', source: RADIUS_SOURCE, paint: { 'fill-color': '#FF5722', 'fill-opacity': 0.06 } })
    m.addLayer({
      id: 'radius-line',
      type: 'line',
      source: RADIUS_SOURCE,
      paint: { 'line-color': '#FF5722', 'line-opacity': 0.5, 'line-width': 1.5, 'line-dasharray': [2, 2] },
    })
  }, [state, map, center, radiusKm])

  // Markers for the restaurants found.
  useEffect(() => {
    const m = map.current
    const ml = lib.current
    if (state !== 'ready' || !m || !ml) return
    markers.current.forEach((mk) => mk.remove())
    markers.current = restaurants.map((r) => {
      const dot = document.createElement('button')
      dot.type = 'button'
      dot.setAttribute('aria-label', pickName(r, lang))
      dot.style.cssText = `width:22px;height:22px;border-radius:9999px;border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);cursor:pointer;background:${
        r.openNow ? '#FF5722' : '#9ca3af'
      }`

      const popup = document.createElement('div')
      popup.style.cssText = 'font-family:inherit;min-width:140px'
      const title = document.createElement('p')
      title.textContent = pickName(r, lang)
      title.style.cssText = 'font-weight:700;margin:0 0 6px'
      const open = document.createElement('button')
      open.type = 'button'
      open.textContent = t('map.openMenu')
      open.className = 'btn btn-primary btn-xs'
      open.onclick = () => latest.current.onOpen(r.id)
      popup.append(title, open)

      return new ml.Marker({ element: dot })
        .setLngLat([r.lng, r.lat])
        .setPopup(new ml.Popup({ offset: 14, closeButton: false }).setDOMContent(popup))
        .addTo(m)
    })
  }, [state, map, lib, restaurants, lang, t])

  // After the user moves the map: offer "Search this area".
  useEffect(() => {
    const m = map.current
    if (state !== 'ready' || !m) return
    const onMoveEnd = () => {
      const c = m.getCenter()
      const here = { lat: c.lat, lng: c.lng }
      setMoved(movedEnough(latest.current.center, here) ? here : null)
    }
    m.on('moveend', onMoveEnd)
    return () => {
      m.off('moveend', onMoveEnd)
    }
  }, [state, map])

  // A new search point from outside (chips, my location, search here) moves the map.
  useEffect(() => {
    const m = map.current
    if (!m) return
    const c = m.getCenter()
    if (movedEnough({ lat: c.lat, lng: c.lng }, center, 0.01)) m.jumpTo({ center: [center.lng, center.lat] })
    setMoved(null)
  }, [center, map, state])

  if (state === 'failed') {
    // The list and the area buttons keep working; say why the map is missing.
    return (
      <p className="rounded-box bg-base-100 p-3 text-sm text-muted shadow-sm">
        {t('map.unavailable')}
        {reason && (
          <span className="mt-1 block font-mono text-xs" dir="ltr">
            {reason}
          </span>
        )}
      </p>
    )
  }

  return (
    <div className="relative h-56 overflow-hidden rounded-box border border-base-300 bg-base-200 sm:h-72" dir="ltr">
      {/* Not "absolute inset-0": MapLibre sets position:relative on this element and would collapse it to 0 px. */}
      <div ref={box} className="h-full w-full" />
      <svg viewBox="0 0 24 36" className="pointer-events-none absolute left-1/2 top-1/2 z-10 h-9 w-6 -translate-x-1/2 -translate-y-full" aria-hidden="true">
        <path d={CENTER_PIN_PATH} fill="#1E1E24" />
        <circle cx="12" cy="12" r="4.5" fill="#fff" />
      </svg>
      {state === 'loading' && <div className="absolute inset-0 z-20 grid place-items-center text-sm text-muted">{t('map.loading')}</div>}
      {moved && (
        <button
          type="button"
          className="btn btn-primary btn-sm absolute left-1/2 top-3 z-20 -translate-x-1/2 shadow-lg"
          onClick={() => {
            onSearchHere(moved)
            setMoved(null)
          }}
        >
          {t('map.searchHere')}
        </button>
      )}
    </div>
  )
}
