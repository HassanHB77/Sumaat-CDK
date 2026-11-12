import { describe, expect, it } from 'vitest'
import { circleRing, distanceKm, movedEnough } from './geo'

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
