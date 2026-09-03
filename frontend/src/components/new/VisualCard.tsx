import { useLang } from '../../i18n'
import type { AspectRatio, AspectRatioPreset, StyleOption } from '../../types'
import { AspectRatioPicker } from '../ProjectSettingsFields'
import { Field, SectionCard } from '../ui'

export interface VisualSettings {
  style_id: string
  style_prompt: string
  aspect_ratio: AspectRatio
}

export default function VisualCard({
  value,
  onChange,
  styles,
  ratios,
}: {
  value: VisualSettings
  onChange: (patch: Partial<VisualSettings>) => void
  styles: StyleOption[]
  ratios: AspectRatioPreset[]
}) {
  const { t } = useLang()
  return (
    <SectionCard title={t('section_visual')}>
      <div className="space-y-4">
        <Field label={t('style')}>
          <select
            className="input"
            value={value.style_id}
            onChange={(e) => {
              const s = styles.find((x) => x.id === e.target.value)
              onChange({ style_id: e.target.value, style_prompt: s?.prompt ?? value.style_prompt })
            }}
          >
            {styles.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t('style_prompt')} hint={t('style_prompt_hint')}>
          <textarea
            className="input font-mono text-xs"
            rows={3}
            value={value.style_prompt}
            onChange={(e) => onChange({ style_prompt: e.target.value })}
          />
        </Field>
        <Field label={t('aspect_ratio')}>
          <AspectRatioPicker ratios={ratios} value={value.aspect_ratio} onChange={(aspect_ratio) => onChange({ aspect_ratio })} />
        </Field>
      </div>
    </SectionCard>
  )
}
