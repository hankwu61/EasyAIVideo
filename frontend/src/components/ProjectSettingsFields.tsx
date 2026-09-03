import { useMemo } from 'react'
import { Check, Music, RectangleHorizontal, RectangleVertical, Square } from 'lucide-react'
import { useLang } from '../i18n'
import type { AspectRatio, AspectRatioPreset, BgmOption, IdLabel, VideoMode, VoiceOption } from '../types'
import { cx } from '../utils'
import { Field, Toggle } from './ui'

/** The subset of project settings shared by the create form and the studio settings panel. */
export interface OutputSettings {
  voice: string
  tts_speed: number
  bgm: string | null
  bgm_volume: number
  motion: string
  /** null = system default; only used when motion === 'ai_video'. */
  video_mode: VideoMode | null
  subtitle_enabled: boolean
  show_title: boolean
}

/** Fallback when the backend does not return `presets.video_modes`. */
export const DEFAULT_VIDEO_MODES: IdLabel[] = [
  { id: 'i2v', label: '圖生影片（場景圖為首幀）' },
  { id: 't2v', label: '文生影片（只用提示詞）' },
  { id: 'keyframes', label: '首尾幀（下一場景圖為尾幀）' },
]

/** The motion preset id that switches a project to AI video clips. */
export const AI_VIDEO_MOTION = 'ai_video'

export function VoiceSelect({
  voices,
  value,
  onChange,
  disabled,
}: {
  voices: VoiceOption[]
  value: string
  onChange: (v: string) => void
  disabled?: boolean
}) {
  const groups = useMemo(() => {
    const map = new Map<string, VoiceOption[]>()
    for (const v of voices) {
      const list = map.get(v.locale) ?? []
      list.push(v)
      map.set(v.locale, list)
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [voices])
  const known = voices.some((v) => v.id === value)
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
      {!known && value && <option value={value}>{value}</option>}
      {groups.map(([locale, list]) => (
        <optgroup key={locale} label={locale}>
          {list.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
              {v.gender ? ` · ${v.gender}` : ''}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

export function OutputSettingsFields({
  value,
  onChange,
  voices,
  bgm,
  motions,
  videoModes = DEFAULT_VIDEO_MODES,
  disabled,
  compact,
}: {
  value: OutputSettings
  onChange: (patch: Partial<OutputSettings>) => void
  voices: VoiceOption[]
  bgm: BgmOption[]
  motions: IdLabel[]
  videoModes?: IdLabel[]
  disabled?: boolean
  compact?: boolean
}) {
  const { t } = useLang()
  const gap = compact ? 'space-y-3' : 'space-y-4'
  return (
    <div className={gap}>
      <Field label={t('voice')}>
        <VoiceSelect voices={voices} value={value.voice} onChange={(voice) => onChange({ voice })} disabled={disabled} />
      </Field>

      <Field label={t('speed')} right={`${value.tts_speed.toFixed(2)}×`}>
        <input
          type="range"
          min={0.5}
          max={2}
          step={0.05}
          value={value.tts_speed}
          onChange={(e) => onChange({ tts_speed: Number(e.target.value) })}
          disabled={disabled}
        />
      </Field>

      <div className={cx('grid gap-3', compact ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2')}>
        <Field label={t('bgm')}>
          <div className="relative">
            <Music size={14} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-faint" />
            <select
              className="input pl-8"
              value={value.bgm ?? ''}
              onChange={(e) => onChange({ bgm: e.target.value || null })}
              disabled={disabled}
            >
              <option value="">{t('bgm_none')}</option>
              {value.bgm && !bgm.some((b) => b.name === value.bgm) && <option value={value.bgm}>{value.bgm}</option>}
              {bgm.map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
        </Field>
        <Field label={t('bgm_volume')} right={`${Math.round(value.bgm_volume * 100)}%`}>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value.bgm_volume}
            onChange={(e) => onChange({ bgm_volume: Number(e.target.value) })}
            disabled={disabled || !value.bgm}
            className={cx(!value.bgm && 'opacity-40')}
          />
        </Field>
      </div>

      <Field label={t('motion')}>
        <select
          className="input"
          value={value.motion}
          onChange={(e) => onChange({ motion: e.target.value })}
          disabled={disabled}
        >
          {!motions.some((m) => m.id === value.motion) && value.motion && (
            <option value={value.motion}>{value.motion}</option>
          )}
          {motions.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </Field>

      {value.motion === AI_VIDEO_MOTION && (
        <Field label={t('project_video_mode')}>
          <select
            className="input"
            value={value.video_mode ?? ''}
            onChange={(e) => onChange({ video_mode: (e.target.value || null) as VideoMode | null })}
            disabled={disabled}
          >
            <option value="">{t('video_mode_default')}</option>
            {value.video_mode && !videoModes.some((m) => m.id === value.video_mode) && (
              <option value={value.video_mode}>{value.video_mode}</option>
            )}
            {videoModes.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </Field>
      )}

      <div className={cx('grid gap-2', compact ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2')}>
        <Toggle
          checked={value.subtitle_enabled}
          onChange={(subtitle_enabled) => onChange({ subtitle_enabled })}
          label={t('subtitle')}
          disabled={disabled}
        />
        <Toggle
          checked={value.show_title}
          onChange={(show_title) => onChange({ show_title })}
          label={t('show_title')}
          disabled={disabled}
        />
      </div>
    </div>
  )
}

const ratioIcon: Record<AspectRatio, typeof Square> = {
  '9:16': RectangleVertical,
  '16:9': RectangleHorizontal,
  '1:1': Square,
}

export function AspectRatioPicker({
  ratios,
  value,
  onChange,
  disabled,
}: {
  ratios: AspectRatioPreset[]
  value: AspectRatio
  onChange: (v: AspectRatio) => void
  disabled?: boolean
}) {
  const { t } = useLang()
  const names: Record<AspectRatio, string> = {
    '9:16': t('ratio_portrait'),
    '16:9': t('ratio_landscape'),
    '1:1': t('ratio_square'),
  }
  return (
    <div className="grid grid-cols-3 gap-2">
      {ratios.map((r) => {
        const Icon = ratioIcon[r.id] ?? Square
        const active = r.id === value
        return (
          <button
            key={r.id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(r.id)}
            className={cx(
              'relative flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center transition',
              active
                ? 'border-accent bg-accent/10 text-text shadow-[0_0_0_1px_rgb(124_108_255/0.5)]'
                : 'border-border bg-bg-elev text-muted hover:border-border-strong hover:text-text',
              disabled && 'cursor-not-allowed opacity-50',
            )}
          >
            {active && (
              <span className="absolute top-1.5 right-1.5 grid h-4 w-4 place-items-center rounded-full bg-accent text-white">
                <Check size={10} strokeWidth={3} />
              </span>
            )}
            <Icon size={26} strokeWidth={1.5} className={active ? 'text-accent' : ''} />
            <span className="text-sm font-semibold">{r.id}</span>
            <span className="text-[10px] leading-tight text-faint">
              {names[r.id] ?? ''} · {r.width}×{r.height}
            </span>
          </button>
        )
      })}
    </div>
  )
}
