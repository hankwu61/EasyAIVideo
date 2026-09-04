import { useEffect, useRef, useState } from 'react'
import { Info, LayoutTemplate, Sparkles } from 'lucide-react'
import { errorMessage, listTemplates, patchProject } from '../api'
import type { Resources } from '../hooks/useResources'
import { useLang } from '../i18n'
import type { Project, ProjectPatch, Template } from '../types'
import { DEFAULT_VIDEO_MODES, OutputSettingsFields, type OutputSettings } from './ProjectSettingsFields'
import { useToast } from './Toast'
import { Field } from './ui'
import { TemplateEditModal } from './templates/TemplateEditModal'

interface LocalSettings extends OutputSettings {
  style_id: string
  style_prompt: string
  template_id?: string | null
}

function fromProject(p: Project): LocalSettings {
  return {
    voice: p.voice,
    tts_speed: p.tts_speed,
    bgm: p.bgm,
    bgm_volume: p.bgm_volume,
    motion: p.motion,
    video_mode: p.video_mode ?? null,
    subtitle_enabled: p.subtitle_enabled,
    show_title: p.show_title,
    style_id: p.style_id,
    style_prompt: p.style_prompt,
    font_family: p.font_family || 'msjh',
    font_size: p.font_size || 24,
    subtitle_position: p.subtitle_position || 'bottom',
    transition: p.transition || 'none',
    transition_duration: p.transition_duration ?? 0.5,
    template_id: p.template_id ?? null,
  }
}

const DEBOUNCE_MS = 600

export default function StudioSettings({
  project,
  resources,
  disabled,
  onProject,
}: {
  project: Project
  resources: Resources
  disabled: boolean
  onProject: (p: Project) => void
}) {
  const { t } = useLang()
  const toast = useToast()
  const [local, setLocal] = useState<LocalSettings>(() => fromProject(project))
  const [templates, setTemplates] = useState<Template[]>([])
  const [isSaveTemplateOpen, setIsSaveTemplateOpen] = useState(false)
  const pending = useRef<ProjectPatch>({})
  const timer = useRef<number | null>(null)
  const inflight = useRef(false)

  useEffect(() => {
    listTemplates().then(setTemplates).catch(console.error)
  }, [])

  // Sync from server only when nothing is pending locally.
  useEffect(() => {
    if (timer.current === null && !inflight.current) setLocal(fromProject(project))
  }, [project])

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )

  const flush = async () => {
    timer.current = null
    const patch = pending.current
    pending.current = {}
    if (Object.keys(patch).length === 0) return
    inflight.current = true
    try {
      const updated = await patchProject(project.id, patch)
      onProject(updated)
      toast.success(t('settings_updated'))
    } catch (e) {
      toast.error(errorMessage(e))
      setLocal(fromProject(project))
    } finally {
      inflight.current = false
    }
  }

  const queue = (patch: Partial<LocalSettings>, debounce: boolean) => {
    setLocal((l) => ({ ...l, ...patch }))
    pending.current = { ...pending.current, ...patch }
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => void flush(), debounce ? DEBOUNCE_MS : 0)
  }

  const onOutputChange = (patch: Partial<OutputSettings>) => {
    const debounce = 'tts_speed' in patch || 'bgm_volume' in patch || 'transition_duration' in patch
    queue(patch, debounce)
  }

  const applyTemplate = (tpl: Template) => {
    const patch: Partial<LocalSettings> = {
      style_id: tpl.config.style_id,
      style_prompt: tpl.config.style_prompt,
      font_family: tpl.config.font_family,
      font_size: tpl.config.font_size,
      subtitle_position: tpl.config.subtitle_position,
      transition: tpl.config.transition,
      transition_duration: tpl.config.transition_duration,
      bgm: tpl.config.bgm,
      bgm_volume: tpl.config.bgm_volume,
      template_id: tpl.id,
    }
    queue(patch, false)
    toast.success(t('template_applied'))
  }

  const { styles, voices, bgm, presets } = resources

  return (
    <section className="card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{t('settings')}</h2>
        <button
          type="button"
          onClick={() => setIsSaveTemplateOpen(true)}
          className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
          title={t('save_as_template')}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{t('save_as_template')}</span>
        </button>
      </div>

      <div className="space-y-3">
        {/* Quick Template Switcher */}
        {templates.length > 0 && (
          <div className="rounded-xl border border-purple-500/20 bg-purple-950/20 p-3 space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-purple-300">
              <LayoutTemplate className="w-4 h-4" />
              <span>{t('choose_template')}</span>
            </div>
            <select
              className="input text-xs"
              value={local.template_id ?? ''}
              disabled={disabled}
              onChange={(e) => {
                const found = templates.find((t) => t.id === e.target.value)
                if (found) applyTemplate(found)
              }}
            >
              <option value="">-- 選擇模板一鍵套用 --</option>
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name} {tpl.is_builtin ? '⭐' : ''}
                </option>
              ))}
            </select>
          </div>
        )}

        <OutputSettingsFields
          compact
          value={local}
          onChange={onOutputChange}
          voices={voices}
          bgm={bgm}
          motions={presets.motions}
          videoModes={presets.video_modes ?? DEFAULT_VIDEO_MODES}
          disabled={disabled}
        />

        <Field label={t('style')}>
          <select
            className="input"
            value={local.style_id}
            disabled={disabled}
            onChange={(e) => {
              const s = styles.find((x) => x.id === e.target.value)
              queue({ style_id: e.target.value, style_prompt: s?.prompt ?? local.style_prompt }, false)
            }}
          >
            {!styles.some((s) => s.id === local.style_id) && local.style_id && (
              <option value={local.style_id}>{local.style_id}</option>
            )}
            {styles.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label={t('style_prompt')}>
          <textarea
            className="input min-h-16 font-mono text-xs"
            rows={3}
            value={local.style_prompt}
            disabled={disabled}
            onChange={(e) => queue({ style_prompt: e.target.value }, true)}
          />
        </Field>

        <p className="flex items-start gap-2 rounded-lg border border-border bg-bg-elev px-3 py-2 text-[11px] leading-relaxed text-muted">
          <Info size={13} className="mt-0.5 shrink-0 text-accent" />
          {t('settings_stale_note')}
        </p>
      </div>

      <TemplateEditModal
        isOpen={isSaveTemplateOpen}
        initialName={`${project.title || '專案'} 模板`}
        initialDescription={`從專案「${project.title || project.id}」產生的視覺風格模板`}
        initialConfig={{
          style_id: local.style_id,
          style_prompt: local.style_prompt,
          font_family: local.font_family,
          font_size: local.font_size,
          subtitle_position: local.subtitle_position,
          transition: local.transition,
          transition_duration: local.transition_duration,
          bgm: local.bgm,
          bgm_volume: local.bgm_volume,
        }}
        onClose={() => setIsSaveTemplateOpen(false)}
        onSaveSuccess={(newTpl) => {
          setTemplates((prev) => [newTpl, ...prev])
          toast.success(t('template_saved'))
        }}
      />
    </section>
  )
}
