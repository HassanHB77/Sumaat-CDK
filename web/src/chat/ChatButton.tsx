import { useState } from 'react'
import { useLocation } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { useCart } from '../cart/CartContext'
import { getConfig } from '../config/config'
import { useLanguage } from '../i18n/LanguageContext'
import { ChatPanel } from './ChatPanel'
import type { ChatMode } from './chatState'
import { useChat } from './useChat'

/** Floating "Ask the assistant" button on customer/visitor pages (staff never see it here). */
export function ChatButton() {
  const config = getConfig()
  const { status, role } = useAuth()
  if (!config.chatPath || role === 'owner' || role === 'cashier') return null
  return <ChatWidget mode="customer" limit={config.chatDailyLimit ?? 50} canChat={status === 'signedIn' && role === 'customer'} />
}

/** The owner's assistant (owner pages only): questions about their own restaurant's orders and sales.
 *  Cashiers never get one. */
export function OwnerChatButton() {
  const config = getConfig()
  const { status, role, restaurantId } = useAuth()
  if (!config.chatPath || role !== 'owner' || !restaurantId) return null
  return <ChatWidget mode="owner" limit={config.chatDailyLimit ?? 50} canChat={status === 'signedIn'} />
}

function ChatWidget({ mode, limit, canChat }: { mode: ChatMode; limit: number; canChat: boolean }) {
  const [open, setOpen] = useState(false)
  const chat = useChat(mode)
  const { count } = useCart()
  const { pathname } = useLocation()
  const { t } = useLanguage()
  const cartBarShown = mode === 'customer' && count > 0 && pathname !== '/cart' // keep the button above the "View cart" bar

  return (
    <>
      <button
        type="button"
        className={`btn btn-circle btn-primary btn-lg fixed end-4 z-40 shadow-lg ${cartBarShown ? 'bottom-24' : 'bottom-4'}`}
        aria-label={t('chat.open')}
        title={t('chat.open')}
        onClick={() => {
          setOpen(true)
          if (canChat) void chat.loadQuota()
        }}
      >
        <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path
            d="M4 5h16v10H9l-5 4V5z"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <path d="M8 9h8M8 12h5" strokeLinecap="round" />
        </svg>
      </button>
      <ChatPanel
        open={open}
        onClose={() => setOpen(false)}
        mode={mode}
        canChat={canChat}
        state={chat.state}
        limit={limit}
        onSend={(text) => void chat.send(text)}
        onNew={chat.reset}
        onDraftAdded={chat.markAdded}
      />
    </>
  )
}
