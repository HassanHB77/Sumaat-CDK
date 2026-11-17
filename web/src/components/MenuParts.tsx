import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { DietTag, MenuItem, RestaurantDetail } from '../api/types'
import { categoryLabel, dietLabel } from '../i18n/labels'
import { useLanguage } from '../i18n/LanguageContext'
import { formatCalories, formatMoney, pickDescription, pickName } from '../lib/format'
import { CuisineBadges } from './CuisineParts'
import type { MenuSection } from '../lib/menu'
import { LocationPreview } from './LocationPreview'
import { HoursText, OpenStatusBadge } from './OpenStatusBadge'
import { Photo } from './Photo'
import { RestaurantIcon } from './RestaurantIcon'

export const sectionId = (category: string) => `cat-${category.replace(/\W+/g, '-')}`

/** "Usually ready in about 15 min" (median accept -> ready of the last 30 days), or nothing if unknown. */
export function ReadyTime({ minutes, className = '' }: { minutes?: number | null; className?: string }) {
  const { t } = useLanguage()
  if (!minutes) return null
  return (
    <p className={`flex items-center gap-1 text-sm ${className}`}>
      <svg viewBox="0 0 24 24" className="size-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" strokeLinecap="round" />
      </svg>
      <span>{t('menu.readyIn', { n: minutes })}</span>
    </p>
  )
}

export function MenuHeader({ restaurant: r }: { restaurant: RestaurantDetail }) {
  const { lang } = useLanguage()
  return (
    <section className="card bg-base-100 shadow-sm">
      {/* Phone: info, then the map under it. Wider screens: info beside the map, same card. */}
      <div className="flex flex-col sm:flex-row">
        <div className="flex min-w-0 flex-1">
          <div className="flex shrink-0 items-center ps-4">
            <Photo
              src={r.imageUrl}
              className="size-20 sm:size-24"
              dimmed={!r.openNow}
              fallback={<RestaurantIcon dimmed={!r.openNow} className="size-16" />}
            />
          </div>
          {/* justify-center + grow-0: DaisyUI lets <p> grow inside card-body, which opened gaps next to the tall map. */}
          <div className="card-body min-w-0 justify-center gap-1 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="card-title text-2xl">{pickName(r, lang)}</h1>
              <OpenStatusBadge restaurant={r} />
            </div>
            <p className="grow-0 text-sm text-muted">
              {r.district} · {r.city} · <HoursText hours={r.hours} />
            </p>
            <CuisineBadges cuisines={r.cuisines} />
            {pickDescription(r, lang) && <p className="grow-0 text-sm">{pickDescription(r, lang)}</p>}
            <ReadyTime minutes={r.typicalReadyMinutes} className="grow-0 text-muted" />
          </div>
        </div>
        <div className="shrink-0 px-4 pb-4 sm:w-80 sm:p-3 sm:ps-0 lg:w-96">
          <LocationPreview lat={r.lat} lng={r.lng} name={pickName(r, lang)} className="h-40 sm:h-full sm:min-h-40" />
        </div>
      </div>
    </section>
  )
}

/** Sticky tabs: tap to jump; the tab of the section on screen is highlighted (scroll-spy). */
export function CategoryTabs({ sections }: { sections: MenuSection[] }) {
  const { t } = useLanguage()
  const [active, setActive] = useState(sections[0]?.category)
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!sections.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) setActive(visible[0].target.getAttribute('data-category') ?? undefined)
      },
      { rootMargin: '-120px 0px -60% 0px' }, // a section counts as "current" near the top, under the sticky bars
    )
    for (const s of sections) {
      const el = document.getElementById(sectionId(s.category))
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [sections])

  useEffect(() => {
    // keep the active tab visible in the horizontal bar
    barRef.current?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [active])

  function jump(category: string) {
    setActive(category)
    document.getElementById(sectionId(category))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  if (sections.length < 2) return null
  return (
    <nav className="sticky top-[56px] z-20 -mx-4 bg-base-200/95 px-4 py-2 backdrop-blur">
      <div ref={barRef} className="flex gap-2 overflow-x-auto pb-1" role="tablist">
        {sections.map((s) => {
          const isActive = s.category === active
          return (
            <button
              key={s.category}
              type="button"
              role="tab"
              aria-selected={isActive}
              data-active={isActive}
              className={`btn btn-sm shrink-0 rounded-full ${isActive ? 'btn-primary' : 'btn-ghost bg-base-100'}`}
              onClick={() => jump(s.category)}
            >
              {categoryLabel(s.category, t)}
            </button>
          )
        })}
      </div>
    </nav>
  )
}

export function DietFilterChips({
  tags,
  selected,
  onChange,
}: {
  tags: DietTag[]
  selected: DietTag[]
  onChange: (next: DietTag[]) => void
}) {
  const { t } = useLanguage()
  if (!tags.length) return null
  const toggle = (tag: DietTag) => onChange(selected.includes(tag) ? selected.filter((x) => x !== tag) : [...selected, tag])
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted">{t('menu.diet')}</span>
      {tags.map((tag) => (
        <button
          key={tag}
          type="button"
          aria-pressed={selected.includes(tag)}
          className={`btn btn-xs rounded-full ${selected.includes(tag) ? 'btn-success' : 'btn-outline'}`}
          onClick={() => toggle(tag)}
        >
          {dietLabel(tag, t)}
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

export function DietBadges({ tags }: { tags: DietTag[] }) {
  const { t } = useLanguage()
  if (!tags?.length) return null
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span key={tag} className={`badge badge-sm ${tag === 'spicy' ? 'badge-error badge-outline' : 'badge-ghost'}`}>
          {dietLabel(tag, t)}
        </span>
      ))}
    </div>
  )
}

/** Name, price, calories, diet badges; `action` = the Add button / quantity stepper (or owner controls later). */
export function MenuItemCard({ item, action }: { item: MenuItem; action?: ReactNode }) {
  const { t, lang } = useLanguage()
  return (
    <article className="flex items-start gap-3 rounded-box bg-base-100 p-4 shadow-sm">
      <Photo src={item.imageUrl} className="size-16 sm:size-20" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-medium">{pickName(item, lang)}</h3>
          {item.popular && <span className="badge badge-sm badge-primary badge-soft">{t('menu.popular')}</span>}
        </div>
        <p className="text-sm text-muted" dir="ltr">
          {formatCalories(item.calories, lang)}
        </p>
        <DietBadges tags={item.dietTags} />
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2">
        <p className="font-bold" dir="ltr">
          {formatMoney(item.priceHalalas, lang)}
        </p>
        {action}
      </div>
    </article>
  )
}
