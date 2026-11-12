import { useEffect, useRef, useState, type FormEvent } from 'react'
import type { MenuItemInput } from '../api/endpoints'
import { DIET_TAGS, type MenuItem } from '../api/types'
import { FormField } from '../components/FormParts'
import { categoryLabel, dietLabel } from '../i18n/labels'
import { useLanguage } from '../i18n/LanguageContext'
import { halalasToSar, parseSar, validateItem, type Errors, type ItemValues } from './forms'

/** Add or edit a dish. Bottom sheet on phones, centred dialog on larger screens. */
export function ItemFormDialog({
  open,
  item,
  defaultCategory,
  categories,
  busy,
  onCancel,
  onSave,
}: {
  open: boolean
  item: MenuItem | null // null = new dish
  defaultCategory: string
  categories: string[]
  busy: boolean
  onCancel: () => void
  onSave: (values: MenuItemInput) => void
}) {
  const { t } = useLanguage()
  const ref = useRef<HTMLDialogElement>(null)
  const blank: ItemValues = { name: '', nameAr: '', category: defaultCategory, price: '', calories: '', dietTags: [], isAvailable: true }
  const [v, setV] = useState<ItemValues>(blank)
  const [errors, setErrors] = useState<Errors<keyof ItemValues>>({})

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open) {
      setV(
        item
          ? {
              name: item.name,
              nameAr: item.nameAr,
              category: item.category,
              price: halalasToSar(item.priceHalalas),
              calories: String(item.calories ?? ''),
              dietTags: [...(item.dietTags ?? [])],
              isAvailable: item.isAvailable,
            }
          : { ...blank, category: defaultCategory || categories[0] || '' },
      )
      setErrors({})
      if (!d.open) d.showModal()
    } else if (d.open) d.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, item, defaultCategory])

  const set = <K extends keyof ItemValues>(k: K, value: ItemValues[K]) => setV((old) => ({ ...old, [k]: value }))
  const toggleTag = (tag: string) =>
    set('dietTags', v.dietTags.includes(tag) ? v.dietTags.filter((x) => x !== tag) : [...v.dietTags, tag])

  function submit(e: FormEvent) {
    e.preventDefault()
    const found = validateItem(v)
    setErrors(found)
    if (Object.keys(found).length) return
    onSave({
      name: v.name.trim(),
      nameAr: v.nameAr.trim(),
      category: v.category,
      priceHalalas: parseSar(v.price)!,
      calories: v.calories.trim() ? Number(v.calories.trim()) : 0,
      dietTags: DIET_TAGS.filter((tag) => v.dietTags.includes(tag)), // stable order
      isAvailable: v.isAvailable,
    })
  }

  const err = (k: keyof ItemValues) => (errors[k] ? t(errors[k]!) : null)

  return (
    <dialog ref={ref} className="modal modal-bottom sm:modal-middle" onClose={onCancel}>
      <form onSubmit={submit} noValidate className="modal-box flex flex-col gap-1">
        <h3 className="text-lg font-bold">{item ? t('owner.menu.editTitle') : t('owner.menu.newTitle')}</h3>
        <div className="grid gap-x-3 sm:grid-cols-2">
          <FormField label={t('owner.item.name')} error={err('name')}>
            <input className="input w-full" dir="ltr" maxLength={80} value={v.name} onChange={(e) => set('name', e.target.value)} />
          </FormField>
          <FormField label={t('owner.item.nameAr')} error={err('nameAr')}>
            <input className="input w-full" dir="rtl" lang="ar" maxLength={80} value={v.nameAr} onChange={(e) => set('nameAr', e.target.value)} />
          </FormField>
        </div>
        <div className="grid gap-x-3 sm:grid-cols-3">
          <FormField label={t('owner.item.category')} error={err('category')}>
            <select className="select w-full" value={v.category} onChange={(e) => set('category', e.target.value)}>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {categoryLabel(c, t)}
                </option>
              ))}
            </select>
          </FormField>
          <FormField label={t('owner.item.price')} error={err('price')}>
            <input
              className="input w-full"
              dir="ltr"
              inputMode="decimal"
              placeholder="48.50"
              value={v.price}
              onChange={(e) => set('price', e.target.value.replace(',', '.'))}
            />
          </FormField>
          <FormField label={t('owner.item.calories')} error={err('calories')}>
            <input className="input w-full" dir="ltr" inputMode="numeric" value={v.calories} onChange={(e) => set('calories', e.target.value)} />
          </FormField>
        </div>
        <FormField label={t('owner.item.diet')}>
          <div className="flex flex-wrap gap-2">
            {DIET_TAGS.map((tag) => (
              <label key={tag} className="label cursor-pointer gap-1 rounded-full border border-base-300 px-3 py-1">
                <input type="checkbox" className="checkbox checkbox-xs" checked={v.dietTags.includes(tag)} onChange={() => toggleTag(tag)} />
                {dietLabel(tag, t)}
              </label>
            ))}
          </div>
        </FormField>
        <label className="label mt-2 cursor-pointer gap-2">
          <input type="checkbox" className="toggle toggle-success" checked={v.isAvailable} onChange={(e) => set('isAvailable', e.target.checked)} />
          {t('owner.menu.available')} · <span className="text-muted">{t('owner.item.availableHint')}</span>
        </label>
        <div className="modal-action">
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy && <span className="loading loading-spinner loading-sm" />}
            {t('owner.form.save')}
          </button>
        </div>
      </form>
      <form method="dialog" className="modal-backdrop">
        <button type="submit" aria-label={t('common.cancel')} />
      </form>
    </dialog>
  )
}
