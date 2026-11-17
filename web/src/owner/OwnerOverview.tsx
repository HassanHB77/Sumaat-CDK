import { useQuery } from '@tanstack/react-query'
import { getOwnerStats } from '../api/endpoints'
import type { OwnerStats } from '../api/types'
import { useLanguage } from '../i18n/LanguageContext'
import { formatDayShort, formatMoneyWhole, pickName } from '../lib/format'

const REFRESH_MS = 60_000

/** Owner only (top of /owner/orders): today's numbers + sales of the last 7 business days. Sales = served orders. */
export function OwnerOverview({ restaurantId }: { restaurantId: string }) {
  const { t } = useLanguage()
  const stats = useQuery({
    queryKey: ['owner-stats', restaurantId],
    queryFn: ({ signal }) => getOwnerStats(restaurantId, signal),
    refetchInterval: REFRESH_MS,
  })
  if (stats.isPending) return <div className="skeleton h-28 w-full" aria-hidden="true" />
  if (stats.isError) return null // the order board below matters more; numbers come back on the next refresh
  return (
    <section aria-label={t('owner.stats.title')} className="flex flex-col gap-3">
      <TodayCards today={stats.data.today} />
      <SalesChart days={stats.data.last7} />
    </section>
  )
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-box bg-base-100 p-3 shadow-sm">
      <span className="text-xs text-muted">{label}</span>
      <span className="truncate text-xl font-bold" dir="auto">
        {value}
      </span>
      {sub && <span className="truncate text-xs text-muted">{sub}</span>}
    </div>
  )
}

function TodayCards({ today }: { today: OwnerStats['today'] }) {
  const { t, lang } = useLanguage()
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile
        label={t('owner.stats.orders')}
        value={String(today.orders)}
        sub={t('owner.stats.breakdown', { served: today.served, open: today.open, rejected: today.rejected + today.cancelled })}
      />
      <Tile
        label={t('owner.stats.sales')}
        value={formatMoneyWhole(today.salesHalalas, lang)}
        sub={today.served ? t('owner.stats.avgOrder', { amount: formatMoneyWhole(today.avgOrderHalalas, lang) }) : undefined}
      />
      <Tile
        label={t('owner.stats.prep')}
        value={today.avgPrepMinutes == null ? '—' : t('owner.stats.minutes', { n: Math.round(today.avgPrepMinutes) })}
        sub={t('owner.stats.prepHint')}
      />
      <Tile
        label={t('owner.stats.best')}
        value={today.bestSeller ? pickName(today.bestSeller, lang) : '—'}
        sub={today.bestSeller ? t('owner.stats.sold', { n: today.bestSeller.qty }) : undefined}
      />
    </div>
  )
}

const PLOT_HEIGHT = 112 // px

/**
 * One series (sales per business day): thin columns in the brand colour, growing from one baseline, 4px rounded
 * tops. Today's value is labelled; every column shows its day, sales and orders on hover / keyboard focus; a
 * screen-reader table repeats the numbers. Time runs left to right in both languages.
 */
function SalesChart({ days }: { days: OwnerStats['last7'] }) {
  const { t, lang } = useLanguage()
  const max = Math.max(1, ...days.map((d) => d.salesHalalas))
  const total = days.reduce((sum, d) => sum + d.salesHalalas, 0)
  return (
    <figure className="rounded-box bg-base-100 p-3 shadow-sm">
      <figcaption className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold">{t('owner.stats.chartTitle')}</span>
        <span className="text-xs text-muted">{t('owner.stats.chartTotal', { amount: formatMoneyWhole(total, lang) })}</span>
      </figcaption>
      <div className="flex items-end justify-between gap-1 border-b border-base-300" style={{ height: PLOT_HEIGHT + 20 }} dir="ltr">
        {days.map((d, i) => {
          const isToday = i === days.length - 1
          const h = d.salesHalalas ? Math.max(3, Math.round((d.salesHalalas / max) * PLOT_HEIGHT)) : 0
          const tip = t('owner.stats.chartTip', {
            day: formatDayShort(d.date, lang),
            amount: formatMoneyWhole(d.salesHalalas, lang),
            n: d.servedOrders,
          })
          return (
            <div
              key={d.date}
              tabIndex={0}
              aria-label={tip}
              data-tip={tip}
              className="tooltip tooltip-top group flex h-full flex-1 flex-col items-center justify-end rounded outline-offset-2 focus-visible:outline-2 focus-visible:outline-primary"
            >
              {isToday && (
                <span className="mb-1 text-[11px] font-semibold leading-none">{formatMoneyWhole(d.salesHalalas, lang)}</span>
              )}
              <div
                className={`w-full max-w-6 rounded-t-[4px] transition-opacity ${isToday ? 'bg-primary' : 'bg-primary/60'} group-hover:opacity-80`}
                style={{ height: h }}
              />
            </div>
          )
        })}
      </div>
      <div className="mt-1 flex justify-between gap-1" dir="ltr">
        {days.map((d, i) => (
          <span key={d.date} className={`flex-1 text-center text-[11px] ${i === days.length - 1 ? 'font-semibold' : 'text-muted'}`}>
            {i === days.length - 1 ? t('owner.stats.today') : formatDayShort(d.date, lang)}
          </span>
        ))}
      </div>
      <table className="sr-only">
        <caption>{t('owner.stats.chartTitle')}</caption>
        <thead>
          <tr>
            <th scope="col">{t('owner.stats.day')}</th>
            <th scope="col">{t('owner.stats.sales')}</th>
            <th scope="col">{t('owner.stats.orders')}</th>
          </tr>
        </thead>
        <tbody>
          {days.map((d) => (
            <tr key={d.date}>
              <th scope="row">{formatDayShort(d.date, lang)}</th>
              <td>{formatMoneyWhole(d.salesHalalas, lang)}</td>
              <td>{d.servedOrders}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
