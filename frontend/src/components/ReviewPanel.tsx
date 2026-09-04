import { useState } from 'react'
import { AlertTriangle, ArrowDownToLine, ExternalLink, RefreshCw, ScanEye, Star, Trash2, Wand2 } from 'lucide-react'
import { clearReview, errorMessage } from '../api'
import { useLang } from '../i18n'
import type { Project, SceneReview } from '../types'
import { cx, timeAgo } from '../utils'
import ConfirmDialog from './ConfirmDialog'
import { AI_VIDEO_MOTION } from './ProjectSettingsFields'
import type { SceneActions } from './SceneCard'
import { useToast } from './Toast'
import { Spinner } from './ui'

interface ReviewPanelProps {
  project: Project
  busy: boolean
  actions: SceneActions
  onReview: () => void
  onProject: (p: Project) => void
}

const scoreColor = (score: number) => (score <= 2 ? 'text-danger' : score < 4 ? 'text-warning' : 'text-success')
const scoreDot = (score: number) => (score <= 2 ? 'bg-danger' : score < 4 ? 'bg-warning' : 'bg-success')

function ScoreDots({ score }: { score: number }) {
  const { t } = useLang()
  const s = Math.max(0, Math.min(5, Math.round(score)))
  return (
    <span className="inline-flex items-center gap-0.5" title={t('review_score_label', { s })}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} className={cx('h-2 w-2 rounded-full', i < s ? scoreDot(s) : 'bg-border-strong')} />
      ))}
    </span>
  )
}

