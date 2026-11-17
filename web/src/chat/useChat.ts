import { useCallback, useEffect, useReducer, useRef } from 'react'
import { apiFetch } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { getConfig } from '../config/config'
import { useLanguage } from '../i18n/LanguageContext'
import { loadSpot } from '../lib/geo'
import { sendChat } from './chatClient'
import { chatReducer, loadChat, newSessionId, saveChat, type ChatMode } from './chatState'

/** The chat's state and actions. Lives in ChatButton (always mounted on customer pages) so closing the panel or
 *  moving between pages keeps the conversation. */
export function useChat(mode: ChatMode = 'customer') {
  const [state, dispatch] = useReducer(chatReducer, undefined, () => loadChat(Date.now(), mode))
  const stateRef = useRef(state)
  const abortRef = useRef<AbortController | null>(null)
  const { lang } = useLanguage()
  const { status } = useAuth()

  useEffect(() => {
    stateRef.current = state
    saveChat(state, mode)
  }, [state, mode])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    dispatch({ type: 'reset', sessionId: newSessionId(), now: Date.now() })
  }, [])

  // Log out (shared devices): the next person starts with an empty chat.
  const wasSignedIn = useRef(false)
  useEffect(() => {
    if (status === 'signedIn') wasSignedIn.current = true
    if (status === 'signedOut' && wasSignedIn.current) {
      wasSignedIn.current = false
      reset()
    }
  }, [status, reset])

  const loadQuota = useCallback(async () => {
    try {
      const q = await apiFetch<{ left: number; limit: number }>('/me/chat-quota', { auth: true })
      dispatch({ type: 'quotaLoaded', left: q.left })
    } catch {
      /* the count arrives with the next reply anyway */
    }
  }, [])

  const send = useCallback(
    async (text: string) => {
      const message = text.trim()
      const path = getConfig().chatPath
      if (!message || !path || stateRef.current.sending) return
      dispatch({ type: 'send', text: message, now: Date.now() })
      const ctrl = new AbortController()
      abortRef.current = ctrl
      try {
        await sendChat(
          { path, message, sessionId: stateRef.current.sessionId, lang, spot: loadSpot(), signal: ctrl.signal },
          (event) => dispatch({ type: 'event', event }),
        )
      } catch (e) {
        if ((e as Error)?.name !== 'AbortError') dispatch({ type: 'networkError' })
      }
    },
    [lang],
  )

  const markAdded = useCallback((index: number) => dispatch({ type: 'draftAdded', index }), [])

  return { state, send, reset, loadQuota, markAdded }
}
