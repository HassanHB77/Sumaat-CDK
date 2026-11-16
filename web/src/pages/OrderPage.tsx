import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { cancelOrder, getOrder, getRestaurant } from '../api/endpoints'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { LocationPreview } from '../components/LocationPreview'
import { OrderItems, OrderStatusBadge, OrderStepper } from '../components/OrderParts'
import { PageContainer } from '../components/PageContainer'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useToast } from '../components/Toast'
import { useLanguage } from '../i18n/LanguageContext'
import { formatOrderLabel, formatTime, pickName } from '../lib/format'
import { isFinal, rejectReason } from '../lib/orders'
import { usePageTitle } from '../lib/usePageTitle'

const LIVE_MS = 10_000 // refresh while the order is still moving

export function OrderPage() {
  const { orderId = '' } = useParams()
  const { t, lang } = useLanguage()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [confirmCancel, setConfirmCancel] = useState(false)

  const order = useQuery({
    queryKey: ['orders', orderId],
    queryFn: ({ signal }) => getOrder(orderId, signal),
    // Every 10 s until it's finished; TanStack pauses this while the tab is hidden.
    refetchInterval: (q) => (q.state.data && isFinal(q.state.data.status) ? false : LIVE_MS),
  })

  // Orders don't carry the restaurant's location: load it (shared cache with the menu page) for the map + "Go".
  const restaurantId = order.data?.restaurantId
  const place = useQuery({
    queryKey: ['restaurant', restaurantId],
    queryFn: ({ signal }) => getRestaurant(restaurantId!, signal),
    enabled: !!restaurantId,
    staleTime: 5 * 60_000,
  })

  const cancel = useMutation({
    mutationFn: () => cancelOrder(orderId),
    onSuccess: (updated) => {
      queryClient.setQueryData(['orders', orderId], updated)
      queryClient.invalidateQueries({ queryKey: ['orders', 'mine'] })
      toast.show(t('order.cancelledToast'), 'success')
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) toast.show(t('order.tooLate'), 'error', 6000)
      else toast.show(t('auth.err.generic'), 'error')
      order.refetch()
    },
    onSettled: () => setConfirmCancel(false),
  })
  usePageTitle(order.data ? formatOrderLabel(order.data.orderNumber, order.data.businessDate, lang) : t('page.order'))

  if (order.isPending) {
    return (
      <PageContainer>
        <LoadingState rows={3} />
      </PageContainer>
    )
  }
  if (order.isError) {
    const notFound = order.error instanceof ApiError && order.error.status === 404
    return (
      <PageContainer>
        {notFound ? (
          <EmptyState>
            <p className="mb-4">{t('order.notFound')}</p>
            <Link to="/orders" className="btn btn-primary">
              {t('page.orders')}
            </Link>
          </EmptyState>
        ) : (
          <ErrorState onRetry={() => order.refetch()} />
        )}
      </PageContainer>
    )
  }

  const o = order.data
  const label = formatOrderLabel(o.orderNumber, o.businessDate, lang)
  const restaurant = pickName({ name: o.restaurantName, nameAr: o.restaurantNameAr ?? '' }, lang)
  const reason = rejectReason(o)
  // The order keeps its own names and prices; photos come from the restaurant's current menu (already loaded).
  const photos = new Map((place.data?.menu ?? []).flatMap((m) => (m.imageUrl ? [[m.id, m.imageUrl] as const] : [])))

  return (
    <PageContainer>
      <div className="mx-auto flex max-w-xl flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold" dir="ltr">
              {label}
            </h1>
            <Link to={`/r/${o.restaurantId}`} className="link link-hover text-lg">
              {restaurant}
            </Link>
            <p className="text-sm text-muted">{t('order.placedAt', { time: formatTime(o.createdAt, lang) })}</p>
          </div>
          <OrderStatusBadge status={o.status} />
        </div>

        {place.data && (
          <LocationPreview lat={place.data.lat} lng={place.data.lng} name={restaurant} wide className="h-40 sm:h-48" />
        )}

        {o.status === 'READY_FOR_PICKUP' && (
          <div role="status" className="alert alert-success text-lg font-bold">
            {t('order.ready', { n: o.orderNumber })}
          </div>
        )}
        {o.status === 'SERVED' && <div className="alert">{t('order.served')}</div>}
        {o.status === 'REJECTED' && (
          <div role="alert" className="alert alert-error flex-col items-start">
            <span className="font-bold">{t('order.rejected')}</span>
            {reason && <span>{t('order.reason', { reason })}</span>}
          </div>
        )}
        {o.status === 'CANCELLED' && <div className="alert alert-error">{t('order.cancelled')}</div>}

        {o.status !== 'REJECTED' && o.status !== 'CANCELLED' && (
          <div className="rounded-box bg-base-100 p-4 shadow-sm">
            <OrderStepper order={o} />
          </div>
        )}

        <div className="rounded-box bg-base-100 p-4 shadow-sm">
          <OrderItems order={o} photos={photos} />
          {o.note && (
            <p className="mt-3 rounded-box bg-warning/20 p-2 text-sm">
              <span className="font-medium">{t('order.note')}:</span> {o.note}
            </p>
          )}
          <p className="mt-3 text-sm text-muted">{t('order.payAtCounter')}</p>
        </div>

        <div className="flex items-center justify-between gap-2">
          {!isFinal(o.status) ? (
            <span className="flex items-center gap-2 text-sm text-muted">
              <span className="status status-success animate-pulse" aria-hidden="true" />
              {t('order.live')}
            </span>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => order.refetch()} disabled={order.isFetching}>
              {order.isFetching && <span className="loading loading-spinner loading-xs" />}
              {t('order.refresh')}
            </button>
            {o.status === 'PLACED' && (
              <button type="button" className="btn btn-outline btn-error btn-sm" onClick={() => setConfirmCancel(true)}>
                {t('order.cancel')}
              </button>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmCancel}
        title={t('order.cancelTitle')}
        confirmLabel={t('order.cancel')}
        cancelLabel={t('order.keep')}
        danger
        busy={cancel.isPending}
        onCancel={() => setConfirmCancel(false)}
        onConfirm={() => cancel.mutate()}
      >
        {t('order.cancelBody')}
      </ConfirmDialog>
    </PageContainer>
  )
}
