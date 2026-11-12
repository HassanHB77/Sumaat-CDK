import { useState, type FormEvent } from 'react'
import type { RestaurantInput } from '../api/endpoints'
import { FormField } from '../components/FormParts'
import { MapPicker } from '../components/MapPicker'
import { useLanguage } from '../i18n/LanguageContext'
import { composeHours, splitHours, validateRestaurant, type Errors, type RestaurantValues } from './forms'

const CITIES = [
  { value: 'Al-Hofuf', key: 'loc.hofuf' },
  { value: 'Al-Mubarraz', key: 'loc.mubarraz' },
] as const

/** Shared by /owner/setup (create) and /owner/restaurant (edit). */
export function RestaurantForm({
  initial,
  submitLabel,
  busy,
  dirtyCheck,
  onSubmit,
}: {
  initial: RestaurantInput
  submitLabel: string
  busy: boolean
  /** Edit mode: disable Save when nothing changed. */
  dirtyCheck?: (values: RestaurantInput) => boolean
  onSubmit: (values: RestaurantInput) => void
}) {
  const { t } = useLanguage()
  const startHours = splitHours(initial.hours)
  const knownCity = CITIES.some((c) => c.value === initial.city)

  const [name, setName] = useState(initial.name)
  const [nameAr, setNameAr] = useState(initial.nameAr)
  const [description, setDescription] = useState(initial.description)
  const [cityChoice, setCityChoice] = useState(knownCity ? initial.city : initial.city ? 'other' : 'Al-Hofuf')
  const [otherCity, setOtherCity] = useState(knownCity ? '' : initial.city)
  const [district, setDistrict] = useState(initial.district)
  const [open, setOpen] = useState(startHours.allDay ? '12:00' : startHours.open)
  const [close, setClose] = useState(startHours.allDay ? '23:00' : startHours.close)
  const [allDay, setAllDay] = useState(startHours.allDay)
  const [point, setPoint] = useState({ lat: initial.lat, lng: initial.lng })
  const [errors, setErrors] = useState<Errors<keyof RestaurantValues>>({})

  const values: RestaurantInput = {
    name: name.trim(),
    nameAr: nameAr.trim(),
    description: description.trim(),
    city: cityChoice === 'other' ? otherCity.trim() : cityChoice,
    district: district.trim(),
    lat: point.lat,
    lng: point.lng,
    hours: composeHours(open, close, allDay) ?? '',
  }
  const dirty = dirtyCheck ? dirtyCheck(values) : true

  function submit(e: FormEvent) {
    e.preventDefault()
    const found = validateRestaurant(values)
    setErrors(found)
    if (Object.keys(found).length === 0) onSubmit(values)
  }

  const err = (k: keyof RestaurantValues) => (errors[k] ? t(errors[k]!) : null)

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-1">
      <div className="grid gap-x-4 sm:grid-cols-2">
        <FormField label={t('owner.form.name')} error={err('name')}>
          <input className="input w-full" dir="ltr" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
        </FormField>
        <FormField label={t('owner.form.nameAr')} error={err('nameAr')}>
          <input className="input w-full" dir="rtl" lang="ar" maxLength={80} value={nameAr} onChange={(e) => setNameAr(e.target.value)} />
        </FormField>
      </div>

      <FormField label={t('owner.form.description')} error={err('description')}>
        <textarea className="textarea w-full" rows={2} maxLength={500} value={description} onChange={(e) => setDescription(e.target.value)} />
      </FormField>

      <FormField label={t('owner.form.hours')} error={err('hours')}>
        <label className="label mb-1 cursor-pointer gap-2">
          <input type="checkbox" className="checkbox checkbox-sm" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />
          {t('owner.form.allDay')}
        </label>
        {!allDay && (
          <div className="flex flex-wrap items-end gap-3" dir="ltr">
            <label className="flex flex-col text-sm">
              {t('owner.form.open')}
              <input type="time" className="input" value={open} onChange={(e) => setOpen(e.target.value)} />
            </label>
            <label className="flex flex-col text-sm">
              {t('owner.form.close')}
              <input type="time" className="input" value={close} onChange={(e) => setClose(e.target.value)} />
            </label>
            {close < open && <span className="pb-2 text-sm text-muted">{t('hours.pastMidnight')}</span>}
          </div>
        )}
      </FormField>

      <div className="grid gap-x-4 sm:grid-cols-2">
        <FormField label={t('owner.form.city')} error={err('city')}>
          <select className="select w-full" value={cityChoice} onChange={(e) => setCityChoice(e.target.value)}>
            {CITIES.map((c) => (
              <option key={c.value} value={c.value}>
                {t(c.key)}
              </option>
            ))}
            <option value="other">{t('owner.form.cityOther')}</option>
          </select>
          {cityChoice === 'other' && (
            <input
              className="input mt-2 w-full"
              placeholder={t('owner.form.cityName')}
              maxLength={80}
              value={otherCity}
              onChange={(e) => setOtherCity(e.target.value)}
            />
          )}
        </FormField>
        <FormField label={t('owner.form.district')} error={err('district')}>
          <input className="input w-full" maxLength={80} value={district} onChange={(e) => setDistrict(e.target.value)} />
        </FormField>
      </div>

      <FormField label={t('owner.form.location')} error={err('lat')} hint={t('owner.form.locationNote')}>
        <p className="mb-1 text-sm text-muted">{t('owner.form.locationHint')}</p>
        <MapPicker value={point} onChange={setPoint} />
      </FormField>

      <button type="submit" className="btn btn-primary mt-4" disabled={busy || !dirty}>
        {busy && <span className="loading loading-spinner loading-sm" />}
        {dirty ? submitLabel : t('owner.form.noChanges')}
      </button>
    </form>
  )
}
