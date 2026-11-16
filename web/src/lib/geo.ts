/** Where the customer is looking for food. The map picker (M7) will reuse this. */

export type Spot = { lat: number; lng: number; label: 'hofuf' | 'mubarraz' | 'me' | 'map' }

export const PRESETS: Record<'hofuf' | 'mubarraz', Spot> = {
  hofuf: { lat: 25.38, lng: 49.588, label: 'hofuf' },
  mubarraz: { lat: 25.41, lng: 49.58, label: 'mubarraz' },
}

export const DEFAULT_SPOT = PRESETS.hofuf

/** Rough box around Al-Ahsa (Al-Hofuf, Al-Mubarraz and nearby towns). */
const BOUNDS = { minLat: 25.1, maxLat: 25.7, minLng: 49.3, maxLng: 49.9 }

export function isInAlAhsa(lat: number, lng: number): boolean {
  return lat >= BOUNDS.minLat && lat <= BOUNDS.maxLat && lng >= BOUNDS.minLng && lng <= BOUNDS.maxLng
}

export const RADII = [1, 3, 4] as const // km; 4 is the API maximum (the search grid reaches 4.4, we offer a round 4)
export type Radius = (typeof RADII)[number]
export const DEFAULT_RADIUS: Radius = 4

const SPOT_KEY = 'sumaat.spot'

/** Read the last spot from storage; anything missing, broken or outside Al-Ahsa -> the default. */
export function parseSpot(raw: string | null): Spot {
  if (!raw) return DEFAULT_SPOT
  try {
    const s = JSON.parse(raw)
    if (typeof s?.lat === 'number' && typeof s?.lng === 'number' && isInAlAhsa(s.lat, s.lng)) {
      const label = ['hofuf', 'mubarraz', 'me', 'map'].includes(s.label) ? s.label : 'map'
      return { lat: s.lat, lng: s.lng, label }
    }
  } catch {
    /* fall through */
  }
  return DEFAULT_SPOT
}

export function loadSpot(): Spot {
  try {
    return parseSpot(localStorage.getItem(SPOT_KEY))
  } catch {
    return DEFAULT_SPOT
  }
}

export function saveSpot(spot: Spot): void {
  try {
    localStorage.setItem(SPOT_KEY, JSON.stringify(spot))
  } catch {
    /* private mode: just don't remember */
  }
}

// --- map helpers (customer map) ---------------------------------------------------------

export type Point = { lat: number; lng: number }

/** Great-circle distance in km (same formula as the API). */
export function distanceKm(a: Point, b: Point): number {
  const R = 6371.0088
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLng = toRad(b.lng - a.lng)
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

/** Show "Search this area" only after a real move (not a tiny nudge). */
export function movedEnough(from: Point, to: Point, minKm = 0.3): boolean {
  return distanceKm(from, to) >= minKm
}

/** Closed ring of [lng, lat] points approximating a circle (for the faint radius circle on the map). */
export function circleRing(center: Point, km: number, steps = 64): [number, number][] {
  const latDeg = km / 111.32
  const lngDeg = km / (111.32 * Math.cos((center.lat * Math.PI) / 180))
  const ring: [number, number][] = []
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * 2 * Math.PI
    ring.push([center.lng + lngDeg * Math.cos(a), center.lat + latDeg * Math.sin(a)])
  }
  return ring
}

/** Google's universal directions link: opens the Google Maps app on phones that have it, the website otherwise. */
export function directionsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat.toFixed(6)},${lng.toFixed(6)}`
}

/**
 * Amazon Location static map (one picture, street style, labels in the page language), centred on the spot.
 * Sizes are CSS pixels; "@2x" doubles them for sharp phones (the API allows at most 700 wide at @2x).
 */
export function staticMapUrl(lat: number, lng: number, lang: 'en' | 'ar', key: string, width: number, height: number): string {
  const q = new URLSearchParams({
    center: `${lng.toFixed(6)},${lat.toFixed(6)}`,
    zoom: '16',
    width: String(Math.min(width, 700)),
    height: String(height),
    style: 'Standard',
    lang,
    key,
  })
  return `https://maps.geo.us-east-1.amazonaws.com/v2/static/map@2x?${q}`
}
