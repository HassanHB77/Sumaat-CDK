import { useCallback, useState } from 'react'

/**
 * Which fields show their warning: a field is "touched" once the user leaves it (blur) or presses submit.
 * Warnings are then computed from the current values on every render, so they update as the user types
 * and disappear as soon as the field is fixed.
 */
export function useTouched<K extends string>() {
  const [touched, setTouched] = useState<ReadonlySet<K>>(() => new Set())
  const touch = useCallback((k: K) => setTouched((t) => (t.has(k) ? t : new Set(t).add(k))), [])
  const touchAll = useCallback((keys: K[]) => setTouched(new Set(keys)), [])
  const reset = useCallback(() => setTouched(new Set()), [])
  return { isTouched: (k: K) => touched.has(k), touch, touchAll, reset }
}
