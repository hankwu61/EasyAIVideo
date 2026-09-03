import type { MutableRefObject } from 'react'
import { BookOpen, ListTree, ScanSearch, Sparkles } from 'lucide-react'
import { useLang } from '../../i18n'
import type { Project } from '../../types'
import { BackLink } from '../StudioHeader'
import { Spinner } from '../ui'

interface SeriesHeaderProps {
  project: Project
  busy: boolean
  generatingAll: boolean
  titleDraft: string
  titleFocused: MutableRefObject<boolean>
  onTitleChange: (v: string) => void
  onTitleCommit: () => void
  onAnalyze: () => void
  onPlan: () => void
  onGenerateAll: () => void
}

export default function SeriesHeader({
  project,
  busy,
  generatingAll,
  titleDraft,
  titleFocused,
  onTitleChange,
  onTitleCommit,
  onAnalyze,
  onPlan,
  onGenerateAll,
}: SeriesHeaderProps) {
  const { t } = useLang()
  const hasEpisodes = project.episodes.length > 0

  return (
    <div className="mb-6">
      <BackLink />
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
        <span className="chip border-accent/40 bg-accent/15 text-[#c4b5fd]">
          <BookOpen size={11} />
          {t('kind_series_label')}
        </span>
        <span className="chip border-border-strong bg-panel-2 text-muted">
          {t(`content_mode_${project.content_mode}` as const)}
        </span>
        <span className="chip border-border-strong bg-panel-2 text-muted tabular-nums">{project.aspect_ratio}</span>
        <span className="chip border-border-strong bg-panel-2 text-muted tabular-nums">
          {t('source_chars', { n: project.source_chars.toLocaleString() })}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" className="btn-secondary" disabled={busy || project.source_chars === 0} onClick={onAnalyze}>
          <ScanSearch size={15} />
          {t('analyze')}
        </button>
        <button type="button" className="btn-secondary" disabled={busy || project.source_chars === 0} onClick={onPlan}>
          <ListTree size={15} />
          {t('plan_episodes')}
        </button>
        <button type="button" className="btn-primary" disabled={!hasEpisodes || generatingAll} onClick={onGenerateAll}>
          {generatingAll ? <Spinner size={15} /> : <Sparkles size={15} />}
          {t('generate_all_episodes')}
        </button>
      </div>
    </div>
  )
}
