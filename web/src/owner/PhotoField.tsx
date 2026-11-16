import { useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { removeImage } from '../api/endpoints'
import type { MenuItem, Restaurant } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Photo } from '../components/Photo'
import { useToast } from '../components/Toast'
import type { MessageKey } from '../i18n/en'
import { useLanguage } from '../i18n/LanguageContext'
import { PhotoError, uploadPhoto } from '../lib/images'

/**
 * Owner: the restaurant's photo (no itemId) or a dish's photo. Upload / Replace / Delete.
 * The photo is saved on its own (it doesn't wait for the form's Save button); `onChanged` gets the updated
 * restaurant or dish so the page can refresh its data.
 */
export function PhotoField<T extends Restaurant | MenuItem>({
  restaurantId,
  itemId,
  imageUrl,
  hint,
  onChanged,
}: {
  restaurantId: string
  itemId?: string
  imageUrl?: string | null
  hint: string
  onChanged: (updated: T) => void
}) {
  const { t } = useLanguage()
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [current, setCurrent] = useState(imageUrl ?? null)
  const [busy, setBusy] = useState<'upload' | 'delete' | null>(null)
  const [confirm, setConfirm] = useState(false)

  function done(updated: T, message: MessageKey) {
    setCurrent(updated.imageUrl ?? null)
    onChanged(updated)
    toast.show(t(message), 'success')
  }

  async function onPick(file: File | undefined) {
    if (!file) return
    setBusy('upload')
    try {
      done(await uploadPhoto<T>(restaurantId, file, itemId), 'photo.saved')
    } catch (err) {
      const code = err instanceof PhotoError ? err.code : null
      if (code === 'notImage') toast.show(t('photo.err.notImage'), 'error', 6000)
      else if (code === 'tooBig') toast.show(t('photo.err.tooBig'), 'error', 6000)
      else if (err instanceof ApiError && err.status !== 0) toast.show(err.message, 'error', 6000)
      else toast.show(t('photo.err.failed'), 'error', 6000)
    } finally {
      setBusy(null)
      if (input.current) input.current.value = '' // picking the same file again still triggers onChange
    }
  }

  async function onDelete() {
    setBusy('delete')
    try {
      done(await removeImage<T>(restaurantId, itemId), 'photo.deleted')
    } catch {
      toast.show(t('photo.err.failed'), 'error', 6000)
    } finally {
      setBusy(null)
      setConfirm(false)
    }
  }

  return (
    <div className="flex items-center gap-4">
      <Photo
        src={current}
        className="size-24"
        fallback={
          <div className="grid size-24 shrink-0 place-items-center rounded-box border border-dashed border-base-300 bg-base-200 p-2 text-center text-xs text-muted">
            {t('photo.none')}
          </div>
        }
      />
      <div className="flex min-w-0 flex-col gap-2">
        <p className="text-sm text-muted">{hint}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-sm btn-primary" onClick={() => input.current?.click()} disabled={busy !== null}>
            {busy === 'upload' && <span className="loading loading-spinner loading-xs" />}
            {current ? t('photo.replace') : t('photo.upload')}
          </button>
          {current && (
            <button type="button" className="btn btn-sm btn-ghost text-error" onClick={() => setConfirm(true)} disabled={busy !== null}>
              {t('photo.delete')}
            </button>
          )}
        </div>
        <input ref={input} type="file" accept="image/*" className="hidden" onChange={(e) => onPick(e.target.files?.[0])} />
      </div>
      <ConfirmDialog
        open={confirm}
        title={t('photo.deleteTitle')}
        confirmLabel={t('photo.delete')}
        cancelLabel={t('common.cancel')}
        danger
        busy={busy === 'delete'}
        onConfirm={onDelete}
        onCancel={() => setConfirm(false)}
      >
        {t('photo.deleteBody')}
      </ConfirmDialog>
    </div>
  )
}
