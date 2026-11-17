import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, NavLink, Outlet, useOutletContext } from 'react-router'
import { getRestaurant, setPaused } from '../api/endpoints'
import type { RestaurantDetail } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { LanguageToggle } from '../components/LanguageToggle'
import { LogoMark } from '../components/Logo'
import { useToast } from '../components/Toast'
import { UserMenu } from '../components/UserMenu'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { pickName } from '../lib/format'
import { loadSoundOn, saveSoundOn } from '../lib/sound'
import { ON_DARK } from '../components/onDark'
import { OwnerChatButton } from '../chat/ChatButton'

export type StaffContext = { restaurantId: string | null; soundOn: boolean }

export function useStaff(): StaffContext {
  return useOutletContext<StaffContext>()
}

export const restaurantKey = (id: string) => ['restaurant', id] as const

/** Header + (for owners) tabs for the staff area. Replaces the customer header: no cart, no customer links. */
export function StaffLayout() {
  const { role, restaurantId } = useAuth()
  const { t, lang } = useLanguage()
  const [soundOn, setSoundOn] = useState(loadSoundOn)

  const restaurant = useQuery({
    queryKey: restaurantKey(restaurantId ?? ''),
    queryFn: ({ signal }) => getRestaurant(restaurantId!, signal),
    enabled: Boolean(restaurantId),
    refetchInterval: 30_000, // open/closed and paused can change
  })

  function toggleSound() {
    setSoundOn((on) => {
      saveSoundOn(!on)
      return !on
    })
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 bg-secondary text-secondary-content shadow">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-2 px-4">
          <Link to={role === 'owner' ? '/owner' : '/counter'} className="flex min-w-0 items-center gap-2 me-auto">
            <LogoMark className="size-8 shrink-0" />
            <span className="truncate font-bold">
              {restaurant.data ? pickName(restaurant.data, lang) : t('app.name')}
            </span>
          </Link>
          {restaurant.data && <PauseToggle restaurant={restaurant.data} />}
          <button
            type="button"
            className={`btn btn-sm btn-ghost btn-square ${ON_DARK}`}
            onClick={toggleSound}
            aria-pressed={soundOn}
            aria-label={soundOn ? t('counter.soundOn') : t('counter.soundOff')}
            title={soundOn ? t('counter.soundOn') : t('counter.soundOff')}
          >
            {soundOn ? '🔔' : '🔕'}
          </button>
          <LanguageToggle className={ON_DARK} />
          <UserMenu />
        </div>
        {role === 'owner' && restaurantId && <OwnerTabs />}
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-4">
        <Outlet context={{ restaurantId, soundOn } satisfies StaffContext} />
      </main>
      {role === 'owner' && <OwnerChatButton />}
    </div>
  )
}

function OwnerTabs() {
  const { t } = useLanguage()
  const tabs: [string, MessageKey][] = [
    ['/owner/orders', 'owner.tab.orders'],
    ['/owner/menu', 'owner.tab.menu'],
    ['/owner/restaurant', 'owner.tab.restaurant'],
    ['/owner/cashiers', 'owner.tab.cashiers'],
  ]
  return (
    <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4 pb-2">
      {tabs.map(([to, key]) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => `btn btn-sm shrink-0 ${isActive ? 'btn-primary' : `btn-ghost ${ON_DARK}`}`}
        >
          {t(key)}
        </NavLink>
      ))}
    </nav>
  )
}

/** Taking orders / Paused / Closed now. Pause asks first; Resume is immediate. Owner and cashier. */
function PauseToggle({ restaurant }: { restaurant: RestaurantDetail }) {
  const { t } = useLanguage()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [asking, setAsking] = useState(false)

  const change = useMutation({
    mutationFn: (paused: boolean) => setPaused(restaurant.id, paused),
    onSuccess: (updated) => {
      queryClient.setQueryData(restaurantKey(restaurant.id), { ...restaurant, ...updated })
      setAsking(false)
    },
    onError: () => toast.show(t('auth.err.generic'), 'error'),
  })

  const label = restaurant.isPaused ? t('pause.paused') : restaurant.openNow ? t('pause.taking') : t('pause.closedNow')
  const dot = restaurant.isPaused ? 'status-neutral' : restaurant.openNow ? 'status-success' : 'status-warning'

  return (
    <>
      <div className="flex items-center gap-2">
        <span className="hidden items-center gap-1 text-sm sm:flex">
          <span className={`status ${dot}`} aria-hidden="true" />
          {label}
        </span>
        {restaurant.isPaused ? (
          <button type="button" className="btn btn-sm btn-success" onClick={() => change.mutate(false)} disabled={change.isPending}>
            {t('pause.resume')}
          </button>
        ) : (
          <button type="button" className="btn btn-sm btn-outline text-secondary-content" onClick={() => setAsking(true)}>
            {t('pause.pause')}
          </button>
        )}
      </div>
      <ConfirmDialog
        open={asking}
        title={t('pause.confirmTitle')}
        confirmLabel={t('pause.pause')}
        cancelLabel={t('common.cancel')}
        busy={change.isPending}
        onCancel={() => setAsking(false)}
        onConfirm={() => change.mutate(true)}
      >
        {t('pause.confirmBody')}
      </ConfirmDialog>
    </>
  )
}
