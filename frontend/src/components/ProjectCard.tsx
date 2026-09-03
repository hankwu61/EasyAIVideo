import { Link } from 'react-router-dom'
import { BookOpen, Clock, Film, Layers, Trash2 } from 'lucide-react'
import { useLang } from '../i18n'
import type { ProjectSummary } from '../types'
import { cx, timeAgo } from '../utils'
import { ProgressBar, StatusBadge } from './ui'

export default function ProjectCard({
  project,
  onDelete,
}: {
  project: ProjectSummary
  onDelete: (p: ProjectSummary) => void
}) {
  const { t } = useLang()
  const task = project.active_task
  const title = project.title || t('untitled')
  const isSeries = project.kind === 'series'
  const href = isSeries ? `/series/${project.id}` : `/projects/${project.id}`

  return (
    <div className="card group relative flex flex-col overflow-hidden transition hover:border-border-strong">
      <Link to={href} className="block">
        <div className="relative aspect-video w-full overflow-hidden bg-bg-elev">
          {project.thumbnail_url ? (
            <img
              src={project.thumbnail_url}
              alt=""
              loading="lazy"
              className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
            />
          ) : (
            <div className="grid h-full w-full place-items-center bg-[radial-gradient(circle_at_30%_20%,rgb(124_108_255/0.18),transparent_55%)] text-faint">
              {isSeries ? <BookOpen size={30} strokeWidth={1.25} /> : <Film size={30} strokeWidth={1.25} />}
            </div>
          )}
          <span
            className={cx(
              'chip absolute top-2 left-2 backdrop-blur',
              isSeries ? 'border-accent/40 bg-accent/30 text-white' : 'border-white/10 bg-black/40 text-white/80',
            )}
          >
            {isSeries && <BookOpen size={10} />}
            {t(isSeries ? 'kind_series' : project.kind === 'episode' ? 'kind_episode' : 'kind_single')}
          </span>
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-black/70 to-transparent px-3 pt-8 pb-2">
            <StatusBadge status={project.status} className="backdrop-blur" />
            <span className="chip border-white/10 bg-black/40 text-white/80 backdrop-blur">{project.aspect_ratio}</span>
          </div>
        </div>
      </Link>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <Link to={href} className="line-clamp-2 text-[15px] font-semibold leading-snug hover:text-accent">
          {title}
        </Link>
        <div className="mt-auto flex items-center gap-3 text-xs text-muted">
          <span className="inline-flex items-center gap-1">
            {isSeries ? <BookOpen size={12} /> : <Layers size={12} />}
            {isSeries ? t('episode_count', { n: project.episode_count }) : t('scene_count', { n: project.scene_count })}
          </span>
          <span className="inline-flex items-center gap-1" title={project.updated_at}>
            <Clock size={12} />
            {timeAgo(project.updated_at)}
          </span>
        </div>

        {task && (
          <div className="mt-1 space-y-1.5">
            <ProgressBar value={task.progress} indeterminate={task.status === 'queued'} />
            <div className="flex items-center justify-between gap-2 text-[11px] text-muted">
              <span className="truncate">{task.message || t(`task_${task.status}` as const)}</span>
              <span className="shrink-0 tabular-nums">{Math.round(task.progress * 100)}%</span>
            </div>
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={(e) => {
          e.preventDefault()
          onDelete(project)
        }}
        aria-label={t('delete')}
        title={t('delete')}
        className={cx(
          'absolute top-2 right-2 grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-black/50 text-white/70 backdrop-blur transition',
          'opacity-0 hover:border-danger/50 hover:bg-danger/30 hover:text-white focus-visible:opacity-100 group-hover:opacity-100',
        )}
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
