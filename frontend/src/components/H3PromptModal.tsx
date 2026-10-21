import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Check, Clapperboard, Copy, FileText, Layers, Play, Save, Sparkles, X } from 'lucide-react'
import { generateH3Video, updateH3Segment } from '../api'
import { useLang } from '../i18n'
import type { H3Segment, Project, Task } from '../types'

interface H3PromptModalProps {
  isOpen: boolean
  onClose: () => void
  project: Project
  /** Called with the saved project after a part prompt is edited. */
  onProjectChange?: (project: Project) => void
  /** Studio task starter (shows toasts and starts polling). */
  onStartTask?: (fn: () => Promise<Task>) => void | Promise<void>
  busy?: boolean
}

type Tab = 'segments' | 'prompt' | 'forensics'

const STATUS_STYLE: Record<H3Segment['status'], string> = {
  pending: 'bg-panel-2 text-muted',
  generating: 'bg-accent/20 text-accent animate-pulse',
  done: 'bg-emerald-500/15 text-emerald-400',
  failed: 'bg-danger/15 text-danger',
}

function SegmentCard({
  project,
  seg,
  total,
  busy,
  onProjectChange,
  onStartTask,
}: {
  project: Project
  seg: H3Segment
  total: number
  busy: boolean
  onProjectChange?: (p: Project) => void
  onStartTask?: (fn: () => Promise<Task>) => void | Promise<void>
}) {
  const { t } = useLang()
  const [draft, setDraft] = useState(seg.prompt)
  const [dur, setDur] = useState(seg.request_duration)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDraft(seg.prompt)
    setDur(seg.request_duration)
  }, [seg.prompt, seg.request_duration])

  const dirty = draft !== seg.prompt || dur !== seg.request_duration
  const over = draft.length > 7000

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const p = await updateH3Segment(project.id, seg.index, { prompt: draft, request_duration: dur })
      onProjectChange?.(p)
      setSaved(true)
      setTimeout(() => setSaved(false), 1800)
    } catch (e: any) {
      setError(e?.detail || e?.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(draft)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="rounded-xl border border-border bg-panel p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-text">
          {t('h3_part', { n: seg.index + 1 })} / {total}
        </span>
        <span className="text-xs text-muted">
          {t('h3_source_range', { start: seg.start.toFixed(2), end: seg.end.toFixed(2), dur: seg.duration.toFixed(2) })}
        </span>
        {seg.reason && <span className="rounded bg-panel-2 px-1.5 py-0.5 font-mono text-[10px] text-muted">{seg.reason}</span>}
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLE[seg.status]}`}>
          {t(`h3_status_${seg.status}` as 'h3_status_pending')}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_200px]">
        <div className="space-y-2">
          <textarea
            className={`input h-56 w-full resize-y font-mono text-[11px] leading-relaxed ${over ? 'border-danger' : ''}`}
            value={draft}
            spellCheck={false}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className={over ? 'text-danger font-medium' : 'text-muted'}>{t('h3_chars', { n: draft.length })}</span>
            <label className="flex items-center gap-1 text-muted">
              {t('h3_request_duration')}
              <input
                type="number"
                min={4}
                max={15}
                className="input w-16 py-0.5 text-xs"
                value={dur}
                onChange={(e) => setDur(Math.max(4, Math.min(15, Number(e.target.value) || 4)))}
              />
            </label>
            {dirty && <span className="text-amber-400">{t('h3_unsaved')}</span>}
            <div className="ml-auto flex items-center gap-2">
              <button type="button" onClick={copy} className="btn-secondary flex items-center gap-1 px-2.5 py-1 text-xs">
                {copied ? <Check size={13} /> : <Copy size={13} />}
              </button>
              <button
                type="button"
                disabled={!dirty || saving || over}
                onClick={save}
                className="btn-secondary flex items-center gap-1 px-2.5 py-1 text-xs disabled:opacity-50"
              >
                {saved ? <Check size={13} /> : <Save size={13} />}
                {saved ? t('h3_saved') : t('h3_save_prompt')}
              </button>
              <button
                type="button"
                disabled={busy || dirty || !seg.prompt.trim()}
                onClick={() => onStartTask?.(() => generateH3Video(project.id, { segment_indexes: [seg.index], force: true }))}
                className="btn-primary flex items-center gap-1 px-2.5 py-1 text-xs disabled:opacity-50"
              >
                <Play size={13} />
                {seg.clip_url ? t('h3_regenerate_part') : t('h3_generate_part')}
              </button>
            </div>
          </div>
          {error && <p className="text-xs text-danger">{error}</p>}
          {seg.error && <p className="text-xs text-danger">{seg.error}</p>}
          {seg.warnings.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5">
              <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-amber-400">
                <AlertTriangle size={12} />
                {t('h3_warnings')}
              </div>
              <ul className="list-disc space-y-0.5 pl-4 text-[11px] text-muted">
                {seg.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="space-y-2">
          {seg.clip_url ? (
            <div>
              <div className="mb-1 text-[11px] font-medium text-emerald-400">{t('h3_generated_clip')}</div>
              <video src={seg.clip_url} controls playsInline className="w-full rounded-lg bg-black" />
            </div>
          ) : seg.ref_video_url ? (
            <div>
              <div className="mb-1 text-[11px] text-muted">{t('h3_ref_video')}</div>
              <video src={seg.ref_video_url} controls playsInline poster={seg.first_frame_url ?? undefined} className="w-full rounded-lg bg-black" />
            </div>
          ) : seg.first_frame_url ? (
            <img src={seg.first_frame_url} alt="" className="w-full rounded-lg" />
          ) : null}
          {seg.sheet_urls.length > 0 && (
            <div>
              <div className="mb-1 text-[11px] text-muted">{t('h3_sheets')}</div>
              <div className="flex flex-wrap gap-1.5">
                {seg.sheet_urls.map((u, i) => (
                  <a key={u} href={u} target="_blank" rel="noreferrer" className="block h-14 w-10 overflow-hidden rounded border border-border">
                    <img src={u} alt={`sheet ${i + 1}`} className="h-full w-full object-cover" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function H3PromptModal({ isOpen, onClose, project, onProjectChange, onStartTask, busy = false }: H3PromptModalProps) {
  const { t } = useLang()
  const segments = useMemo(() => [...(project.h3_segments ?? [])].sort((a, b) => a.index - b.index), [project.h3_segments])
  const [activeTab, setActiveTab] = useState<Tab>(segments.length ? 'segments' : 'prompt')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (isOpen) setActiveTab(segments.length ? 'segments' : 'prompt')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  if (!isOpen) return null

  const promptText = project.h3_prompt || '（尚未生成 MiniMax H3 提示詞）'
  const reportText = project.forensic_report || '（尚未生成取證分析報告）'
  const allDone = segments.length > 0 && segments.every((s) => s.status === 'done' && s.clip_url)
  const anyDone = segments.some((s) => s.clip_url)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(promptText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable */
    }
  }

  const tabBtn = (id: Tab, icon: JSX.Element, label: string) => (
    <button
      type="button"
      onClick={() => setActiveTab(id)}
      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
        activeTab === id ? 'bg-accent text-white shadow-sm' : 'text-muted hover:bg-panel-2 hover:text-text'
      }`}
    >
      {icon}
      {label}
    </button>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm animate-fade-in">
      <div className="card relative flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden border border-border bg-panel-2 shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent/20 text-accent">
              <Sparkles size={18} />
            </span>
            <div>
              <h2 className="text-base font-semibold text-text">{t('view_h3_dossier')}</h2>
              <p className="max-w-md truncate text-xs text-muted">
                {project.title}
                {project.h3_mode ? ` · ${project.h3_mode.toUpperCase()}` : ''}
              </p>
              {project.source_url && (
                <a
                  href={project.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="block max-w-md truncate text-[11px] text-accent hover:underline"
                  title={project.source_url}
                >
                  {t('h3_source_link')}：{project.source_meta?.title || project.source_url}
                  {project.source_meta?.uploader ? ` · ${project.source_meta.uploader}` : ''}
                </a>
              )}
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1 text-muted transition-colors hover:bg-panel hover:text-text">
            <X size={18} />
          </button>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-panel px-6 py-2.5">
          <div className="flex items-center gap-2">
            {segments.length > 0 && tabBtn('segments', <Layers size={14} />, t('h3_segments_tab'))}
            {tabBtn('prompt', <FileText size={14} />, t('h3_prompt_tab'))}
            {tabBtn('forensics', <Sparkles size={14} />, t('h3_forensic_tab'))}
          </div>
          {activeTab === 'prompt' && (
            <button type="button" onClick={handleCopy} className="btn-primary flex items-center gap-1.5 px-3 py-1.5 text-xs">
              {copied ? <Check size={14} className="text-emerald-300" /> : <Copy size={14} />}
              {copied ? '已複製到剪貼簿！' : t('copy_h3_prompt')}
            </button>
          )}
          {activeTab === 'segments' && segments.length > 0 && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onStartTask?.(() => generateH3Video(project.id, { force: allDone }))}
              className="btn-primary flex items-center gap-1.5 px-3 py-1.5 text-xs disabled:opacity-50"
            >
              <Clapperboard size={14} />
              {anyDone && !allDone ? t('h3_generate_missing') : t('h3_generate_all')}
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'segments' ? (
            <div className="space-y-4">
              <p className="text-[11px] text-muted">{t('h3_need_minimax')}</p>
              {segments.map((seg) => (
                <SegmentCard
                  key={seg.index}
                  project={project}
                  seg={seg}
                  total={segments.length}
                  busy={busy}
                  onProjectChange={onProjectChange}
                  onStartTask={onStartTask}
                />
              ))}
            </div>
          ) : activeTab === 'prompt' ? (
            <div className="select-all whitespace-pre-wrap rounded-lg border border-border bg-panel p-4 font-mono text-xs leading-relaxed text-text">
              {promptText}
            </div>
          ) : (
            <div className="prose prose-sm max-w-none whitespace-pre-wrap rounded-lg border border-border bg-panel p-5 text-xs leading-relaxed text-text dark:prose-invert">
              {reportText}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border bg-panel px-6 py-3 text-xs text-muted">
          <span>{segments.length ? `${segments.length} parts · MiniMax-H3 v2 API` : t('h3_no_segments')}</span>
          <button type="button" onClick={onClose} className="btn-secondary px-4 py-1.5 text-xs">
            關閉
          </button>
        </div>
      </div>
    </div>
  )
}