/** Scroll the matching scene card into view. */
function jumpToScene(sceneId: string) {
  document.getElementById('scene-' + sceneId)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

export default function ReviewPanel({ project, busy, actions, onReview, onProject }: ReviewPanelProps) {
  const { t } = useLang()
  const toast = useToast()
  const review = project.review
  const [confirmClear, setConfirmClear] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [applying, setApplying] = useState<string | null>(null)

  if (!review) return null

  const outdated = !project.final_video_url || !project.final_video_url.includes(review.video_path)
  const sceneIds = new Set(project.scenes.map((s) => s.id))
  const scenes = [...review.scenes].sort((a, b) => a.score - b.score)
  const aiVideo = project.motion === AI_VIDEO_MOTION

  const doClear = async () => {
    setClearing(true)
    try {
      onProject(await clearReview(project.id))
      setConfirmClear(false)
      toast.success(t('review_cleared'))
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setClearing(false)
    }
  }

  const apply = async (sr: SceneReview, regenerate: boolean) => {
    setApplying(sr.scene_id)
    try {
      const ok = await actions.patch(sr.scene_id, { image_prompt: sr.suggested_image_prompt })
      if (!ok) return
      toast.success(t('review_prompt_applied'))
      if (regenerate) await actions.regenerate(sr.scene_id, aiVideo ? ['image', 'video'] : ['image'])
    } finally {
      setApplying(null)
    }
  }

  return (
    <section className="card overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <ScanEye size={15} className="text-accent" />
        <h2 className="text-sm font-semibold">{t('review_results')}</h2>
        <span
          className={cx('inline-flex items-center gap-1 text-sm font-semibold tabular-nums', scoreColor(review.average_score))}
        >
          <Star size={13} className="fill-current" />
          {review.average_score.toFixed(1)} / 5
        </span>
        <span
          className={cx(
            'chip',
            review.issue_count > 0 ? 'border-warning/40 bg-warning/10 text-warning' : 'border-success/30 bg-success/10 text-success',
          )}
        >
          {review.issue_count > 0 ? t('review_issue_count', { n: review.issue_count }) : t('review_no_issues')}
        </span>
        <span className="ml-auto flex items-center gap-1">
          <button
            type="button"
            className="btn-ghost btn-sm"
            disabled={busy || !project.final_video_url}
            onClick={onReview}
            title={project.final_video_url ? t('review_rerun') : t('review_need_render')}
          >
            <RefreshCw size={13} />
            {t('review_rerun')}
          </button>
          <button
            type="button"
            className="btn-ghost btn-sm text-danger"
            disabled={busy}
            onClick={() => setConfirmClear(true)}
            title={t('review_clear')}
          >
            <Trash2 size={13} />
            {t('review_clear')}
          </button>
        </span>
      </div>

      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-x-2 text-[11px] text-faint">
          <span className="font-mono">{review.model}</span>
          <span>·</span>
          <span>{timeAgo(review.created_at)}</span>
        </div>

        {outdated && (
          <p className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            {t('review_outdated')}
          </p>
        )}

        {review.summary && <p className="text-sm leading-relaxed">{review.summary}</p>}

        <ul className="space-y-3">
          {scenes.map((sr) => {
            const exists = sceneIds.has(sr.scene_id)
            const canApply = exists && !busy && applying === null
            const working = applying === sr.scene_id
            return (
              <li key={sr.scene_id} className="rounded-lg border border-border bg-bg-elev p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="grid h-6 min-w-6 place-items-center rounded-md bg-panel-2 px-1.5 text-[11px] font-semibold"
                    title={t('scene_n', { n: sr.index + 1 })}
                  >
                    {sr.index + 1}
                  </span>
                  <ScoreDots score={sr.score} />
                  <span
                    className={cx(
                      'chip',
                      sr.match ? 'border-success/30 bg-success/10 text-success' : 'border-danger/30 bg-danger/10 text-danger',
                    )}
                  >
                    {sr.match ? t('review_match') : t('review_mismatch')}
                  </span>
                  {exists && (
                    <button
                      type="button"
                      className="ml-auto inline-flex items-center gap-1 text-[11px] text-muted hover:text-text"
                      onClick={() => jumpToScene(sr.scene_id)}
                    >
                      <ArrowDownToLine size={11} />
                      {t('review_jump_to_scene')}
                    </button>
                  )}
                </div>

                {sr.frame_urls.length > 0 && (
                  <div className="mt-2 flex gap-1.5 overflow-x-auto">
                    {sr.frame_urls.map((u) => (
                      <a
                        key={u}
                        href={u}
                        target="_blank"
                        rel="noreferrer"
                        className="group relative shrink-0 overflow-hidden rounded-md border border-border"
                        title={t('open_image')}
                      >
                        <img src={u} alt="" loading="lazy" className="h-16 w-auto object-cover" />
                        <span className="absolute inset-0 grid place-items-center bg-black/50 opacity-0 transition group-hover:opacity-100">
                          <ExternalLink size={12} className="text-white" />
                        </span>
                      </a>
                    ))}
                  </div>
                )}

                {sr.error && (
                  <p className="mt-2 rounded-md border border-danger/30 bg-danger/10 px-2.5 py-1.5 text-xs text-danger break-words">
                    {sr.error}
                  </p>
                )}

                {sr.issues.length > 0 && (
                  <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs">
                    {sr.issues.map((issue, i) => (
                      <li key={i}>{issue}</li>
                    ))}
                  </ul>
                )}

                {sr.note && <p className="mt-2 text-xs leading-relaxed text-muted">{sr.note}</p>}

                {sr.suggested_image_prompt && (
                  <div className="mt-2 space-y-2">
                    <div className="text-[11px] font-medium tracking-wide text-muted">{t('review_suggested_prompt')}</div>
                    <pre className="rounded-md border border-border bg-panel-2 px-2.5 py-2 font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap">
                      {sr.suggested_image_prompt}
                    </pre>
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        disabled={!canApply}
                        onClick={() => void apply(sr, false)}
                      >
                        {working ? <Spinner size={12} /> : <Wand2 size={12} />}
                        {t('review_apply_prompt')}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        disabled={!canApply}
                        onClick={() => void apply(sr, true)}
                      >
                        <RefreshCw size={12} />
                        {t('review_apply_regen')}
                      </button>
                    </div>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      </div>

      <ConfirmDialog
        open={confirmClear}
        danger
        busy={clearing}
        title={t('review_clear')}
        message={t('review_clear_confirm')}
        confirmLabel={t('review_clear')}
        onCancel={() => !clearing && setConfirmClear(false)}
        onConfirm={() => void doClear()}
      />
    </section>
  )
}
