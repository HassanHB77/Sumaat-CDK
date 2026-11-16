import { describe, expect, it } from 'vitest'
import { circleRing, directionsUrl, distanceKm, movedEnough, staticMapUrl } from './geo'

const NAKHLA = { lat: 25.3797, lng: 49.5867 }
const MUBARRAZ = { lat: 25.4086, lng: 49.5823 }

describe('map helpers', () => {
  it('distance matches the API (~3.2 km Nakhla -> Mubarraz)', () => {
    expect(distanceKm(NAKHLA, MUBARRAZ)).toBeCloseTo(3.24, 1)
    expect(distanceKm(NAKHLA, NAKHLA)).toBe(0)
  })

  it('movedEnough ignores small nudges', () => {
    expect(movedEnough(NAKHLA, { lat: 25.3807, lng: 49.5867 })).toBe(false) // ~110 m
    expect(movedEnough(NAKHLA, MUBARRAZ)).toBe(true)
  })

  it('circle ring is closed and has the right radius', () => {
    const ring = circleRing(NAKHLA, 4.4, 32)
    expect(ring).toHaveLength(33)
    expect(ring[0]).toEqual(ring[32])
    for (const [lng, lat] of ring) expect(distanceKm(NAKHLA, { lat, lng })).toBeCloseTo(4.4, 1)
  })
})

describe('directionsUrl', () => {
  it('builds the Google Maps directions link with 6-decimal coordinates', () => {
    expect(directionsUrl(25.3797, 49.5867)).toBe(
      'https://www.google.com/maps/dir/?api=1&destination=25.379700,49.586700',
    )
    expect(directionsUrl(25.123456789, 49.987654321)).toBe(
      'https://www.google.com/maps/dir/?api=1&destination=25.123457,49.987654',
    )
  })
})

describe('staticMapUrl', () => {
  it('asks Amazon Location for a street map centred on the spot (lng,lat), in the page language', () => {
    const url = new URL(staticMapUrl(25.3797, 49.5867, 'ar', 'k1', 400, 180))
    expect(url.origin + url.pathname).toBe('https://maps.geo.us-east-1.amazonaws.com/v2/static/map@2x')
    expect(url.searchParams.get('center')).toBe('49.586700,25.379700')
    expect(url.searchParams.get('style')).toBe('Standard')
    expect(url.searchParams.get('lang')).toBe('ar')
    expect(url.searchParams.get('key')).toBe('k1')
    expect(url.searchParams.get('width')).toBe('400')
    expect(url.searchParams.get('height')).toBe('180')
    expect(new URL(staticMapUrl(25.3797, 49.5867, 'en', 'k1', 400, 180)).searchParams.get('lang')).toBe('en')
  })

  it('never asks for more than the API allows (700 wide at @2x)', () => {
    expect(new URL(staticMapUrl(25.3797, 49.5867, 'en', 'k1', 1200, 200)).searchParams.get('width')).toBe('700')
  })
})
