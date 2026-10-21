import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { useLang } from '../../i18n'
import type { LlmConfig, LlmPreset, LlmProvider, TtsConfig, TtsProvider, VoiceOption } from '../../types'
import { VoiceSelect } from '../ProjectSettingsFields'
import { Field, SectionCard } from '../ui'
import TestButton from './TestButton'

export function SecretInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input
        className="input pr-9 font-mono"
        type={show ? 'text' : 'password'}
        autoComplete="off"
        spellCheck={false}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-faint hover:text-text"
        aria-label={show ? 'hide' : 'show'}
      >
        {show ? <EyeOff size={14} /> : <Eye size={14} />}
      </button>
    </div>
  )
}

export function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
}) {
  return (
    <input
      className="input tabular-nums"
      type="number"
      value={Number.isFinite(value) ? value : ''}
      min={min}
      max={max}
      step={step}
      onChange={(e) => {
        const n = Number(e.target.value)
        if (e.target.value !== '' && Number.isFinite(n)) onChange(n)
      }}
    />
  )
}

interface SectionProps<T> {
  value: T
  onChange: (patch: Partial<T>) => void
  beforeTest: () => Promise<boolean>
}

export function LlmSection({ value, onChange, beforeTest, presets }: SectionProps<LlmConfig> & { presets: LlmPreset[] }) {
  const { t } = useLang()
  const compat = value.provider === 'openai_compat'
  return (
    <SectionCard
      title={t('sec_llm')}
      description={t('sec_llm_desc')}
      actions={<TestButton kind="llm" beforeTest={beforeTest} />}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('provider')}>
          <select className="input" value={value.provider} onChange={(e) => onChange({ provider: e.target.value as LlmProvider })}>
            <option value="openai_compat">{t('provider_openai_compat')}</option>
            <option value="mock">{t('provider_mock')}</option>
          </select>
        </Field>
        {compat && (
          <Field label={t('quick_fill')}>
            <div className="flex flex-wrap gap-1.5">
              {presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => onChange({ base_url: p.base_url, model: p.model })}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </Field>
        )}
        {compat && (
          <>
            <Field label={t('api_key')} hint={t('api_key_hint')} className="sm:col-span-2">
              <SecretInput value={value.api_key} onChange={(api_key) => onChange({ api_key })} placeholder="sk-…" />
            </Field>
            <Field label={t('base_url')}>
              <input className="input font-mono" value={value.base_url} onChange={(e) => onChange({ base_url: e.target.value })} />
            </Field>
            <Field label={t('model')}>
              <input className="input font-mono" value={value.model} onChange={(e) => onChange({ model: e.target.value })} />
            </Field>
          </>
        )}
        <Field label={t('temperature')} right={value.temperature.toFixed(2)}>
          <input
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={value.temperature}
            onChange={(e) => onChange({ temperature: Number(e.target.value) })}
          />
        </Field>
      </div>
    </SectionCard>
  )
}

export function TtsSection({ value, onChange, beforeTest, voices }: SectionProps<TtsConfig> & { voices: VoiceOption[] }) {
  const { t } = useLang()
  const compat = value.provider === 'openai_compat'
  const fish = value.provider === 'fish_audio'
  return (
    <SectionCard
      title={t('sec_tts')}
      description={t('sec_tts_desc')}
      actions={value.provider !== 'silent' ? <TestButton kind="tts" beforeTest={beforeTest} /> : undefined}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('provider')}>
          <select className="input" value={value.provider} onChange={(e) => {
            const provider = e.target.value as TtsProvider
            onChange({ provider, voice: provider === 'fish_audio' ? 'fish-zh-TW-female' : provider === 'edge' ? 'zh-TW-HsiaoChenNeural' : 'alloy' })
          }}>
            <option value="fish_audio">Fish Audio API</option>
            <option value="edge">{t('provider_edge')}</option>
            <option value="openai_compat">{t('provider_openai_compat')}</option>
            <option value="silent">{t('provider_silent')}</option>
          </select>
        </Field>
        <Field label={t('default_voice')}>
          {fish ? (
            <select className="input" value={value.voice} onChange={(e) => onChange({ voice: e.target.value })}>
              <option value="fish-zh-TW-female">{t('fish_female')}</option>
              <option value="fish-zh-TW-male">{t('fish_male')}</option>
            </select>
          ) : voices.length > 0 && !voices.some((v) => v.id.startsWith('fish-')) ? (
            <VoiceSelect voices={voices} value={value.voice} onChange={(voice) => onChange({ voice })} />
          ) : (
            <input className="input font-mono" value={value.voice} onChange={(e) => onChange({ voice: e.target.value })} />
          )}
        </Field>
        <Field label={t('speed')} right={`${value.speed.toFixed(2)}×`} className="sm:col-span-2">
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.05}
            value={value.speed}
            onChange={(e) => onChange({ speed: Number(e.target.value) })}
          />
        </Field>
        {fish && (
          <>
            <Field label={t('api_key')} hint={t('api_key_hint')} className="sm:col-span-2">
              <SecretInput value={value.fish_audio.api_key} onChange={(api_key) => onChange({ fish_audio: { ...value.fish_audio, api_key } })} />
            </Field>
            <Field label={t('base_url')}>
              <input className="input font-mono" value={value.fish_audio.base_url} onChange={(e) => onChange({ fish_audio: { ...value.fish_audio, base_url: e.target.value } })} />
            </Field>
            <Field label={t('model')}>
              <input className="input font-mono" value={value.fish_audio.model} onChange={(e) => onChange({ fish_audio: { ...value.fish_audio, model: e.target.value } })} />
            </Field>
            <Field label={t('fish_female')} hint={t('fish_voice_hint')}>
              <input className="input font-mono" placeholder="Voice ID" value={value.fish_audio.female_reference_id} onChange={(e) => onChange({ fish_audio: { ...value.fish_audio, female_reference_id: e.target.value } })} />
            </Field>
            <Field label={t('fish_male')} hint={t('fish_voice_hint')}>
              <input className="input font-mono" placeholder="Voice ID" value={value.fish_audio.male_reference_id} onChange={(e) => onChange({ fish_audio: { ...value.fish_audio, male_reference_id: e.target.value } })} />
            </Field>
          </>
        )}
        {compat && (
          <>
            <Field label={t('api_key')} hint={t('api_key_hint')} className="sm:col-span-2">
              <SecretInput value={value.api_key} onChange={(api_key) => onChange({ api_key })} placeholder="sk-…" />
            </Field>
            <Field label={t('base_url')}>
              <input className="input font-mono" value={value.base_url} onChange={(e) => onChange({ base_url: e.target.value })} />
            </Field>
            <Field label={t('model')}>
              <input className="input font-mono" value={value.model} onChange={(e) => onChange({ model: e.target.value })} />
            </Field>
          </>
        )}
      </div>
    </SectionCard>
  )
}
