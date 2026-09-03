import { useEffect, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { useLang } from '../i18n'
import { Spinner } from './ui'
import { cx } from '../utils'

interface ConfirmDialogProps {
  open: boolean
  title: ReactNode
  message?: ReactNode
  confirmLabel?: ReactNode
  danger?: boolean
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const { t } = useLang()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, busy, onCancel])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-40 grid place-items-center bg-black/60 p-4 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel()
      }}
    >
      <div role="dialog" aria-modal="true" className="card w-full max-w-md p-5 animate-fade-in">
        <div className="flex items-start gap-3">
          <span
            className={cx(
              'grid h-9 w-9 shrink-0 place-items-center rounded-lg',
              danger ? 'bg-danger/15 text-danger' : 'bg-accent/15 text-accent',
            )}
          >
            <AlertTriangle size={18} />
          </span>
          <div className="min-w-0">
            <h3 className="text-base font-semibold">{title}</h3>
            {message && <p className="mt-1 text-sm leading-relaxed text-muted">{message}</p>}
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={busy}>
            {t('cancel')}
          </button>
          <button
            type="button"
            className={danger ? 'btn-danger' : 'btn-primary'}
            onClick={onConfirm}
            disabled={busy}
            autoFocus
          >
            {busy && <Spinner size={14} />}
            {confirmLabel ?? t('confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
