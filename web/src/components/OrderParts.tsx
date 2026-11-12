import type { Order, OrderStatus } from '../api/types'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { formatMoney, formatTime, pickName } from '../lib/format'
import { STEPS, stepIndex, timeOf } from '../lib/orders'

export const statusKey = (s: OrderStatus) => `ostatus.${s}` as MessageKey

const BADGE: Record<OrderStatus, string> = {
  PLACED: 'badge-primary',
  ACCEPTED: 'badge-accent',
  READY_FOR_PICKUP: 'badge-success',
  SERVED: 'badge-ghost',
  REJECTED: 'badge-error',
  CANCELLED: 'badge-ghost',
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  const { t } = useLanguage()
  return <span className={`badge ${BADGE[status]} whitespace-nowrap`}>{t(statusKey(status))}</span>
}

/** Placed -> Accepted -> Ready -> Served, with the time of each reached step. */
export function OrderStepper({ order }: { order: Order }) {
  const { t, lang } = useLanguage()
  const current = stepIndex(order.status)
  return (
    <ul className="steps steps-horizontal w-full">
      {STEPS.map((s, i) => {
        const at = timeOf(order, s)
        return (
          <li key={s} className={`step ${i <= current ? (s === 'READY_FOR_PICKUP' || s === 'SERVED' ? 'step-success' : 'step-primary') : ''}`}>
            <span className="text-sm">{t(statusKey(s))}</span>
            {at && i <= current && (
              <span className="block text-xs text-muted" dir="ltr">
                {formatTime(at, lang)}
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}

/** qty × name ..... line total, then the total (VAT included). */
export function OrderItems({ order }: { order: Order }) {
  const { t, lang } = useLanguage()
  return (
    <div className="flex flex-col gap-2">
      <ul className="divide-y divide-base-300">
        {order.items.map((l) => (
          <li key={l.itemId} className="flex justify-between gap-3 py-2">
            <span>
              <span dir="ltr" className="font-bold">
                {l.qty} ×
              </span>{' '}
              {pickName(l, lang)}
            </span>
            <span dir="ltr">{formatMoney(l.lineTotalHalalas, lang)}</span>
          </li>
        ))}
      </ul>
      <div className="flex justify-between border-t border-base-300 pt-2 text-lg font-bold">
        <span>{t('cart.total')}</span>
        <span dir="ltr">{formatMoney(order.totalHalalas, lang)}</span>
      </div>
    </div>
  )
}
