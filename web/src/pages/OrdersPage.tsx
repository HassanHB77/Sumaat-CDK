import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getMyOrders } from '../api/endpoints'
import type { Order } from '../api/types'
import { OrderStatusBadge } from '../components/OrderParts'
import { PageContainer } from '../components/PageContainer'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'
import { formatMoney, formatOrderLabel, pickName } from '../lib/format'
import { isOpen } from '../lib/orders'

function OrderRow({ order: o }: { order: Order }) {
  const { lang } = useLanguage()
  return (
    <li>
      <Link
        to={`/orders/${o.id}`}
        className="flex items-center justify-between gap-3 rounded-box bg-base-100 p-4 shadow-sm transition hover:shadow-md"
      >
        <div className="min-w-0">
          <p className="font-medium">{pickName({ name: o.restaurantName, nameAr: o.restaurantNameAr ?? '' }, lang)}</p>
          <p className="text-sm text-muted" dir="ltr">
            {formatOrderLabel(o.orderNumber, o.businessDate, lang)} · {formatMoney(o.totalHalalas, lang)}
          </p>
        </div>
        <OrderStatusBadge status={o.status} />
      </Link>
    </li>
  )
}

export function OrdersPage() {
  const { t } = useLanguage()
  usePageTitle(t('page.orders'))
  const mine = useQuery({
    queryKey: ['orders', 'mine'],
    queryFn: ({ signal }) => getMyOrders(signal),
    refetchInterval: 30_000,
  })

  if (mine.isPending)
    return (
      <PageContainer title={t('page.orders')}>
        <LoadingState />
      </PageContainer>
    )
  if (mine.isError)
    return (
      <PageContainer title={t('page.orders')}>
        <ErrorState onRetry={() => mine.refetch()} />
      </PageContainer>
    )

  const active = mine.data.filter((o) => isOpen(o.status))
  const past = mine.data.filter((o) => !isOpen(o.status))

  return (
    <PageContainer title={t('page.orders')}>
      {mine.data.length === 0 ? (
        <EmptyState>
          <p className="mb-4">{t('orders.empty')}</p>
          <Link to="/restaurants" className="btn btn-primary">
            {t('cart.browse')}
          </Link>
        </EmptyState>
      ) : (
        <div className="mx-auto flex max-w-xl flex-col gap-6">
          {active.length > 0 && (
            <section>
              <h2 className="mb-2 text-lg font-bold">{t('orders.active')}</h2>
              <ul className="flex flex-col gap-2">
                {active.map((o) => (
                  <OrderRow key={o.id} order={o} />
                ))}
              </ul>
            </section>
          )}
          {past.length > 0 && (
            <section>
              <h2 className="mb-2 text-lg font-bold text-muted">{t('orders.past')}</h2>
              <ul className="flex flex-col gap-2 opacity-90">
                {past.map((o) => (
                  <OrderRow key={o.id} order={o} />
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </PageContainer>
  )
}
