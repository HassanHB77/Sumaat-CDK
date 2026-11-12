import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Navigate } from 'react-router'
import { ApiError } from '../api/client'
import { createCashier, listCashiers, resetCashierPassword, setCashierEnabled, type CashierInput } from '../api/endpoints'
import type { Cashier } from '../api/types'
import { useStaff } from '../counter/StaffLayout'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { EmptyState, ErrorState, LoadingState } from '../components/States'
import { useToast } from '../components/Toast'
import { useLanguage } from '../i18n/LanguageContext'
import { usePageTitle } from '../lib/usePageTitle'
import { AddCashierDialog, ResetPasswordDialog } from './CashierDialogs'

type Credentials = { email: string; password: string }

/** /owner/cashiers: add, list, disable/enable, reset password. */
export function CashiersPage() {
  const { restaurantId } = useStaff()
  const { t } = useLanguage()
  const toast = useToast()
  const queryClient = useQueryClient()
  const key = ['cashiers', restaurantId] as const
  usePageTitle(t('page.ownerCashiers'))

  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [disabling, setDisabling] = useState<Cashier | null>(null)
  const [resetting, setResetting] = useState<Cashier | null>(null)
  const [shown, setShown] = useState<Credentials | null>(null) // shown once, never stored

  const cashiers = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => listCashiers(restaurantId!, signal),
    enabled: Boolean(restaurantId),
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: key })
  const errorText = (err: unknown) => (err instanceof ApiError ? err.message : t('auth.err.generic'))

  const create = useMutation({
    mutationFn: (input: CashierInput) => createCashier(restaurantId!, input),
    onMutate: () => setAddError(null),
    onSuccess: (_c, input) => {
      setAdding(false)
      setShown({ email: input.email, password: input.password })
      refresh()
    },
    onError: (err) =>
      setAddError(err instanceof ApiError && err.status === 409 ? t('cashiers.emailTaken') : errorText(err)),
  })

  const toggle = useMutation({
    mutationFn: ({ c, enable }: { c: Cashier; enable: boolean }) => setCashierEnabled(restaurantId!, c.sub, enable),
    onSuccess: (c) => {
      setDisabling(null)
      toast.show(t(c.status === 'active' ? 'cashiers.enabledToast' : 'cashiers.disabledToast', { name: c.name }), 'success')
      refresh()
    },
    onError: (err) => toast.show(errorText(err), 'error', 6000),
  })

  const reset = useMutation({
    mutationFn: ({ c, password }: { c: Cashier; password: string }) => resetCashierPassword(restaurantId!, c.sub, password),
    onSuccess: (_r, { c, password }) => {
      setResetting(null)
      setShown({ email: c.email, password })
    },
    onError: (err) => toast.show(errorText(err), 'error', 6000),
  })

  if (!restaurantId) return <Navigate to="/owner/setup" replace />
  const busy = create.isPending || toggle.isPending || reset.isPending

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t('page.ownerCashiers')}</h1>
        <button type="button" className="btn btn-primary" onClick={() => setAdding(true)} disabled={busy}>
          + {t('cashiers.add')}
        </button>
      </div>

      {shown && <CredentialsCard credentials={shown} onDone={() => setShown(null)} />}

      {cashiers.isPending ? (
        <LoadingState rows={2} />
      ) : cashiers.isError ? (
        <ErrorState onRetry={() => cashiers.refetch()} />
      ) : cashiers.data.length === 0 ? (
        <EmptyState>{t('cashiers.empty')}</EmptyState>
      ) : (
        <ul className="flex flex-col gap-2">
          {cashiers.data.map((c) => (
            <li key={c.sub} className={`card bg-base-100 shadow-sm ${c.status === 'disabled' ? 'opacity-70' : ''}`}>
              <div className="card-body flex-row flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium">
                    {c.name}
                    <span className={`badge badge-sm ${c.status === 'active' ? 'badge-success' : 'badge-ghost'}`}>
                      {t(c.status === 'active' ? 'cashiers.active' : 'cashiers.disabled')}
                    </span>
                  </p>
                  <p className="truncate text-sm text-muted" dir="ltr">
                    {c.email} · {c.phone}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => setResetting(c)} disabled={busy}>
                    {t('cashiers.reset')}
                  </button>
                  {c.status === 'active' ? (
                    <button type="button" className="btn btn-sm btn-outline btn-error" onClick={() => setDisabling(c)} disabled={busy}>
                      {t('cashiers.disable')}
                    </button>
                  ) : (
                    <button type="button" className="btn btn-sm btn-success" onClick={() => toggle.mutate({ c, enable: true })} disabled={busy}>
                      {t('cashiers.enable')}
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <AddCashierDialog
        open={adding}
        busy={create.isPending}
        serverError={addError}
        onCancel={() => {
          setAdding(false)
          setAddError(null)
        }}
        onSave={(input) => create.mutate(input)}
      />
      <ResetPasswordDialog
        name={resetting?.name ?? null}
        busy={reset.isPending}
        onCancel={() => setResetting(null)}
        onSave={(password) => resetting && reset.mutate({ c: resetting, password })}
      />
      <ConfirmDialog
        open={disabling !== null}
        title={t('cashiers.disableTitle', { name: disabling?.name ?? '' })}
        confirmLabel={t('cashiers.disable')}
        cancelLabel={t('common.cancel')}
        danger
        busy={toggle.isPending}
        onCancel={() => setDisabling(null)}
        onConfirm={() => disabling && toggle.mutate({ c: disabling, enable: false })}
      >
        {t('cashiers.disableBody')}
      </ConfirmDialog>
    </div>
  )
}

/** Email + password to hand to the cashier, shown once with Copy buttons. */
function CredentialsCard({ credentials, onDone }: { credentials: Credentials; onDone: () => void }) {
  const { t } = useLanguage()
  const [copied, setCopied] = useState<string | null>(null)
  const loginUrl = `${window.location.origin}/login`

  async function copy(label: string, text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(label)
      setTimeout(() => setCopied(null), 1500)
    } catch {
      /* clipboard blocked: the text is visible and selectable anyway */
    }
  }

  const row = (label: string, value: string) => (
    <div className="flex items-center justify-between gap-2 rounded-box bg-base-200 px-3 py-2">
      <div className="min-w-0">
        <p className="text-xs text-muted">{label}</p>
        <p className="truncate font-mono" dir="ltr">
          {value}
        </p>
      </div>
      <button type="button" className="btn btn-sm" onClick={() => copy(label, value)}>
        {copied === label ? t('cashiers.copied') : t('cashiers.copy')}
      </button>
    </div>
  )

  return (
    <div role="status" className="card border-2 border-success bg-base-100 shadow">
      <div className="card-body gap-2">
        <h2 className="card-title">{t('cashiers.giveTitle')}</h2>
        <p className="text-sm text-muted">{t('cashiers.giveBody')}</p>
        {row(t('cashiers.loginAt'), loginUrl)}
        {row(t('auth.email'), credentials.email)}
        {row(t('auth.password'), credentials.password)}
        <div className="card-actions justify-end">
          <button type="button" className="btn btn-primary btn-sm" onClick={onDone}>
            {t('cashiers.done')}
          </button>
        </div>
      </div>
    </div>
  )
}
