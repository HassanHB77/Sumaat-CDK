import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { getCategories, getRestaurant } from '../api/endpoints'
import { DIET_TAGS, type DietTag, type MenuItem } from '../api/types'
import { useCart } from '../cart/CartContext'
import { AddToCart } from '../components/AddToCart'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { CategoryTabs, DietFilterChips, MenuHeader, MenuItemCard, sectionId } from '../components/MenuParts'
import { useToast } from '../components/Toast'
import { PageContainer } from '../components/PageContainer'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { categoryLabel } from '../i18n/labels'
import { useLanguage } from '../i18n/LanguageContext'
import { pickName } from '../lib/format'
import { usePageTitle } from '../lib/usePageTitle'
import { availableDietTags, groupMenu } from '../lib/menu'

// Stable empty lists: `?? []` would create a new array every render and defeat useMemo.
const NO_ITEMS: MenuItem[] = []
const NO_CATEGORIES: string[] = []

export function MenuPage() {
  const { restaurantId = '' } = useParams()
  const { t, lang } = useLanguage()
  const toast = useToast()
  const { cart, add, clear, reconcileWith } = useCart()
  const [diet, setDiet] = useState<DietTag[]>([])
  const [search, setSearch] = useState('')
  const [pending, setPending] = useState<MenuItem | null>(null) // waiting for "start a new cart?"

  const restaurant = useQuery({
    queryKey: ['restaurant', restaurantId],
    queryFn: ({ signal }) => getRestaurant(restaurantId, signal),
    refetchInterval: 60_000,
  })
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => getCategories(signal),
    staleTime: 10 * 60_000, // changes rarely
  })
  usePageTitle(restaurant.data ? pickName(restaurant.data, lang) : t('page.menu'))

  const items = restaurant.data?.menu ?? NO_ITEMS
  const order = categories.data?.categories ?? NO_CATEGORIES
  const sections = useMemo(() => groupMenu(items, order, diet, { search }), [items, order, diet, search])
  const dietTags = useMemo(() => availableDietTags(items, DIET_TAGS), [items])

  // Keep the cart in line with this menu (hidden dishes, new prices).
  const loaded = restaurant.data
  useEffect(() => {
    if (loaded && reconcileWith(loaded.id, loaded.menu)) toast.show(t('cart.updated'), 'info')
  }, [loaded, reconcileWith, toast, t])

  if (restaurant.isPending || categories.isPending) {
    return (
      <PageContainer>
        <LoadingState rows={4} />
      </PageContainer>
    )
  }

  if (restaurant.isError) {
    const notFound = restaurant.error instanceof ApiError && restaurant.error.status === 404
    return (
      <PageContainer>
        {notFound ? (
          <EmptyState>
            <p className="mb-4">{t('menu.notFound')}</p>
            <Link to="/restaurants" className="btn btn-primary">
              {t('menu.back')}
            </Link>
          </EmptyState>
        ) : (
          <ErrorState onRetry={() => restaurant.refetch()} />
        )}
      </PageContainer>
    )
  }

  const r = restaurant.data
  const hasAnyItem = items.some((i) => i.isAvailable)
  const cartRestaurant = { id: r.id, name: r.name, nameAr: r.nameAr }
  const otherName = pickName({ name: cart.restaurantName, nameAr: cart.restaurantNameAr }, lang)

  return (
    <PageContainer>
      <div className="flex flex-col gap-4">
        <Link to="/restaurants" className="link link-hover w-fit text-sm text-muted">
          <span className="rtl:hidden">←</span>
          <span className="ltr:hidden">→</span> {t('menu.back')}
        </Link>

        <MenuHeader restaurant={r} />

        {!r.openNow && (
          <div role="status" className="alert alert-warning">
            {r.isPaused ? t('menu.pausedBanner') : t('menu.closedBanner')}
          </div>
        )}

        {!hasAnyItem ? (
          <EmptyState>{t('menu.noItems')}</EmptyState>
        ) : (
          <>
            <label className="input w-full">
              <svg viewBox="0 0 24 24" className="size-4 opacity-60" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" strokeLinecap="round" />
              </svg>
              <input
                type="search"
                className="grow"
                placeholder={t('menu.searchPlaceholder')}
                aria-label={t('menu.search')}
                value={search}
                maxLength={60}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <CategoryTabs sections={sections} />
            <DietFilterChips tags={dietTags} selected={diet} onChange={setDiet} />
            {sections.length === 0 ? (
              <EmptyState>{search.trim() ? t('menu.noMatch', { q: search.trim() }) : t('menu.empty')}</EmptyState>
            ) : (
              sections.map((s) => (
                <section
                  key={s.category}
                  id={sectionId(s.category)}
                  data-category={s.category}
                  className="flex scroll-mt-32 flex-col gap-2"
                >
                  <h2 className="mt-2 text-xl font-bold">{categoryLabel(s.category, t)}</h2>
                  {s.items.map((item) => (
                    <MenuItemCard
                      key={item.id}
                      item={item}
                      action={
                        <AddToCart restaurant={cartRestaurant} item={item} disabled={!r.openNow} onNeedReplace={setPending} />
                      }
                    />
                  ))}
                </section>
              ))
            )}
          </>
        )}
      </div>
      <ConfirmDialog
        open={pending !== null}
        title={t('cart.switchTitle')}
        confirmLabel={t('cart.switchConfirm')}
        cancelLabel={t('common.cancel')}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          clear()
          if (pending) add(cartRestaurant, pending)
          setPending(null)
        }}
      >
        {t('cart.switchBody', { name: otherName })}
      </ConfirmDialog>
    </PageContainer>
  )
}
