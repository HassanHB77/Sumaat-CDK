import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { DietTag, MenuItem, RestaurantDetail } from '../api/types'
import { categoryLabel, dietLabel } from '../i18n/labels'
import { useLanguage } from '../i18n/LanguageContext'
import { formatCalories, formatMoney, pickName } from '../lib/format'
import type { MenuSection } from '../lib/menu'
import { HoursText, OpenStatusBadge } from './OpenStatusBadge'
import { RestaurantIcon } from './RestaurantIcon'

export const sectionId = (category: string) => `cat-${category.replace(/\W+/g, '-')}`

export function MenuHeader({ restaurant: r }: { restaurant: RestaurantDetail }) {
  const { lang } = useLanguage()
  return (
    <section className="card card-side bg-base-100 shadow-sm">
      <figure className="ps-4">
        <RestaurantIcon dimmed={!r.openNow} className="size-16" />
      </figure>
      <div className="card-body gap-1 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="card-title text-2xl">{pickName(r, lang)}</h1>
          <OpenStatusBadge restaurant={r} />
        </div>
        <p className="text-sm text-muted">
          {r.district} · {r.city} · <HoursText hours={r.hours} />
        </p>
        {r.description && <p className="text-sm">{r.description}</p>}
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
  const { lang } = useLanguage()
  return (
    <article className="flex items-start justify-between gap-3 rounded-box bg-base-100 p-4 shadow-sm">
      <div className="flex min-w-0 flex-col gap-1">
        <h3 className="font-medium">{pickName(item, lang)}</h3>
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
