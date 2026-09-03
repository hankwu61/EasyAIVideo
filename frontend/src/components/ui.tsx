import type { ReactNode } from 'react'
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react'
import { useLang } from '../i18n'
import type { ProjectStatus, SceneStatus, TaskStatus } from '../types'
import { cx } from '../utils'

export function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={cx('animate-spin', className)} />
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('skeleton', className)} />
}

export function ErrorAlert({
  message,
  title,
  onRetry,
  className,
}: {
  message: string
  title?: string
  onRetry?: () => void
  className?: string
}) {
  const { t } = useLang()
  return (
    <div
      role="alert"
      className={cx(
        'flex items-start gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger',
        className,
      )}
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <div className="font-medium">{title}</div>}
        <div className={cx('break-words', title && 'mt-0.5 text-danger/80')}>{message}</div>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-danger btn-sm shrink-0">
          <RefreshCw size={12} />
          {t('retry')}
        </button>
      )}
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Field({
  label,
  hint,
  right,
  children,
  className,
}: {
  label: ReactNode
  hint?: ReactNode
  right?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="text-xs font-medium tracking-wide text-muted">{label}</span>
        {right && <span className="text-xs text-faint tabular-nums">{right}</span>}
      </div>
      {children}
      {hint && <p className="mt-1.5 text-[11px] leading-relaxed text-faint">{hint}</p>}
    </div>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: ReactNode
  disabled?: boolean
}) {
  return (
    <label
      className={cx(
        'flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-border bg-bg-elev px-3 py-2 text-sm select-none',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <span>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          'relative h-5 w-9 shrink-0 rounded-full transition',
          checked ? 'bg-accent' : 'bg-border-strong',
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition',
            checked ? 'left-[18px]' : 'left-0.5',
          )}
        />
      </button>
    </label>
  )
}

export function ProgressBar({
  value,
  indeterminate,
  className,
}: {
  value: number
  indeterminate?: boolean
  className?: string
}) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  return (
    <div className={cx('h-1.5 w-full overflow-hidden rounded-full bg-border', className)}>
      <div
        className={cx('h-full rounded-full transition-[width] duration-500', indeterminate ? 'progress-shimmer' : 'bg-accent')}
        style={{ width: indeterminate ? '100%' : `${pct}%` }}
      />
    </div>
  )
}

const projectStatusStyle: Record<ProjectStatus, string> = {
  draft: 'border-border-strong bg-panel-2 text-muted',
  scripted: 'border-sky-400/30 bg-sky-400/10 text-sky-300',
  assets_ready: 'border-amber-400/30 bg-amber-400/10 text-amber-300',
  rendered: 'border-success/30 bg-success/10 text-success',
}

export function StatusBadge({ status, className }: { status: ProjectStatus; className?: string }) {
  const { t } = useLang()
  return (
    <span className={cx('chip', projectStatusStyle[status] ?? projectStatusStyle.draft, className)}>
      {t(`status_${status}` as const)}
    </span>
  )
}

const taskStatusStyle: Record<TaskStatus, string> = {
  queued: 'border-border-strong bg-panel-2 text-muted',
  running: 'border-accent/40 bg-accent/15 text-[#c4b5fd]',
  succeeded: 'border-success/30 bg-success/10 text-success',
  failed: 'border-danger/30 bg-danger/10 text-danger',
  cancelled: 'border-border-strong bg-panel-2 text-muted',
}

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const { t } = useLang()
  return <span className={cx('chip', taskStatusStyle[status])}>{t(`task_${status}` as const)}</span>
}

const sceneDotStyle: Record<SceneStatus, string> = {
  pending: 'bg-faint',
  partial: 'bg-warning shadow-[0_0_6px_rgb(251_191_36/0.6)]',
  ready: 'bg-success shadow-[0_0_6px_rgb(52_211_153/0.6)]',
  failed: 'bg-danger shadow-[0_0_6px_rgb(248_113_113/0.6)]',
}

export function SceneStatusDot({ status, error }: { status: SceneStatus; error?: string | null }) {
  const { t } = useLang()
  const label = t(`scene_status_${status}` as const)
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[11px] text-muted"
      title={status === 'failed' && error ? `${label}: ${error}` : label}
    >
      <span className={cx('h-2 w-2 rounded-full', sceneDotStyle[status])} />
      <span className={cx(status === 'failed' && 'text-danger')}>{label}</span>
    </span>
  )
}

export function StaleChip({ label }: { label?: string }) {
  const { t } = useLang()
  return <span className="chip border-warning/40 bg-warning/10 text-warning">{label ?? t('stale')}</span>
}

export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cx('card p-5', className)}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}
