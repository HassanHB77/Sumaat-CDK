/** Where the customer is looking for food. The map picker (M7) will reuse this. */

export type Spot = { lat: number; lng: number; label: 'hofuf' | 'mubarraz' | 'me' }

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

export const RADII = [1, 3, 4.4] as const // km; 4.4 is the API maximum
export type Radius = (typeof RADII)[number]
export const DEFAULT_RADIUS: Radius = 4.4

const SPOT_KEY = 'sumaat.spot'

/** Read the last spot from storage; anything missing, broken or outside Al-Ahsa -> the default. */
export function parseSpot(raw: string | null): Spot {
  if (!raw) return DEFAULT_SPOT
  try {
    const s = JSON.parse(raw)
    if (typeof s?.lat === 'number' && typeof s?.lng === 'number' && isInAlAhsa(s.lat, s.lng)) {
      const label = ['hofuf', 'mubarraz', 'me'].includes(s.label) ? s.label : 'me'
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
