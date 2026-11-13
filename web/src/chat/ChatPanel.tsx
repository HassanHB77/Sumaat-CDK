import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { DraftCard } from './DraftCard'
import { MAX_MESSAGE, type ChatMessage, type ChatState } from './chatState'

const CHIPS: MessageKey[] = ['chat.chip1', 'chat.chip2', 'chat.chip3']
const TOOL_LABELS: Record<string, MessageKey> = {
  find_restaurants: 'chat.tool.find_restaurants',
  search_dishes: 'chat.tool.search_dishes',
  get_menu: 'chat.tool.get_menu',
  list_categories: 'chat.tool.list_categories',
  draft_cart: 'chat.tool.draft_cart',
}

type Props = {
  open: boolean
  onClose: () => void
  signedInCustomer: boolean
  state: ChatState
  limit: number
  onSend: (text: string) => void
  onNew: () => void
  onDraftAdded: (index: number) => void
}

/** Bottom sheet on phones, side panel on larger screens (native <dialog>: Esc and the backdrop close it).
 *  `sm:[translate:0]`: DaisyUI's RTL rule for modal-end (translate -100%) outranks its "open" rule, so in Arabic
 *  the panel stayed off-screen and only the dimmed backdrop showed. Pinning it in place fixes that (it fades in). */
export function ChatPanel({ open, onClose, signedInCustomer, state, limit, onSend, onNew, onDraftAdded }: Props) {
  const { t } = useLanguage()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [draft, setDraft] = useState('')
  const location = useLocation()

  useEffect(() => {
    const d = dialogRef.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  // Keep the newest message in view.
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [state.messages, open])

  const outOfMessages = state.left === 0
  const canSend = signedInCustomer && !state.sending && !outOfMessages
  const submit = (text: string) => {
    if (!canSend || !text.trim()) return
    onSend(text.slice(0, MAX_MESSAGE))
    setDraft('')
    inputRef.current?.focus()
  }

  return (
    <dialog ref={dialogRef} className="modal modal-bottom sm:modal-end" onClose={onClose} aria-label={t('chat.title')}>
      <div className="modal-box flex h-[85dvh] max-h-none flex-col gap-0 p-0 sm:h-dvh sm:w-full sm:max-w-md sm:rounded-none sm:[translate:0]">
        {/* Header */}
        <div className="bg-secondary text-secondary-content flex items-center gap-2 px-4 py-3">
          <div className="flex-1">
            <h2 className="font-bold">{t('chat.title')}</h2>
            {signedInCustomer && (
              <span
                className={`badge badge-sm ${state.left !== null && state.left <= 2 ? 'badge-error' : 'badge-ghost'}`}
                aria-live="polite"
              >
                {state.left === null ? t('chat.limit', { limit }) : t('chat.left', { left: state.left, limit })}
              </span>
            )}
          </div>
          {signedInCustomer && state.messages.length > 0 && (
            <button type="button" className="btn btn-sm btn-outline border-secondary-content/40 text-secondary-content" onClick={onNew}>
              {t('chat.new')}
            </button>
          )}
          <button type="button" className="btn btn-sm btn-circle btn-ghost text-secondary-content" onClick={onClose} aria-label={t('chat.close')}>
            ✕
          </button>
        </div>

        {/* Messages */}
        <div ref={listRef} className="flex-1 overflow-y-auto px-3 py-3">
          {!signedInCustomer ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <p>{t('chat.loginNeeded')}</p>
              <Link
                to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
                className="btn btn-primary"
                onClick={onClose}
              >
                {t('nav.login')}
              </Link>
            </div>
          ) : (
            <>
              <div className="chat chat-start">
                <div className="chat-bubble">{t('chat.hello')}</div>
              </div>
              {state.messages.length === 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {CHIPS.map((key) => (
                    <button key={key} type="button" className="btn btn-sm btn-outline btn-primary" disabled={!canSend} onClick={() => submit(t(key))}>
                      {t(key)}
                    </button>
                  ))}
                </div>
              )}
              {state.messages.map((m, i) => (
                <Message key={i} message={m} onDraftAdded={() => onDraftAdded(i)} />
              ))}
            </>
          )}
        </div>

        {/* Input */}
        {signedInCustomer && (
          <form
            className="border-base-300 flex flex-col gap-1 border-t px-3 py-2"
            onSubmit={(e) => {
              e.preventDefault()
              submit(draft)
            }}
          >
            <div className="flex gap-2">
              <input
                ref={inputRef}
                className="input input-bordered flex-1"
                dir="auto"
                value={draft}
                maxLength={MAX_MESSAGE}
                placeholder={t('chat.placeholder')}
                onChange={(e) => setDraft(e.target.value)}
                disabled={outOfMessages}
                aria-label={t('chat.placeholder')}
              />
              <button type="submit" className="btn btn-primary" disabled={!canSend || !draft.trim()}>
                {state.sending ? <span className="loading loading-spinner loading-sm" /> : t('chat.send')}
              </button>
            </div>
            <div className="flex justify-between text-xs opacity-60">
              <span>{t('chat.disclaimer')}</span>
              {draft.length > MAX_MESSAGE - 100 && <span dir="ltr">{draft.length}/{MAX_MESSAGE}</span>}
            </div>
          </form>
        )}
      </div>
      <form method="dialog" className="modal-backdrop">
        <button type="submit" aria-label={t('chat.close')} />
      </form>
    </dialog>
  )
}

function Message({ message: m, onDraftAdded }: { message: ChatMessage; onDraftAdded: () => void }) {
  const { t } = useLanguage()
  if (m.role === 'user') {
    return (
      <div className="chat chat-end">
        <div className="chat-bubble chat-bubble-primary whitespace-pre-line" dir="auto">
          {m.text}
        </div>
      </div>
    )
  }
  const waiting = !m.done && !m.text && !m.blocked
  return (
    <div className="chat chat-start">
      <div className={`chat-bubble ${m.blocked || m.error ? 'opacity-80' : ''}`}>
        {waiting && (
          <span className="flex items-center gap-2 text-sm">
            <span className="loading loading-dots loading-sm" />
            {t(TOOL_LABELS[m.status ?? ''] ?? 'chat.thinking')}
          </span>
        )}
        {m.text && (
          <div className="whitespace-pre-line" dir="auto">
            {m.text}
          </div>
        )}
        {m.blocked && <div className="italic">{t('chat.blocked')}</div>}
        {m.error && <div className="text-sm italic">{t(`chat.err.${m.error}` as MessageKey)}</div>}
        {m.draft && !m.blocked && <DraftCard draft={m.draft} added={!!m.added} onAdded={onDraftAdded} />}
      </div>
    </div>
  )
}
