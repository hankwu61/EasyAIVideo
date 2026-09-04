import { useState } from 'react'
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  Clock,
  ExternalLink,
  Send,
  Share2,
  Video,
  X,
  Youtube,
} from 'lucide-react'
import { cancelPublishSchedule, errorMessage, patchProject, publishProject } from '../api'
import { useLang } from '../i18n'
import type { Project, ProjectPublishSettings, PublishPlatform, PublishPrivacy } from '../types'
import { useToast } from './Toast'
import { Spinner } from './ui'

interface PublishModalProps {
  project: Project
  isOpen: boolean
  onClose: () => void
  onProjectUpdated: (p: Project) => void
  onPublishTriggered?: () => void
}

export default function PublishModal({
  project,
  isOpen,
  onClose,
  onProjectUpdated,
  onPublishTriggered,
}: PublishModalProps) {
  const { t } = useLang()
  const toast = useToast()

  const [settings, setSettings] = useState<ProjectPublishSettings>(() => ({
    enabled: project.publish_settings?.enabled ?? true,
    auto_publish: project.publish_settings?.auto_publish ?? false,
    platforms: project.publish_settings?.platforms ?? ['youtube', 'tiktok'],
    schedule_mode: project.publish_settings?.schedule_mode ?? 'immediate',
    schedule_time: project.publish_settings?.schedule_time ?? null,
    privacy: project.publish_settings?.privacy ?? 'public',
    title_template: project.publish_settings?.title_template ?? '{title} #Shorts',
    description_template:
      project.publish_settings?.description_template ?? '{topic}\n\nCreated with EasyAIVideo\n#Shorts #TikTok',
    tags: project.publish_settings?.tags ?? ['Shorts', 'AI', 'EasyAIVideo'],
  }))

  const [submitting, setSubmitting] = useState(false)
  const [publishingNow, setPublishingNow] = useState(false)
  const [cancellingSched, setCancellingSched] = useState(false)

  if (!isOpen) return null

  const hasVideo = !!project.final_video_url
  const isScheduled = project.publish_status === 'scheduled' && !!settings.schedule_time

  const togglePlatform = (plat: PublishPlatform) => {
    setSettings((s) => {
      const exists = s.platforms.includes(plat)
      const next = exists ? s.platforms.filter((p) => p !== plat) : [...s.platforms, plat]
      return { ...s, platforms: next }
    })
  }

  const handleSaveSettings = async () => {
    setSubmitting(true)
    try {
      const updated = await patchProject(project.id, {
        publish_settings: settings,
      })
      onProjectUpdated(updated)
      toast.success(t('publish_schedule_saved'))
      onClose()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setSubmitting(false)
    }
  }

  const handlePublishNow = async () => {
    if (!hasVideo) {
      toast.error(t('publish_need_render'))
      return
    }
    setPublishingNow(true)
    try {
      await patchProject(project.id, { publish_settings: settings })
      await publishProject(project.id, {
        platforms: settings.platforms,
        privacy: settings.privacy,
        schedule_time: null, // immediate
      })
      toast.success(t('publish_status_publishing'))
      onPublishTriggered?.()
      onClose()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setPublishingNow(false)
    }
  }

  const handleCancelSchedule = async () => {
    setCancellingSched(true)
    try {
      const updated = await cancelPublishSchedule(project.id)
      onProjectUpdated(updated)
      setSettings((s) => ({ ...s, schedule_time: null, schedule_mode: 'immediate' }))
      toast.success(t('publish_schedule_cancelled'))
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setCancellingSched(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="card max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-border pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 text-accent">
              <Share2 size={20} />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight">{t('publish_modal_title')}</h2>
              <p className="text-xs text-muted">
                {project.title} · {project.aspect_ratio}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="rounded-lg p-1 text-muted hover:bg-panel-2 hover:text-text"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="mt-5 space-y-6">
          {/* Target Platforms */}
          <div>
            <label className="text-xs font-semibold text-muted uppercase tracking-wider">
              {t('publish_target_platforms')}
            </label>
            <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {/* YouTube Shorts */}
              <button
                type="button"
                onClick={() => togglePlatform('youtube')}
                className={`flex items-center gap-2.5 rounded-xl border p-3 text-left transition ${
                  settings.platforms.includes('youtube')
                    ? 'border-red-500/50 bg-red-500/10 text-text'
                    : 'border-border bg-panel-2/50 text-muted hover:border-border-strong'
                }`}
              >
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                    settings.platforms.includes('youtube')
                      ? 'bg-red-500 text-white'
                      : 'bg-panel-2 text-muted'
                  }`}
                >
                  <Youtube size={18} />
                </div>
                <div>
                  <div className="text-sm font-semibold">{t('platform_youtube')}</div>
                  <div className="text-[11px] text-muted">9:16 Shorts</div>
                </div>
              </button>

              {/* TikTok */}
              <button
                type="button"
                onClick={() => togglePlatform('tiktok')}
                className={`flex items-center gap-2.5 rounded-xl border p-3 text-left transition ${
                  settings.platforms.includes('tiktok')
                    ? 'border-cyan-500/50 bg-cyan-500/10 text-text'
                    : 'border-border bg-panel-2/50 text-muted hover:border-border-strong'
                }`}
              >
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                    settings.platforms.includes('tiktok')
                      ? 'bg-cyan-500 text-black'
                      : 'bg-panel-2 text-muted'
                  }`}
                >
                  <Video size={18} />
                </div>
                <div>
                  <div className="text-sm font-semibold">{t('platform_tiktok')}</div>
                  <div className="text-[11px] text-muted">Direct Post</div>
                </div>
              </button>

              {/* Webhook */}
              <button
                type="button"
                onClick={() => togglePlatform('webhook')}
                className={`flex items-center gap-2.5 rounded-xl border p-3 text-left transition ${
                  settings.platforms.includes('webhook')
                    ? 'border-accent/50 bg-accent/10 text-text'
                    : 'border-border bg-panel-2/50 text-muted hover:border-border-strong'
                }`}
              >
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                    settings.platforms.includes('webhook')
                      ? 'bg-accent text-white'
                      : 'bg-panel-2 text-muted'
                  }`}
                >
                  <Send size={16} />
                </div>
                <div>
                  <div className="text-sm font-semibold">{t('platform_webhook')}</div>
                  <div className="text-[11px] text-muted">Zapier/Make</div>
                </div>
              </button>
            </div>
          </div>

          {/* Auto publish toggle */}
          <div className="rounded-xl border border-border bg-panel-2/50 p-4">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={settings.auto_publish}
                onChange={(e) => setSettings((s) => ({ ...s, auto_publish: e.target.checked }))}
                className="mt-0.5 h-4 w-4 rounded border-border accent-accent"
              />
              <div className="flex-1">
                <div className="text-sm font-medium">{t('publish_auto_toggle')}</div>
                <div className="text-xs text-muted">{t('publish_auto_toggle_hint')}</div>
              </div>
            </label>
          </div>

          {/* Mode & Schedule Time */}
          <div className="space-y-3">
            <label className="text-xs font-semibold text-muted uppercase tracking-wider">
              {t('publish_mode_scheduled')}
            </label>
            <div className="flex rounded-lg border border-border bg-panel-2 p-1">
              <button
                type="button"
                onClick={() => setSettings((s) => ({ ...s, schedule_mode: 'immediate' }))}
                className={`flex-1 rounded-md py-1.5 text-xs font-medium transition ${
                  settings.schedule_mode === 'immediate'
                    ? 'bg-accent text-white shadow-xs'
                    : 'text-muted hover:text-text'
                }`}
              >
                {t('publish_mode_immediate')}
              </button>
              <button
                type="button"
                onClick={() => setSettings((s) => ({ ...s, schedule_mode: 'scheduled' }))}
                className={`flex-1 rounded-md py-1.5 text-xs font-medium transition ${
                  settings.schedule_mode === 'scheduled'
                    ? 'bg-accent text-white shadow-xs'
                    : 'text-muted hover:text-text'
                }`}
              >
                <Calendar size={13} className="mr-1 inline" />
                {t('publish_mode_scheduled')}
              </button>
            </div>

            {settings.schedule_mode === 'scheduled' && (
              <div className="rounded-xl border border-border bg-bg-elev p-3.5">
                <label className="block text-xs font-medium text-text mb-1">
                  {t('publish_schedule_time')}
                </label>
                <input
                  type="datetime-local"
                  className="input w-full text-sm"
                  value={settings.schedule_time ? settings.schedule_time.slice(0, 16) : ''}
                  onChange={(e) =>
                    setSettings((s) => ({
                      ...s,
                      schedule_time: e.target.value ? new Date(e.target.value).toISOString() : null,
                    }))
                  }
                />
                <p className="mt-1.5 text-[11px] text-muted">
                  {t('publish_schedule_time_hint')}
                </p>
              </div>
            )}
          </div>

          {/* Privacy & Metadata */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                {t('publish_privacy')}
              </label>
              <select
                className="input w-full text-sm"
                value={settings.privacy}
                onChange={(e) => setSettings((s) => ({ ...s, privacy: e.target.value as PublishPrivacy }))}
              >
                <option value="public">{t('privacy_public')}</option>
                <option value="unlisted">{t('privacy_unlisted')}</option>
                <option value="private">{t('privacy_private')}</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                {t('publish_tags_label')}
              </label>
              <input
                type="text"
                className="input w-full text-sm"
                value={settings.tags.join(', ')}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    tags: e.target.value
                      .split(',')
                      .map((t) => t.trim())
                      .filter(Boolean),
                  }))
                }
                placeholder="Shorts, AI, Drama"
              />
            </div>
          </div>

          {/* Title Template */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-xs font-medium text-muted">{t('publish_title_template')}</label>
              <span className="text-[11px] text-muted">{t('publish_title_hint')}</span>
            </div>
            <input
              type="text"
              className="input w-full text-sm"
              value={settings.title_template}
              onChange={(e) => setSettings((s) => ({ ...s, title_template: e.target.value }))}
            />
          </div>

          {/* History */}
          {project.publish_records && project.publish_records.length > 0 && (
            <div>
              <label className="text-xs font-semibold text-muted uppercase tracking-wider">
                {t('publish_history')}
              </label>
              <div className="mt-2 divide-y divide-border rounded-xl border border-border bg-panel-2/40">
                {project.publish_records.map((rec) => (
                  <div key={rec.id} className="flex items-center justify-between p-3 text-xs">
                    <div className="flex items-center gap-2.5">
                      {rec.status === 'succeeded' ? (
                        <CheckCircle2 size={16} className="text-emerald-400" />
                      ) : (
                        <AlertCircle size={16} className="text-red-400" />
                      )}
                      <div>
                        <div className="font-semibold text-text uppercase">
                          {rec.platform}
                          {rec.status === 'failed' && (
                            <span className="ml-2 text-red-400 font-normal">{rec.error}</span>
                          )}
                        </div>
                        <div className="text-[11px] text-muted">
                          {new Date(rec.published_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    {rec.url && (
                      <a
                        href={rec.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-accent hover:bg-accent/10"
                      >
                        {t('publish_open_link')}
                        <ExternalLink size={11} />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
          <div>
            {isScheduled && (
              <button
                type="button"
                className="btn-secondary text-red-400 hover:text-red-300"
                disabled={cancellingSched}
                onClick={handleCancelSchedule}
              >
                {cancellingSched ? <Spinner size={14} /> : <Clock size={14} />}
                {t('publish_cancel_schedule')}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" className="btn-secondary" onClick={handleSaveSettings} disabled={submitting}>
              {submitting ? <Spinner size={14} /> : null}
              {t('publish_save_schedule')}
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={publishingNow || !hasVideo || settings.platforms.length === 0}
              onClick={handlePublishNow}
            >
              {publishingNow ? <Spinner size={14} /> : <Send size={14} />}
              {t('publish_now')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
