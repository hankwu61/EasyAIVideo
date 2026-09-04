import { useLang } from '../../i18n'
import type { ReviewConfig } from '../../types'
import { Field, SectionCard } from '../ui'
import { NumberInput, SecretInput } from './ProviderSections'
import TestButton from './TestButton'

export default function ReviewSection({
  value,
  onChange,
  beforeTest,
}: {
  value: ReviewConfig
  onChange: (patch: Partial<ReviewConfig>) => void
  beforeTest: () => Promise<boolean>
}) {
  const { t } = useLang()
  const fallback = t('review_fallback_hint')
  return (
    <SectionCard
      title={t('sec_review')}
      description={t('sec_review_desc')}
      actions={<TestButton kind="review" beforeTest={beforeTest} />}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('api_key')} hint={`${fallback} ${t('api_key_hint')}`} className="sm:col-span-2">
          <SecretInput value={value.api_key} onChange={(api_key) => onChange({ api_key })} placeholder={fallback} />
        </Field>
        <Field label={t('base_url')} hint={fallback}>
          <input
            className="input font-mono"
            value={value.base_url}
            placeholder={fallback}
            onChange={(e) => onChange({ base_url: e.target.value })}
          />
        </Field>
        <Field label={t('model')} hint={fallback}>
          <input
            className="input font-mono"
            value={value.model}
            placeholder={fallback}
            onChange={(e) => onChange({ model: e.target.value })}
          />
        </Field>
        <Field label={t('review_frames_per_scene')}>
          <NumberInput
            value={value.frames_per_scene}
            onChange={(frames_per_scene) => onChange({ frames_per_scene })}
            min={1}
            max={3}
            step={1}
          />
        </Field>
        <Field label={t('review_frame_width')}>
          <NumberInput
            value={value.frame_width}
            onChange={(frame_width) => onChange({ frame_width })}
            min={256}
            max={1920}
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
      </div>
    </SectionCard>
  )
}
