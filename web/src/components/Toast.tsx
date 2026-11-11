import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

type ToastKind = 'info' | 'success' | 'error'
type Toast = { id: number; kind: ToastKind; message: string }

type ToastValue = { show: (message: string, kind?: ToastKind, ms?: number) => void }

const ToastContext = createContext<ToastValue | null>(null)

const KIND_CLASS: Record<ToastKind, string> = {
  info: 'alert-info',
  success: 'alert-success',
  error: 'alert-error',
}

/** Small stack of messages at the bottom (DaisyUI `toast`). The Undo toasts of the counter come in M4. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const show = useCallback((message: string, kind: ToastKind = 'info', ms = 4000) => {
    const id = Date.now() + Math.random()
    setToasts((list) => [...list, { id, kind, message }])
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), ms)
  }, [])

  const value = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast toast-center toast-bottom z-50" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} role="status" className={`alert ${KIND_CLASS[t.kind]}`}>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
