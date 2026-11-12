/** The API has no photos: a simple plate icon in brand colours stands in. */
export function RestaurantIcon({ dimmed = false, className = 'size-14' }: { dimmed?: boolean; className?: string }) {
  return (
    <div
      className={`grid shrink-0 place-items-center rounded-box ${dimmed ? 'bg-base-300' : 'bg-secondary'} ${className}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 48 48" className="size-3/5">
        <path d="M8 26h32a16 11 0 0 1-32 0z" fill={dimmed ? '#adb5bd' : '#FF5722'} />
        <rect x="6" y="23" width="36" height="4" rx="2" fill={dimmed ? '#adb5bd' : '#FF5722'} />
        <path d="M18 18c0-3 2-3 2-6M24 18c0-3 2-3 2-6M30 18c0-3 2-3 2-6" stroke={dimmed ? '#adb5bd' : '#2ECC71'} strokeWidth="2" fill="none" strokeLinecap="round" />
      </svg>
    </div>
  )
}
