import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Navigate } from 'react-router'
import { ApiError } from '../api/client'
import { addMenuItem, getCategories, getRestaurant, updateMenuItem, type MenuItemInput } from '../api/endpoints'
import type { MenuItem, RestaurantDetail } from '../api/types'
import { restaurantKey, useStaff } from '../counter/StaffLayout'
import { CategoryTabs, MenuItemCard, sectionId } from '../components/MenuParts'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useToast } from '../components/Toast'
import { categoryLabel } from '../i18n/labels'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'
import { pickName } from '../lib/format'
import { groupMenu } from '../lib/menu'
import { changedFields } from './forms'
import { ItemFormDialog } from './ItemFormDialog'

const NO_ITEMS: MenuItem[] = []
const NO_CATEGORIES: string[] = []

/** /owner/menu: the customer menu layout + hidden dishes, Available switches, add/edit. No delete: hide instead. */
export function OwnerMenuPage() {
  const { restaurantId } = useStaff()
  const { t, lang } = useLanguage()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [asCustomer, setAsCustomer] = useState(false)
  usePageTitle(t('page.ownerMenu'))
  const [editing, setEditing] = useState<{ item: MenuItem | null; category: string } | null>(null)

  const key = restaurantKey(restaurantId ?? '')
  const restaurant = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => getRestaurant(restaurantId!, signal),
    enabled: Boolean(restaurantId),
  })
  const categories = useQuery({ queryKey: ['categories'], queryFn: ({ signal }) => getCategories(signal), staleTime: 10 * 60_000 })

  const items = restaurant.data?.menu ?? NO_ITEMS
  const order = categories.data?.categories ?? NO_CATEGORIES
  const sections = useMemo(() => groupMenu(items, order, [], { includeHidden: !asCustomer }), [items, order, asCustomer])

  const replaceItem = (saved: MenuItem) =>
    queryClient.setQueryData<RestaurantDetail>(key, (old) =>
      old ? { ...old, menu: old.menu.some((m) => m.id === saved.id) ? old.menu.map((m) => (m.id === saved.id ? saved : m)) : [...old.menu, saved] } : old,
    )

  // Available switch: show the change at once, undo it if the API says no.
  const toggle = useMutation({
    mutationFn: (item: MenuItem) => updateMenuItem(restaurantId!, item.id, { isAvailable: !item.isAvailable }),
    onMutate: (item) => replaceItem({ ...item, isAvailable: !item.isAvailable }),
    onSuccess: (saved) =>
      toast.show(t(saved.isAvailable ? 'owner.item.shownToast' : 'owner.item.hiddenToast', { name: pickName(saved, lang) }), 'success'),
    onError: (_e, item) => {
      replaceItem(item)
      toast.show(t('auth.err.generic'), 'error')
    },
  })

  const save = useMutation({
    mutationFn: ({ item, values }: { item: MenuItem | null; values: MenuItemInput }) => {
      if (!item) return addMenuItem(restaurantId!, values)
      const original: MenuItemInput = {
        name: item.name,
        nameAr: item.nameAr,
        category: item.category,
        priceHalalas: item.priceHalalas,
        calories: item.calories ?? 0,
        dietTags: item.dietTags ?? [],
        isAvailable: item.isAvailable,
      }
      const changes = changedFields(original, values)
      return Object.keys(changes).length ? updateMenuItem(restaurantId!, item.id, changes) : Promise.resolve(item)
    },
    onSuccess: (saved) => {
      replaceItem(saved)
      setEditing(null)
      toast.show(t('owner.item.saved'), 'success')
    },
    onError: (err) => toast.show(err instanceof ApiError ? err.message : t('auth.err.generic'), 'error', 6000),
  })

  if (!restaurantId) return <Navigate to="/owner/setup" replace />
  if (restaurant.isPending || categories.isPending) return <LoadingState rows={4} />
  if (restaurant.isError) return <ErrorState onRetry={() => restaurant.refetch()} />

  const addButton = (category: string, small = false) =>
    !asCustomer && (
      <button type="button" className={`btn btn-primary ${small ? 'btn-sm btn-outline' : ''}`} onClick={() => setEditing({ item: null, category })}>
        + {t('owner.menu.add')}
      </button>
    )

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t('page.ownerMenu')}</h1>
        <div className="flex items-center gap-3">
          <label className="label cursor-pointer gap-2">
            <input type="checkbox" className="toggle toggle-sm" checked={asCustomer} onChange={(e) => setAsCustomer(e.target.checked)} />
            {t('owner.menu.seeAsCustomer')}
          </label>
          {addButton(order[0] ?? '')}
        </div>
      </div>

      {sections.length === 0 ? (
        <EmptyState>{t('owner.menu.empty')}</EmptyState>
      ) : (
        <>
          <CategoryTabs sections={sections} />
          {sections.map((s) => (
            <section key={s.category} id={sectionId(s.category)} data-category={s.category} className="flex scroll-mt-40 flex-col gap-2">
              <div className="mt-2 flex items-center justify-between">
                <h2 className="text-xl font-bold">{categoryLabel(s.category, t)}</h2>
                {addButton(s.category, true)}
              </div>
              {s.items.map((item) => (
                <div key={item.id} className={item.isAvailable ? '' : 'opacity-60'}>
                  <MenuItemCard
                    item={item}
                    action={
                      !asCustomer && (
                        <div className="flex items-center gap-2">
                          {!item.isAvailable && <span className="badge badge-ghost">{t('owner.menu.hidden')}</span>}
                          <input
                            type="checkbox"
                            className="toggle toggle-success toggle-sm"
                            checked={item.isAvailable}
                            onChange={() => toggle.mutate(item)}
                            aria-label={t('owner.menu.available')}
                            title={t('owner.menu.available')}
                          />
                          <button type="button" className="btn btn-ghost btn-xs" onClick={() => setEditing({ item, category: item.category })}>
                            {t('owner.menu.edit')}
                          </button>
                        </div>
                      )
                    }
                  />
                </div>
              ))}
            </section>
          ))}
        </>
      )}

      <ItemFormDialog
        open={editing !== null}
        item={editing?.item ?? null}
        defaultCategory={editing?.category ?? ''}
        categories={order}
        busy={save.isPending}
        onCancel={() => setEditing(null)}
        onSave={(values) => editing && save.mutate({ item: editing.item, values })}
      />
    </div>
  )
}
