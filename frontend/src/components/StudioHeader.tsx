import type { MutableRefObject } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Clapperboard, FileText, Images, ScanEye, Sparkles } from 'lucide-react'
import { useLang } from '../i18n'
import type { Project } from '../types'
import { Spinner, StatusBadge } from './ui'

interface StudioHeaderProps {
  project: Project
  busy: boolean
  titleDraft: string
  titleFocused: MutableRefObject<boolean>
  onTitleChange: (v: string) => void
  onTitleCommit: () => void
  onScript: () => void
  onAssets: () => void
  onRender: () => void
  onReview: () => void
  onAll: () => void
}

export function BackLink({ to = '/', label }: { to?: string; label?: string }) {
  const { t } = useLang()
  return (
    <Link to={to} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text">
      <ArrowLeft size={15} />
      {label ?? t('back_to_projects')}
    </Link>
  )
}

export default function StudioHeader({
  project,
  busy,
  titleDraft,
  titleFocused,
  onTitleChange,
  onTitleCommit,
  onScript,
  onAssets,
  onRender,
  onReview,
  onAll,
}: StudioHeaderProps) {
  const { t } = useLang()
  const hasScenes = project.scenes.length > 0
  const hasVideo = !!project.final_video_url
  const isEpisode = project.kind === 'episode' && !!project.parent_id

  return (
    <div className="mb-4">
      {isEpisode ? <BackLink to={`/series/${project.parent_id}`} label={t('back_to_series')} /> : <BackLink />}
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <input
          className="min-w-0 flex-1 rounded-lg border border-transparent bg-transparent px-2 py-1 text-2xl font-semibold tracking-tight outline-none transition hover:border-border focus:border-accent focus:bg-bg-elev"
          value={titleDraft}
          placeholder={t('untitled')}
          onFocus={() => (titleFocused.current = true)}
          onChange={(e) => onTitleChange(e.target.value)}
          onBlur={onTitleCommit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
          }}
        />
        {isEpisode && project.episode_index !== null && (
          <span className="chip border-accent/40 bg-accent/15 text-[#c4b5fd]">
            {t('episode_chip', { n: project.episode_index })}
          </span>
        )}
        {project.content_mode === 'drama' && (
          <span className="chip border-border-strong bg-panel-2 text-muted">{t('content_mode_drama')}</span>
        )}
        <StatusBadge status={project.status} />
        <span className="chip border-border-strong bg-panel-2 text-muted tabular-nums">
          {project.aspect_ratio} · {t('video_size_chip', { w: project.width, h: project.height })}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" className="btn-secondary" disabled={busy} onClick={onScript}>
          <FileText size={15} />
          {t('gen_script')}
        </button>
        <button type="button" className="btn-secondary" disabled={busy || !hasScenes} onClick={onAssets}>
          <Images size={15} />
          {t('gen_assets')}
        </button>
        <button type="button" className="btn-secondary" disabled={busy || !hasScenes} onClick={onRender}>
          <Clapperboard size={15} />
          {t('render')}
        </button>
        <span title={hasVideo ? undefined : t('review_need_render')}>
          <button type="button" className="btn-secondary" disabled={busy || !hasVideo} onClick={onReview}>
            <ScanEye size={15} />
            {t('review_button')}
          </button>
        </span>
        <button type="button" className="btn-primary" disabled={busy} onClick={onAll}>
          {busy ? <Spinner size={15} /> : <Sparkles size={15} />}
          {t('gen_all')}
        </button>
      </div>
    </div>
  )
}
