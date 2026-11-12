import { useEffect, useRef, useState, type RefObject } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { getConfig } from '../config/config'
import type { Point } from '../lib/geo'

export type MapLib = typeof import('maplibre-gl')
export type MapState = 'loading' | 'ready' | 'failed'

/** Amazon Location Service, Maps v2. The key is public by design and only works from our site + localhost. */
export function styleUrl(key: string): string {
  return `https://maps.geo.us-east-1.amazonaws.com/v2/styles/Standard/descriptor?key=${encodeURIComponent(key)}`
}

/**
 * Create one MapLibre map in `container`. MapLibre (~300 KB gzip) is downloaded only when a page uses this.
 * Returns the map + library once the style has loaded; `failed` if the key/network/style doesn't work,
 * so the page can fall back to buttons/fields.
 */
export function useMapLibre(container: RefObject<HTMLDivElement | null>, start: Point, zoom: number) {
  const map = useRef<MapLibreMap | null>(null)
  const lib = useRef<MapLib | null>(null)
  const [state, setState] = useState<MapState>('loading')
  const [reason, setReason] = useState<string | null>(null) // why it failed (shown in the fallback)

  useEffect(() => {
    let cancelled = false
    let key = ''
    try {
      key = getConfig().locationApiKey
    } catch {
      key = ''
    }
    if (!key) {
      setReason('no map key in config.json')
      setState('failed')
      return
    }
    ;(async () => {
      try {
        const [ml, worker] = await Promise.all([
          import('maplibre-gl'),
          // MapLibre 6 runs tile work in a separate worker file and looks for it NEXT TO its own file, which
          // isn't there once Vite bundles it. `?url` makes Vite ship the (self-contained) worker as an asset,
          // and setWorkerUrl tells MapLibre where it is.
          import('maplibre-gl/dist/maplibre-gl-worker.mjs?url'),
          import('maplibre-gl/dist/maplibre-gl.css'),
        ])
        if (ml.getWorkerUrl() !== worker.default) ml.setWorkerUrl(worker.default)
        if (cancelled || !container.current) return
        const m = new ml.Map({
          container: container.current,
          style: styleUrl(key),
          center: [start.lng, start.lat],
          zoom,
          attributionControl: { compact: true }, // attribution must stay visible
        })
        m.addControl(new ml.NavigationControl({ showCompass: false }), 'top-right')
        // Only a map whose STYLE never loads counts as failed (wrong key, blocked network).
        // Errors after that (one missing tile/font/icon) are normal and harmless: keep the map.
        // Note: map.isStyleLoaded() is also false while tiles are loading, so it can't be used for this.
        let loaded = false
        let lastError = ''
        const giveUp = setTimeout(() => {
          if (loaded || cancelled) return
          setReason(lastError || 'the map style did not load in 15 s')
          setState('failed')
        }, 15_000)
        // 'style.load' = the style is ready, which is all we need (markers, layers). Tiles keep filling in after.
        // ('load' waits until EVERY visible tile is drawn: too slow on weak phones to gate the whole map on it.)
        const ready = () => {
          if (loaded) return
          loaded = true
          clearTimeout(giveUp)
          if (!cancelled) setState('ready')
        }
        m.once('style.load', ready)
        m.once('load', ready)
        m.on('error', (e) => {
          const err = e.error as { message?: string; status?: number; url?: string } | undefined
          const status = err?.status
          lastError = `${status ?? ''} ${err?.message ?? 'map error'} ${err?.url ? `(${err.url.split('?')[0]})` : ''}`.trim()
          console.warn('[map]', lastError)
          // The key was refused (wrong key, or the page address is not allowed): no point waiting.
          if (!loaded && !cancelled && (status === 401 || status === 403)) {
            clearTimeout(giveUp)
            setReason(`${lastError} — the map key only works on the website and http://localhost:5173`)
            setState('failed')
          }
        })
        map.current = m
        lib.current = ml
      } catch (err) {
        if (!cancelled) {
          setReason(String((err as Error)?.message ?? err))
          setState('failed')
        }
      }
    })()
    return () => {
      cancelled = true
      map.current?.remove()
      map.current = null
    }
    // the starting point only matters once; callers move the map themselves later
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { map, lib, state, reason }
}

/** The orange pin drawn on top of the map; its tip marks the map centre. */
export const CENTER_PIN_PATH = 'M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24C24 5.4 18.6 0 12 0z'
