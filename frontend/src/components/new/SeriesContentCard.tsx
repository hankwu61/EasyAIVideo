import { useRef, useState, type DragEvent } from 'react'
import { FileText, UploadCloud, X } from 'lucide-react'
import { useLang } from '../../i18n'
import type { ContentMode, IdLabel } from '../../types'
import { cx, formatBytes } from '../../utils'
import { SOURCE_ACCEPT } from '../series/SourceSection'
import { Field, SectionCard } from '../ui'

/** Fallback when the backend does not return `presets.content_modes`. */
export const DEFAULT_CONTENT_MODES: IdLabel[] = [
  { id: 'narration', label: '旁白解說' },
  { id: 'drama', label: '劇情演繹（角色對白）' },
]

export interface SeriesContent {
  source_file: File | null
  source_text: string
  title: string
  language: string
  content_mode: ContentMode
  episode_target_seconds: number
}

const ACCEPTED_EXT = SOURCE_ACCEPT.split(',')

export function formatTarget(sec: number, t: ReturnType<typeof useLang>['t']): string {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  if (m === 0) return t('seconds_short', { s })
  if (s === 0) return t('minutes_short', { m })
  return t('minutes_seconds_short', { m, s })
}

export default function SeriesContentCard({
  value,
  onChange,
  languages,
  contentModes,
}: {
  value: SeriesContent
  onChange: (patch: Partial<SeriesContent>) => void
  languages: IdLabel[]
  contentModes: IdLabel[]
}) {
  const { t, lang } = useLang()
  const fileInput = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  const pick = (file: File | undefined) => {
    if (!file) return
    const ext = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
    if (!ACCEPTED_EXT.includes(ext)) return
    onChange({ source_file: file })
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files?.[0])
  }

  return (
    <SectionCard title={t('section_content')}>
      <div className="space-y-4">
        <Field label={t('source_label')} hint={t('source_accept_hint')}>
          {value.source_file ? (
            <div className="flex items-center gap-3 rounded-lg border border-accent/40 bg-accent/10 px-3 py-2.5 text-sm">
              <FileText size={16} className="shrink-0 text-accent" />
              <span className="min-w-0 flex-1 truncate">{value.source_file.name}</span>
              <span className="shrink-0 text-xs text-muted tabular-nums">{formatBytes(value.source_file.size)}</span>
              <button
                type="button"
                className="btn-ghost btn-icon h-7 w-7"
                onClick={() => onChange({ source_file: null })}
                aria-label={t('remove_file')}
                title={t('remove_file')}
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <div
              role="button"
              tabIndex={0}
              onClick={() => fileInput.current?.click()}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') fileInput.current?.click()
              }}
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cx(
                'flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition',
                dragging
                  ? 'border-accent bg-accent/10 text-text'
                  : 'border-border-strong bg-bg-elev text-muted hover:border-accent/60 hover:text-text',
              )}
            >
              <UploadCloud size={26} strokeWidth={1.5} className={dragging ? 'text-accent' : ''} />
              <span className="text-sm">{t('source_drop_hint')}</span>
              <span className="btn-secondary btn-sm pointer-events-none">{t('source_choose_file')}</span>
            </div>
          )}
          <input
            ref={fileInput}
            type="file"
            accept={SOURCE_ACCEPT}
            className="hidden"
            onChange={(e) => {
              pick(e.target.files?.[0])
              e.target.value = ''
            }}
          />
        </Field>

        {!value.source_file && (
          <Field label={t('source_or_paste')}>
            <textarea
              className="input min-h-40"
              rows={8}
              placeholder={t('source_paste_placeholder')}
              value={value.source_text}
              onChange={(e) => onChange({ source_text: e.target.value })}
            />
          </Field>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={`${t('title_label')} · ${t('optional')}`}>
            <input
              className="input"
              placeholder={t('title_placeholder')}
              value={value.title}
              onChange={(e) => onChange({ title: e.target.value })}
            />
          </Field>
          <Field label={t('language')}>
            <select className="input" value={value.language} onChange={(e) => onChange({ language: e.target.value })}>
              {languages.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field label={t('content_mode')}>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {contentModes.map((m) => {
              const active = m.id === value.content_mode
              const known = m.id === 'narration' ? 'narration' : m.id === 'drama' ? 'drama' : null
              const label = lang === 'en' && known ? t(`content_mode_${known}`) : m.label
              return (
                <label
                  key={m.id}
                  className={cx(
                    'flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 text-sm transition',
                    active
                      ? 'border-accent bg-accent/10 text-text'
                      : 'border-border bg-bg-elev text-muted hover:border-border-strong hover:text-text',
                  )}
                >
                  <input
                    type="radio"
                    name="content_mode"
                    value={m.id}
                    checked={active}
                    onChange={() => onChange({ content_mode: m.id as ContentMode })}
                    className="mt-1 accent-accent"
                  />
                  <span className="min-w-0">
                    <span className="block font-medium">{label}</span>
                    {known && (
                      <span className="mt-0.5 block text-[11px] leading-relaxed text-faint">
                        {t(`content_mode_${known}_desc`)}
                      </span>
                    )}
                  </span>
                </label>
              )
            })}
          </div>
        </Field>

        <Field label={t('episode_target')} right={formatTarget(value.episode_target_seconds, t)}>
          <input
            type="range"
            min={30}
            max={600}
            step={15}
            value={value.episode_target_seconds}
            onChange={(e) => onChange({ episode_target_seconds: Number(e.target.value) })}
          />
        </Field>
      </div>
    </SectionCard>
  )
}
