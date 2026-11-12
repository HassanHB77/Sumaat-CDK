/**
 * Ghost buttons on the dark header: white text, and a faint light overlay on hover/active
 * (DaisyUI's ghost hover is a light grey box, which hides white text).
 */
export const ON_DARK =
  'text-secondary-content hover:bg-white/10 hover:border-transparent hover:shadow-none ' +
  // Focus (keyboard, or a clicked dropdown trigger) and pressed: DaisyUI makes these light grey with a dark ring.
  'focus-visible:bg-white/10 focus-visible:border-transparent focus-visible:shadow-none focus-visible:outline-white/70 ' +
  'active:bg-white/15 active:border-transparent'

/** Active nav link on the dark header (instead of DaisyUI's light `btn-active`). */
export const ON_DARK_ACTIVE = 'bg-white/15 border-transparent'
