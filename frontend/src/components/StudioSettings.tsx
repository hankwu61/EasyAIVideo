import { useEffect, useRef, useState } from 'react'
import { Info } from 'lucide-react'
import { errorMessage, patchProject } from '../api'
import type { Resources } from '../hooks/useResources'
import { useLang } from '../i18n'
import type { Project, ProjectPatch } from '../types'
import { DEFAULT_VIDEO_MODES, OutputSettingsFields, type OutputSettings } from './ProjectSettingsFields'
import { useToast } from './Toast'
import { Field } from './ui'

interface LocalSettings extends OutputSettings {
  style_id: string
  style_prompt: string
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
  const pending = useRef<ProjectPatch>({})
  const timer = useRef<number | null>(null)
  const inflight = useRef(false)

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
    const debounce = 'tts_speed' in patch || 'bgm_volume' in patch
    queue(patch, debounce)
  }

  const { styles, voices, bgm, presets } = resources

  return (
    <section className="card p-4">
      <h2 className="mb-3 text-sm font-semibold">{t('settings')}</h2>
      <div className="space-y-3">
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
    </section>
  )
}
