import type { StaffAction } from '../api/endpoints'
import { useLanguage } from '../i18n/LanguageContext'
import type { MessageKey } from '../i18n/en'
import { formatMoney, pickName } from '../lib/format'
import { minutesSince, nextAction, UNDO_MS, type BoardCard } from './boardLogic'

const ACTION_STYLE: Record<Exclude<StaffAction, 'reject'>, string> = {
  accept: 'btn-primary',
  ready: 'btn-accent',
  served: 'btn-success',
}

export function OrderCard({
  card,
  now,
  onAction,
  onReject,
}: {
  card: BoardCard
  now: number
  onAction: (card: BoardCard, action: StaffAction) => void
  onReject: (card: BoardCard) => void
}) {
  const { t, lang } = useLanguage()
  const mins = minutesSince(card.createdAt, now)
  const action = card.pending ? null : nextAction(card.status)
  const secondsLeft = card.pending ? Math.max(0, Math.ceil((card.pending.dueAt - now) / 1000)) : 0
  const progress = card.pending ? Math.min(100, Math.max(0, 100 - ((card.pending.dueAt - now) / UNDO_MS) * 100)) : 0

  return (
    <article className={`card bg-base-100 shadow-sm transition ${card.pending ? 'opacity-50' : ''}`}>
      <div className="card-body gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-3xl font-bold leading-none" dir="ltr">
            #{card.orderNumber}
          </h3>
          {card.pending ? (
            <div className="radial-progress text-xs text-primary" style={{ '--value': progress, '--size': '2.2rem' } as React.CSSProperties} role="progressbar">
              {secondsLeft}
            </div>
          ) : (
            <span className={`badge ${mins >= 15 ? 'badge-error' : 'badge-ghost'}`} dir="ltr">
              {mins < 1 ? t('counter.justNow') : t('counter.minAgo', { n: mins })}
            </span>
          )}
        </div>
        <p className="text-sm">
          <span className="font-medium">{card.customerName}</span>
          {card.customerPhone && (
            <>
              {' · '}
              <a className="link" href={`tel:${card.customerPhone}`} dir="ltr">
                {card.customerPhone}
              </a>
            </>
          )}
        </p>
        <ul className="text-base">
          {card.items.map((l) => (
            <li key={l.itemId}>
              <span className="font-bold" dir="ltr">
                {l.qty} ×
              </span>{' '}
              {pickName(l, lang)}
            </li>
          ))}
        </ul>
        {card.note && <p className="rounded-box bg-warning/30 p-2 text-sm font-medium">{card.note}</p>}
        <p className="text-sm text-muted" dir="ltr">
          {formatMoney(card.totalHalalas, lang)}
        </p>
        {action && (
          <div className="card-actions mt-1 items-center">
            <button type="button" className={`btn btn-lg flex-1 ${ACTION_STYLE[action]}`} onClick={() => onAction(card, action)}>
              {t(`counter.act.${action}` as MessageKey)}
            </button>
            {action === 'accept' && (
              <button type="button" className="btn btn-ghost btn-sm text-error" onClick={() => onReject(card)}>
                {t('counter.act.reject')}
              </button>
            )}
          </div>
        )}
      </div>
    </article>
  )
}
