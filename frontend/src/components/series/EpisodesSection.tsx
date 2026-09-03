import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, ExternalLink, Film, FolderPlus, ListTree, Play } from 'lucide-react'
import { errorMessage, updateEpisode } from '../../api'
import { useLang } from '../../i18n'
import type { Episode, EpisodePatch, EpisodeStatus, Project } from '../../types'
import { cx } from '../../utils'
import { useToast } from '../Toast'
import { ProgressBar, SectionCard, Spinner } from '../ui'

const statusStyle: Record<EpisodeStatus, string> = {
  planned: 'border-border-strong bg-panel-2 text-muted',
  draft: 'border-border-strong bg-panel-2 text-muted',
  scripted: 'border-sky-400/30 bg-sky-400/10 text-sky-300',
  assets_ready: 'border-amber-400/30 bg-amber-400/10 text-amber-300',
  rendered: 'border-success/30 bg-success/10 text-success',
  failed: 'border-danger/30 bg-danger/10 text-danger',
}

export function EpisodeStatusBadge({ status }: { status: EpisodeStatus }) {
  const { t } = useLang()
  return (
    <span className={cx('chip', statusStyle[status] ?? statusStyle.planned)}>
      {t(`episode_status_${status}` as const)}
    </span>
  )
}

function useDraft(serverValue: string) {
  const [value, setValue] = useState(serverValue)
  const focused = useRef(false)
  useEffect(() => {
    if (!focused.current) setValue(serverValue)
  }, [serverValue])
  return { value, setValue, focused }
}

export interface EpisodeActions {
  generate: (index: number) => Promise<void>
  create: (index: number) => Promise<void>
}

function EpisodeRow({
  ep,
  projectId,
  aspect,
  onProject,
  actions,
}: {
  ep: Episode
  projectId: string
  aspect: string
  onProject: (p: Project) => void
  actions: EpisodeActions
}) {
  const { t } = useLang()
  const toast = useToast()
  const title = useDraft(ep.title)
  const summary = useDraft(ep.summary)
  const [working, setWorking] = useState<'generate' | 'create' | null>(null)

  const commit = async (field: keyof EpisodePatch) => {
    const draft = field === 'title' ? title : summary
    draft.focused.current = false
    if (draft.value === ep[field]) return
    try {
      onProject(await updateEpisode(projectId, ep.index, { [field]: draft.value }))
      toast.success(t('episode_saved'))
    } catch (e) {
      toast.error(errorMessage(e))
      draft.setValue(ep[field])
    }
  }

  const run = async (kind: 'generate' | 'create', fn: () => Promise<void>) => {
    setWorking(kind)
    try {
      await fn()
    } finally {
      setWorking(null)
    }
  }

  const taskActive = ep.task_status !== null
  const portrait = aspect === '9:16'

  return (
    <li className="card flex flex-col gap-3 p-4 sm:flex-row">
      <div className="flex shrink-0 gap-3 sm:flex-col sm:items-center">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent/15 text-sm font-semibold text-accent tabular-nums">
          {ep.index}
        </span>
        <div
          className={cx('overflow-hidden rounded-lg border border-border bg-bg-elev', portrait ? 'h-24 w-14' : 'h-14 w-24')}
        >
          {ep.thumbnail_url ? (
            <img src={ep.thumbnail_url} alt="" className="h-full w-full object-cover" loading="lazy" />
          ) : (
            <div className="grid h-full w-full place-items-center text-faint">
              <Film size={16} strokeWidth={1.5} />
            </div>
          )}
        </div>
      </div>

      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="input min-w-0 flex-1 font-semibold"
            placeholder={t('episode_title_placeholder')}
            value={title.value}
            onFocus={() => (title.focused.current = true)}
            onChange={(e) => title.setValue(e.target.value)}
            onBlur={() => void commit('title')}
          />
          <EpisodeStatusBadge status={ep.status} />
          <span className="chip border-border-strong bg-panel-2 text-muted tabular-nums">
            {t('source_chars', { n: ep.chars.toLocaleString() })}
          </span>
          {ep.project_id && (
            <span className="chip border-border-strong bg-panel-2 text-muted tabular-nums">
              {t('scene_count', { n: ep.scene_count })}
            </span>
          )}
        </div>
        <textarea
          className="input min-h-14"
          rows={2}
          placeholder={t('episode_summary_placeholder')}
          value={summary.value}
          onFocus={() => (summary.focused.current = true)}
          onChange={(e) => summary.setValue(e.target.value)}
          onBlur={() => void commit('summary')}
        />
        {taskActive && (
          <div className="space-y-1">
            <ProgressBar value={ep.progress ?? 0} indeterminate={ep.task_status === 'queued'} />
            <div className="flex items-center justify-between gap-2 text-[11px] text-muted">
              <span className="truncate">{ep.task_message || t(`task_${ep.task_status ?? 'queued'}` as const)}</span>
              <span className="shrink-0 tabular-nums">{Math.round((ep.progress ?? 0) * 100)}%</span>
            </div>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <button
            type="button"
            className="btn-primary btn-sm"
            disabled={taskActive || working !== null}
            onClick={() => void run('generate', () => actions.generate(ep.index))}
          >
            {taskActive || working === 'generate' ? <Spinner size={12} /> : <Play size={12} />}
            {t('generate')}
          </button>
          {ep.project_id ? (
            <Link to={`/projects/${ep.project_id}`} className="btn-secondary btn-sm">
              <ExternalLink size={12} />
              {t('open_studio')}
            </Link>
          ) : (
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={taskActive || working !== null}
              onClick={() => void run('create', () => actions.create(ep.index))}
            >
              {working === 'create' ? <Spinner size={12} /> : <FolderPlus size={12} />}
              {t('create_episode')}
            </button>
          )}
          {ep.final_video_url && (
            <a href={ep.final_video_url} download className="btn-ghost btn-sm">
              <Download size={12} />
              {t('download')}
            </a>
          )}
        </div>
      </div>
    </li>
  )
}

export default function EpisodesSection({
  project,
  onProject,
  actions,
}: {
  project: Project
  onProject: (p: Project) => void
  actions: EpisodeActions
}) {
  const { t } = useLang()
  return (
    <SectionCard title={t('section_episodes')} description={t('episode_count', { n: project.episodes.length })}>
      {project.episodes.length === 0 ? (
        <div className="flex flex-col items-center px-6 py-10 text-center">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-accent/15 text-accent">
            <ListTree size={22} />
          </span>
          <h3 className="mt-3 font-semibold">{t('episodes_empty')}</h3>
          <p className="mt-1 max-w-sm text-sm text-muted">{t('episodes_empty_hint')}</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {project.episodes.map((ep) => (
            <EpisodeRow
              key={ep.index}
              ep={ep}
              projectId={project.id}
              aspect={project.aspect_ratio}
              onProject={onProject}
              actions={actions}
            />
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
