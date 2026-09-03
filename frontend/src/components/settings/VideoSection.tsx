import { Info } from 'lucide-react'
import { useLang } from '../../i18n'
import type { IdLabel, VideoConfig, VideoMode, VideoProvider, VideoResolution, Workflows } from '../../types'
import { Field, SectionCard } from '../ui'
import { NumberInput, SecretInput } from './ProviderSections'
import TestButton from './TestButton'
import { WorkflowSelect } from './MediaSections'

const RESOLUTIONS: VideoResolution[] = ['480p', '720p', '1080p']

const modeHintKey = {
  i2v: 'video_mode_hint_i2v',
  t2v: 'video_mode_hint_t2v',
  keyframes: 'video_mode_hint_keyframes',
} as const

export default function VideoSection({
  value,
  onChange,
  beforeTest,
  workflows,
  videoModes,
}: {
  value: VideoConfig
  onChange: (patch: Partial<VideoConfig>) => void
  beforeTest: () => Promise<boolean>
  workflows: Workflows | null
  videoModes: IdLabel[]
}) {
  const { t } = useLang()
  const comfy = value.provider === 'comfyui'
  const agnes = value.provider === 'agnes'
  const hintKey = modeHintKey[value.mode as VideoMode]
  return (
    <SectionCard
      title={t('sec_video')}
      description={t('sec_video_desc')}
      actions={value.provider !== 'kenburns' ? <TestButton kind="video" beforeTest={beforeTest} /> : undefined}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('provider')}>
          <select
            className="input"
            value={value.provider}
            onChange={(e) => onChange({ provider: e.target.value as VideoProvider })}
          >
            <option value="kenburns">{t('provider_kenburns')}</option>
            <option value="comfyui">{t('provider_comfyui')}</option>
            <option value="agnes">{t('provider_agnes')}</option>
          </select>
        </Field>
        <Field label={t('fps')}>
          <NumberInput value={value.fps} onChange={(fps) => onChange({ fps })} min={1} max={120} step={1} />
        </Field>

        {agnes && (
          <>
            <Field label={t('api_key')} hint={t('api_key_hint')} className="sm:col-span-2">
              <SecretInput value={value.api_key} onChange={(api_key) => onChange({ api_key })} placeholder="sk-…" />
            </Field>
            <Field label={t('base_url')}>
              <input
                className="input font-mono"
                value={value.base_url}
                placeholder="https://apihub.agnes-ai.com/v1"
                onChange={(e) => onChange({ base_url: e.target.value })}
              />
            </Field>
            <Field label={t('model')}>
              <input
                className="input font-mono"
                value={value.model}
                placeholder="agnes-video-v2.0"
                onChange={(e) => onChange({ model: e.target.value })}
              />
            </Field>
            <Field label={t('resolution')}>
              <select
                className="input"
                value={value.resolution}
                onChange={(e) => onChange({ resolution: e.target.value as VideoResolution })}
              >
                {!RESOLUTIONS.includes(value.resolution) && value.resolution && (
                  <option value={value.resolution}>{value.resolution}</option>
                )}
                {RESOLUTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('video_gen_mode')} hint={hintKey ? t(hintKey) : undefined}>
              <select className="input" value={value.mode} onChange={(e) => onChange({ mode: e.target.value as VideoMode })}>
                {!videoModes.some((m) => m.id === value.mode) && value.mode && (
                  <option value={value.mode}>{value.mode}</option>
                )}
                {videoModes.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('max_clip_seconds')}>
              <NumberInput
                value={value.max_clip_seconds}
                onChange={(max_clip_seconds) => onChange({ max_clip_seconds })}
                min={1}
                max={18}
                step={1}
              />
            </Field>
            <Field label={t('concurrency')}>
              <NumberInput
                value={value.concurrency}
                onChange={(concurrency) => onChange({ concurrency })}
                min={1}
                max={4}
                step={1}
              />
            </Field>
          </>
        )}

        {comfy && (
          <>
            <Field label={t('comfyui_url')}>
              <input
                className="input font-mono"
                value={value.comfyui_url}
                onChange={(e) => onChange({ comfyui_url: e.target.value })}
              />
            </Field>
            <Field label={t('comfyui_workflow')}>
              <WorkflowSelect
                options={workflows?.video ?? []}
                value={value.comfyui_workflow}
                onChange={(comfyui_workflow) => onChange({ comfyui_workflow })}
              />
            </Field>
          </>
        )}

        <p className="flex items-start gap-2 rounded-lg border border-border bg-bg-elev px-3 py-2 text-[11px] leading-relaxed text-muted sm:col-span-2">
          <Info size={13} className="mt-0.5 shrink-0 text-accent" />
          {t('ai_video_note')}
        </p>
      </div>
    </SectionCard>
  )
}
