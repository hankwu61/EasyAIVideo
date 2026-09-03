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
  return (
    <SectionCard
      title={t('sec_tts')}
      description={t('sec_tts_desc')}
      actions={value.provider !== 'silent' ? <TestButton kind="tts" beforeTest={beforeTest} /> : undefined}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('provider')}>
          <select className="input" value={value.provider} onChange={(e) => onChange({ provider: e.target.value as TtsProvider })}>
            <option value="edge">{t('provider_edge')}</option>
            <option value="openai_compat">{t('provider_openai_compat')}</option>
            <option value="silent">{t('provider_silent')}</option>
          </select>
        </Field>
        <Field label={t('default_voice')}>
          {voices.length > 0 ? (
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
