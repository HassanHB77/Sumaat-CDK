import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { ApiError } from '../api/client'
import { getRestaurantOrders, type StaffAction } from '../api/endpoints'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { OrderStatusBadge, statusKey } from '../components/OrderParts'
import { ErrorState, LoadingState } from '../components/States'
import { useToast } from '../components/Toast'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { formatTime } from '../lib/format'
import { unlockSound } from '../lib/sound'
import { buildBoard, COLUMNS, statusAfter, type BoardCard, type Column, type Pending } from './boardLogic'
import { boardKey, useNewOrderAlert, useNow, usePendingActions } from './hooks'
import { OrderCard } from './OrderCard'

const POLL_MS = 5000

const COLUMN_STYLE: Record<Exclude<Column, 'done'>, string> = {
  new: 'border-primary',
  preparing: 'border-accent',
  ready: 'border-success',
}

/** The counter: New | Preparing | Ready (+ Done today). Shared by cashiers (/counter) and owners (/owner/orders). */
export function OrderBoard({ restaurantId, soundOn }: { restaurantId: string; soundOn: boolean }) {
  const { t } = useLanguage()
  const { logout } = useAuth()
  const toast = useToast()
  const now = useNow(500)
  const [started, setStarted] = useState(false)
  const [tab, setTab] = useState<Exclude<Column, 'done'>>('new')
  const [rejecting, setRejecting] = useState<BoardCard | null>(null)

  const orders = useQuery({
    queryKey: boardKey(restaurantId),
    queryFn: ({ signal }) => getRestaurantOrders(restaurantId, signal),
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: true, // a counter screen is often not the focused tab
  })

  const noAccess = () => {
    toast.show(t('counter.noAccess'), 'error', 8000)
    logout()
  }
  const { pending, start, undo } = usePendingActions(restaurantId, noAccess)
  const { pulse } = useNewOrderAlert(orders.data, soundOn)
  const board = useMemo(() => buildBoard(orders.data ?? [], pending), [orders.data, pending])

  if (orders.isPending) return <LoadingState rows={3} />
  if (orders.isError) {
    const lost = orders.error instanceof ApiError && (orders.error.status === 403 || orders.error.status === 404)
    return lost ? (
      <div role="alert" className="alert alert-error">
        <span>{t('counter.noAccess')}</span>
        <button type="button" className="btn btn-sm" onClick={() => logout()}>
          {t('auth.logout')}
        </button>
      </div>
    ) : (
      <ErrorState onRetry={() => orders.refetch()} />
    )
  }

  const act = (card: BoardCard, action: StaffAction, reason?: string) =>
    start({ orderId: card.id, orderNumber: card.orderNumber, action, reason })

  return (
    <div className="flex flex-col gap-4">
      {/* Phones: tabs. Tablets/laptops: three columns side by side. */}
      <div role="tablist" className="tabs tabs-box md:hidden">
        {COLUMNS.map((c) => (
          <button key={c} type="button" role="tab" className={`tab ${tab === c ? 'tab-active' : ''}`} onClick={() => setTab(c)}>
            {t(`counter.col.${c}` as MessageKey)}
            <span className="badge badge-sm ms-1">{board[c].length}</span>
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {COLUMNS.map((c) => (
          <section key={c} className={`${tab === c ? 'flex' : 'hidden'} min-w-0 flex-col gap-3 md:flex`}>
            <h2
              className={`flex items-center justify-between border-b-4 pb-1 text-lg font-bold ${COLUMN_STYLE[c]} ${
                c === 'new' && pulse ? 'animate-pulse text-primary' : ''
              }`}
            >
              {t(`counter.col.${c}` as MessageKey)}
              <span className="badge">{board[c].length}</span>
            </h2>
            {board[c].length === 0 ? (
              <p className="rounded-box border border-dashed border-base-300 p-6 text-center text-sm text-muted">
                {t('counter.empty')}
              </p>
            ) : (
              board[c].map((card) => (
                <OrderCard key={card.id} card={card} now={now} onAction={act} onReject={setRejecting} />
              ))
            )}
          </section>
        ))}
      </div>

      <details className="collapse-arrow collapse bg-base-100 shadow-sm">
        <summary className="collapse-title font-medium">{t('counter.done', { count: board.done.length })}</summary>
        <div className="collapse-content">
          <ul className="divide-y divide-base-300">
            {board.done.map((card) => (
              <li key={card.id} className="flex items-center justify-between gap-2 py-2">
                <span>
                  <span className="font-bold" dir="ltr">
                    #{card.orderNumber}
                  </span>{' '}
                  {card.customerName}
                </span>
                <span className="flex items-center gap-2 text-sm text-muted">
                  <span dir="ltr">{formatTime(card.updatedAt, 'en')}</span>
                  <OrderStatusBadge status={card.shownStatus} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      </details>

      <UndoToasts pending={pending} now={now} onUndo={undo} />

      <RejectDialog
        card={rejecting}
        onCancel={() => setRejecting(null)}
        onConfirm={(reason) => {
          if (rejecting) act(rejecting, 'reject', reason)
          setRejecting(null)
        }}
      />

      {!started && (
        <StartShiftOverlay
          onStart={() => {
            unlockSound()
            setStarted(true)
          }}
        />
      )}
    </div>
  )
}

function UndoToasts({ pending, now, onUndo }: { pending: Pending[]; now: number; onUndo: (orderId: string) => void }) {
  const { t } = useLanguage()
  if (!pending.length) return null
  return (
    <div className="toast toast-center toast-bottom z-50">
      {pending.map((p) => {
        const s = Math.max(0, Math.ceil((p.dueAt - now) / 1000))
        return (
          <div key={p.orderId} role="status" className={`alert ${p.action === 'reject' ? 'alert-error' : 'alert-info'} shadow-lg`}>
            <span className="font-medium" dir="auto">
              {t('counter.pendingToast', { n: p.orderNumber, status: t(statusKey(statusAfter(p.action))) })}
            </span>
            <button type="button" className="btn btn-sm" onClick={() => onUndo(p.orderId)}>
              {t('counter.undo')} ({s})
            </button>
          </div>
        )
      })}
    </div>
  )
}

const REASONS: MessageKey[] = ['counter.reject.unavailable', 'counter.reject.busy', 'counter.reject.closing']

function RejectDialog({
  card,
  onCancel,
  onConfirm,
}: {
  card: BoardCard | null
  onCancel: () => void
  onConfirm: (reason: string) => void
}) {
  const { t } = useLanguage()
  const [chip, setChip] = useState<MessageKey | null>(null)
  const [other, setOther] = useState('')
  const reason = [chip ? t(chip) : '', other.trim()].filter(Boolean).join(' — ').slice(0, 200)

  function close(fn: () => void) {
    setChip(null)
    setOther('')
    fn()
  }

  return (
    <ConfirmDialog
      open={card !== null}
      title={t('counter.reject.title', { n: card?.orderNumber ?? '' })}
      confirmLabel={t('counter.reject.confirm')}
      cancelLabel={t('common.cancel')}
      danger
      onCancel={() => close(onCancel)}
      onConfirm={() => close(() => onConfirm(reason))}
    >
      <p className="mb-2 text-sm text-muted">{t('counter.reject.why')}</p>
      <div className="mb-3 flex flex-wrap gap-2">
        {REASONS.map((r) => (
          <button
            key={r}
            type="button"
            className={`btn btn-sm rounded-full ${chip === r ? 'btn-error' : 'btn-outline'}`}
            onClick={() => setChip(chip === r ? null : r)}
          >
            {t(r)}
          </button>
        ))}
      </div>
      <input
        className="input w-full"
        maxLength={150}
        placeholder={t('counter.reject.other')}
        value={other}
        onChange={(e) => setOther(e.target.value)}
      />
    </ConfirmDialog>
  )
}

function StartShiftOverlay({ onStart }: { onStart: () => void }) {
  const { t } = useLanguage()
  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-secondary/80 p-6 backdrop-blur-sm">
      <div className="card w-full max-w-sm bg-base-100 text-center shadow-xl">
        <div className="card-body items-center gap-4">
          <p>{t('counter.startShiftBody')}</p>
          <button type="button" className="btn btn-primary btn-lg w-full" onClick={onStart} autoFocus>
            {t('counter.startShift')}
          </button>
        </div>
      </div>
    </div>
  )
}
