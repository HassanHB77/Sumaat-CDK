import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { getNearby } from '../api/endpoints'
import { LocationBar } from '../components/LocationBar'
import { PageContainer } from '../components/PageContainer'
import { CuisineFilterChips } from '../components/CuisineParts'
import { RestaurantCard } from '../components/RestaurantCard'
import { RestaurantsMap } from '../components/RestaurantsMap'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'
import { formatKm } from '../lib/format'
import { DEFAULT_RADIUS, loadSpot, saveSpot, type Radius, type Spot } from '../lib/geo'
import type { Cuisine } from '../api/types'
import { availableCuisines, filterByCuisine } from '../lib/cuisine'
import { sortRestaurants } from '../lib/menu'

export function RestaurantsPage() {
  const { t, lang } = useLanguage()
  const navigate = useNavigate()
  usePageTitle(t('page.restaurants'))
  const [spot, setSpot] = useState<Spot>(loadSpot)
  const [radius, setRadius] = useState<Radius>(DEFAULT_RADIUS)
  const [cuisines, setCuisines] = useState<Cuisine[]>([])

  const nearby = useQuery({
    queryKey: ['restaurants', spot.lat.toFixed(4), spot.lng.toFixed(4), radius],
    queryFn: ({ signal }) => getNearby(spot.lat, spot.lng, radius, signal),
    placeholderData: keepPreviousData, // keep the old list visible while a new area loads
    refetchInterval: 60_000, // open/closed can change while the page is open
  })

  function changeSpot(next: Spot) {
    setSpot(next)
    saveSpot(next)
  }

  const all = useMemo(() => (nearby.data ? sortRestaurants(nearby.data) : []), [nearby.data])
  const offered = useMemo(() => availableCuisines(all), [all])
  // A chip whose cuisine left the area (new spot) stops filtering.
  const active = cuisines.filter((c) => offered.includes(c))
  const list = filterByCuisine(all, active)

  return (
    <PageContainer title={t('page.restaurants')}>
      <div className="flex flex-col gap-4">
        <LocationBar spot={spot} onSpot={changeSpot} radius={radius} onRadius={setRadius} />
        <CuisineFilterChips cuisines={offered} selected={active} onChange={setCuisines} />
        <RestaurantsMap
          center={spot}
          radiusKm={radius}
          restaurants={list}
          onSearchHere={(p) => changeSpot({ lat: p.lat, lng: p.lng, label: 'map' })}
          onOpen={(id) => navigate(`/r/${id}`)}
        />

        {nearby.isPending ? (
          <LoadingState />
        ) : nearby.isError ? (
          <ErrorState onRetry={() => nearby.refetch()} />
        ) : all.length === 0 ? (
          <EmptyState>{t('list.empty', { km: formatKm(radius, lang) })}</EmptyState>
        ) : list.length === 0 ? (
          <EmptyState>{t('list.emptyCuisine')}</EmptyState>
        ) : (
          <ul className={`flex flex-col gap-3 ${nearby.isPlaceholderData ? 'opacity-60' : ''}`}>
            {list.map((r) => (
              <li key={r.id}>
                <RestaurantCard restaurant={r} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageContainer>
  )
}
