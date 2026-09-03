import { Square } from 'lucide-react'
import { useLang } from '../i18n'
import type { Task } from '../types'
import { ProgressBar, Spinner, TaskStatusBadge } from './ui'

export default function TaskBar({
  task,
  onCancel,
  cancelling,
}: {
  task: Task
  onCancel: () => void
  cancelling: boolean
}) {
  const { t } = useLang()
  const pct = Math.round(task.progress * 100)
  const queued = task.status === 'queued'
  return (
    <div className="card mb-6 border-accent/30 bg-[linear-gradient(90deg,rgb(124_108_255/0.10),transparent_60%)] p-4 animate-fade-in">
      <div className="flex flex-wrap items-center gap-3">
        <Spinner size={16} className="text-accent" />
        <span className="text-sm font-medium">{t(`task_type_${task.type}` as const)}</span>
        <TaskStatusBadge status={task.status} />
        <span className="min-w-0 flex-1 truncate text-sm text-muted">{task.message}</span>
        <span className="text-sm font-semibold tabular-nums">{queued ? '' : `${pct}%`}</span>
        <button type="button" className="btn-secondary btn-sm" onClick={onCancel} disabled={cancelling}>
          {cancelling ? <Spinner size={12} /> : <Square size={12} />}
          {cancelling ? t('task_cancelling') : t('task_cancel')}
        </button>
      </div>
      <ProgressBar value={task.progress} indeterminate={queued} className="mt-3" />
    </div>
  )
}
