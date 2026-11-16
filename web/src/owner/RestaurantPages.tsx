import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { createRestaurant, getRestaurant, updateRestaurant, type RestaurantInput } from '../api/endpoints'
import type { RestaurantDetail } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { restaurantKey, useStaff } from '../counter/StaffLayout'
import { LocationPreview } from '../components/LocationPreview'
import { PhotoField } from './PhotoField'
import { ErrorState, LoadingState } from '../components/States'
import { useToast } from '../components/Toast'
import { useLanguage } from '../i18n/LanguageContext'
import { pickName } from '../lib/format'
import { DEFAULT_SPOT } from '../lib/geo'
import { usePageTitle } from '../lib/usePageTitle'
import { changedFields } from './forms'
import { RestaurantForm } from './RestaurantForm'

const EMPTY: RestaurantInput = {
  name: '',
  nameAr: '',
  description: '',
  descriptionAr: '',
  cuisines: [],
  city: 'Al-Hofuf',
  district: '',
  lat: DEFAULT_SPOT.lat,
  lng: DEFAULT_SPOT.lng,
  hours: '12:00-23:00',
}

function toInput(r: RestaurantDetail): RestaurantInput {
  return {
    name: r.name,
    nameAr: r.nameAr,
    description: r.description ?? '',
    descriptionAr: r.descriptionAr ?? '',
    cuisines: r.cuisines ?? [],
    city: r.city,
    district: r.district,
    lat: r.lat,
    lng: r.lng,
    hours: r.hours,
  }
}

/** /owner/setup: a new owner creates their restaurant (only if they don't have one yet). */
export function OwnerSetupPage() {
  const { restaurantId } = useStaff()
  const { refresh } = useAuth()
  const { t } = useLanguage()
  const toast = useToast()
  const navigate = useNavigate()
  usePageTitle(t('page.ownerSetup'))

  const create = useMutation({
    mutationFn: (values: RestaurantInput) => createRestaurant(values),
    onSuccess: async () => {
      // The new restaurant id is added to the owner's login; get a fresh token so it shows up.
      await refresh(true)
      toast.show(t('owner.setup.done'), 'success', 6000)
      navigate('/owner/menu', { replace: true })
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) return navigate('/owner', { replace: true })
      toast.show(err instanceof ApiError ? err.message : t('auth.err.generic'), 'error', 6000)
    },
  })

  if (restaurantId) return <Navigate to="/owner/orders" replace />

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold">{t('page.ownerSetup')}</h1>
      <p className="mb-4 text-muted">{t('owner.setup.intro')}</p>
      <div className="card bg-base-100 shadow-sm">
        <div className="card-body">
          <RestaurantForm initial={EMPTY} submitLabel={t('owner.setup.create')} busy={create.isPending} onSubmit={(v) => create.mutate(v)} />
        </div>
      </div>
    </div>
  )
}

/** /owner/restaurant: edit details; only changed fields are sent. */
export function RestaurantSettingsPage() {
  const { restaurantId } = useStaff()
  const { t, lang } = useLanguage()
  const toast = useToast()
  const queryClient = useQueryClient()
  usePageTitle(t('page.ownerRestaurant'))

  const restaurant = useQuery({
    queryKey: restaurantKey(restaurantId ?? ''),
    queryFn: ({ signal }) => getRestaurant(restaurantId!, signal),
    enabled: Boolean(restaurantId),
  })

  const save = useMutation({
    mutationFn: (changes: Partial<RestaurantInput>) => updateRestaurant(restaurantId!, changes),
    onSuccess: (updated) => {
      queryClient.setQueryData(restaurantKey(restaurantId!), (old: RestaurantDetail | undefined) => (old ? { ...old, ...updated } : old))
      queryClient.invalidateQueries({ queryKey: ['restaurant', restaurantId] })
      toast.show(t('owner.form.saved'), 'success')
    },
    onError: (err) => toast.show(err instanceof ApiError ? err.message : t('auth.err.generic'), 'error', 6000),
  })

  if (!restaurantId) return <Navigate to="/owner/setup" replace />
  if (restaurant.isPending) return <LoadingState rows={3} />
  if (restaurant.isError) return <ErrorState onRetry={() => restaurant.refetch()} />

  const original = toInput(restaurant.data)
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-4 text-2xl font-bold">{t('page.ownerRestaurant')}</h1>
      <div className="card mb-4 bg-base-100 shadow-sm">
        <div className="card-body gap-3">
          <h2 className="card-title text-lg">{t('photo.title')}</h2>
          <PhotoField<RestaurantDetail>
            restaurantId={restaurantId}
            imageUrl={restaurant.data.imageUrl}
            hint={t('photo.restaurantHint')}
            onChanged={(updated) => {
              // Only the photo: keeping updatedAt as is stops the form below from resetting unsaved edits.
              queryClient.setQueryData(restaurantKey(restaurantId), (old: RestaurantDetail | undefined) =>
                old ? { ...old, imageUrl: updated.imageUrl } : old,
              ) // same key as the customer menu page, so it shows the new photo too
            }}
          />
        </div>
      </div>
      <div className="card mb-4 bg-base-100 shadow-sm">
        <div className="card-body gap-3">
          <h2 className="card-title text-lg">{t('owner.location.title')}</h2>
          <LocationPreview
            lat={restaurant.data.lat}
            lng={restaurant.data.lng}
            name={pickName(restaurant.data, lang)}
            wide
            className="h-40 sm:h-48"
          />
        </div>
      </div>
      <div className="card bg-base-100 shadow-sm">
        <div className="card-body">
          <RestaurantForm
            key={restaurant.data.updatedAt} // re-initialise after a save
            initial={original}
            submitLabel={t('owner.form.save')}
            busy={save.isPending}
            dirtyCheck={(v) => Object.keys(changedFields(original, v)).length > 0}
            onSubmit={(v) => save.mutate(changedFields(original, v))}
          />
        </div>
      </div>
    </div>
  )
}
