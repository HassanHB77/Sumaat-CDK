import type { Cuisine } from '../api/types'
import { cuisineLabel } from '../i18n/labels'
import { useLanguage } from '../i18n/LanguageContext'

/** Small read-only chips on restaurant cards and the menu header. */
export function CuisineBadges({ cuisines }: { cuisines?: Cuisine[] }) {
  const { t } = useLanguage()
  if (!cuisines?.length) return null
  return (
    <div className="flex flex-wrap gap-1">
      {cuisines.map((c) => (
        <span key={c} className="badge badge-ghost badge-sm">
          {cuisineLabel(c, t)}
        </span>
      ))}
    </div>
  )
}

/** Browse filter: tap cuisines to show only restaurants with any of them. */
export function CuisineFilterChips({
  cuisines,
  selected,
  onChange,
}: {
  cuisines: Cuisine[]
  selected: Cuisine[]
  onChange: (next: Cuisine[]) => void
}) {
  const { t } = useLanguage()
  if (cuisines.length < 2) return null
  const toggle = (c: Cuisine) => onChange(selected.includes(c) ? selected.filter((x) => x !== c) : [...selected, c])
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted">{t('list.cuisine')}</span>
      {cuisines.map((c) => (
        <button
          key={c}
          type="button"
          aria-pressed={selected.includes(c)}
          className={`btn btn-xs rounded-full ${selected.includes(c) ? 'btn-success' : 'btn-outline'}`}
          onClick={() => toggle(c)}
        >
          {cuisineLabel(c, t)}
        </button>
      ))}
      {selected.length > 0 && (
        <button type="button" className="btn btn-xs btn-ghost" onClick={() => onChange([])}>
          {t('menu.clear')}
        </button>
      )}
    </div>
  )
}
