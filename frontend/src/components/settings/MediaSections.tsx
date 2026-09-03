import { useLang } from '../../i18n'
import type { ImageConfig, ImageProvider, ImageSizeMode, RenderConfig, Workflows } from '../../types'
import { Field, SectionCard, Toggle } from '../ui'
import { NumberInput, SecretInput } from './ProviderSections'
import TestButton from './TestButton'

interface SectionProps<T> {
  value: T
  onChange: (patch: Partial<T>) => void
  beforeTest: () => Promise<boolean>
}

export function WorkflowSelect({
  options,
  value,
  onChange,
}: {
  options: string[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <select className="input font-mono" value={value} onChange={(e) => onChange(e.target.value)}>
      {value && !options.includes(value) && <option value={value}>{value}</option>}
      {options.map((w) => (
        <option key={w} value={w}>
          {w}
        </option>
      ))}
    </select>
  )
}

export function ImageSection({
  value,
  onChange,
  beforeTest,
  workflows,
}: SectionProps<ImageConfig> & { workflows: Workflows | null }) {
  const { t } = useLang()
  const compat = value.provider === 'openai_compat'
  const comfy = value.provider === 'comfyui'
  const exact = value.size_mode === 'exact'
  return (
    <SectionCard
      title={t('sec_image')}
      description={t('sec_image_desc')}
      actions={
        compat ? (
          <TestButton kind="image" beforeTest={beforeTest} />
        ) : comfy ? (
          <TestButton kind="comfyui" beforeTest={beforeTest} />
        ) : undefined
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('provider')} className="sm:col-span-2">
          <select
            className="input"
            value={value.provider}
            onChange={(e) => onChange({ provider: e.target.value as ImageProvider })}
          >
            <option value="placeholder">{t('provider_placeholder')}</option>
            <option value="openai_compat">{t('provider_openai_compat')}</option>
            <option value="comfyui">{t('provider_comfyui')}</option>
          </select>
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
            <Field label={t('size_mode')}>
              <select
                className="input"
                value={value.size_mode}
                onChange={(e) => onChange({ size_mode: e.target.value as ImageSizeMode })}
              >
                <option value="preset">{t('size_mode_preset')}</option>
                <option value="exact">{t('size_mode_exact')}</option>
              </select>
            </Field>
            {exact ? (
              <Field label={t('short_edge')} hint={t('short_edge_hint')}>
                <NumberInput
                  value={value.short_edge}
                  onChange={(short_edge) => onChange({ short_edge })}
                  min={512}
                  max={2160}
                  step={1}
                />
              </Field>
            ) : (
              <div className="grid grid-cols-3 gap-3 sm:col-span-2">
                <Field label={t('size_portrait')}>
                  <input
                    className="input font-mono"
                    value={value.size_portrait}
                    onChange={(e) => onChange({ size_portrait: e.target.value })}
                  />
                </Field>
                <Field label={t('size_landscape')}>
                  <input
                    className="input font-mono"
                    value={value.size_landscape}
                    onChange={(e) => onChange({ size_landscape: e.target.value })}
                  />
                </Field>
                <Field label={t('size_square')}>
                  <input
                    className="input font-mono"
                    value={value.size_square}
                    onChange={(e) => onChange({ size_square: e.target.value })}
                  />
                </Field>
              </div>
            )}
            <div className="sm:col-span-2">
              <Toggle
                checked={value.use_references}
                onChange={(use_references) => onChange({ use_references })}
                label={t('use_references')}
              />
            </div>
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
                options={workflows?.image ?? []}
                value={value.comfyui_workflow}
                onChange={(comfyui_workflow) => onChange({ comfyui_workflow })}
              />
            </Field>
          </>
        )}

        {value.provider !== 'placeholder' && (
          <>
            <Field label={t('prompt_prefix')}>
              <textarea
                className="input min-h-16 font-mono text-xs"
                rows={2}
                value={value.prompt_prefix}
                onChange={(e) => onChange({ prompt_prefix: e.target.value })}
              />
            </Field>
            <Field label={t('negative_prompt')}>
              <textarea
                className="input min-h-16 font-mono text-xs"
                rows={2}
                value={value.negative_prompt}
                onChange={(e) => onChange({ negative_prompt: e.target.value })}
              />
            </Field>
          </>
        )}
      </div>
    </SectionCard>
  )
}

export function RenderSection({ value, onChange }: Omit<SectionProps<RenderConfig>, 'beforeTest'>) {
  const { t } = useLang()
  return (
    <SectionCard title={t('sec_render')} description={t('sec_render_desc')}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('font_path')} className="sm:col-span-2">
          <input
            className="input font-mono"
            value={value.font_path}
            placeholder="C:\\Windows\\Fonts\\msjh.ttc"
            onChange={(e) => onChange({ font_path: e.target.value })}
          />
        </Field>
        <Field label={t('subtitle_size')}>
          <NumberInput
            value={value.subtitle_size}
            onChange={(subtitle_size) => onChange({ subtitle_size })}
            min={12}
            max={200}
            step={1}
          />
        </Field>
        <Field label={t('crf')}>
          <NumberInput value={value.crf} onChange={(crf) => onChange({ crf })} min={0} max={51} step={1} />
        </Field>
        <Field label={t('bgm_volume')} right={`${Math.round(value.bgm_volume * 100)}%`} className="sm:col-span-2">
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value.bgm_volume}
            onChange={(e) => onChange({ bgm_volume: Number(e.target.value) })}
          />
        </Field>
      </div>
    </SectionCard>
  )
}
