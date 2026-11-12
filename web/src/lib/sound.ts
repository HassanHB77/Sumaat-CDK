/**
 * New-order beep with WebAudio (no sound file). Browsers only allow audio after a user tap, so the counter
 * shows a "Start shift" button that calls unlockSound() once.
 */
let ctx: AudioContext | null = null

export function unlockSound(): void {
  try {
    ctx ??= new AudioContext()
    void ctx.resume()
  } catch {
    ctx = null // very old browser: no sound, the visual alert still works
  }
}

/** Two short rising tones (~0.4 s). */
export function beep(): void {
  if (!ctx || ctx.state !== 'running') return
  const start = ctx.currentTime
  for (const [i, freq] of [880, 1320].entries()) {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = freq
    const t = start + i * 0.18
    gain.gain.setValueAtTime(0.0001, t)
    gain.gain.exponentialRampToValueAtTime(0.35, t + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.16)
    osc.connect(gain).connect(ctx.destination)
    osc.start(t)
    osc.stop(t + 0.17)
  }
}

const SOUND_KEY = 'sumaat.sound'

export function loadSoundOn(): boolean {
  try {
    return localStorage.getItem(SOUND_KEY) !== 'off'
  } catch {
    return true
  }
}

export function saveSoundOn(on: boolean): void {
  try {
    localStorage.setItem(SOUND_KEY, on ? 'on' : 'off')
  } catch {
    /* ignore */
  }
}
