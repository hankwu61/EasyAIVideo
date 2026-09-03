import { BookOpen, Check, Clapperboard } from 'lucide-react'
import { useLang } from '../../i18n'
import type { IdLabel, ProjectKind } from '../../types'
import { cx } from '../../utils'

/** Fallback when the backend does not return `presets.kinds`. */
export const DEFAULT_KINDS: IdLabel[] = [
  { id: 'single', label: '短影片（主題／文稿）' },
  { id: 'series', label: '長文／小說 → 分集影片' },
]

const icons: Record<string, typeof Clapperboard> = { single: Clapperboard, series: BookOpen }

export default function KindPicker({
  kinds,
  value,
  onChange,
}: {
  kinds: IdLabel[]
  value: ProjectKind
  onChange: (k: ProjectKind) => void
}) {
  const { t, lang } = useLang()
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {kinds.map((k) => {
        const Icon = icons[k.id] ?? Clapperboard
        const active = k.id === value
        const known = k.id === 'single' ? 'single' : k.id === 'series' ? 'series' : null
        const label = lang === 'en' && known ? t(`kind_${known}_label`) : k.label
        const desc = known ? t(`kind_${known}_desc`) : ''
        return (
          <button
            key={k.id}
            type="button"
            onClick={() => onChange(k.id as ProjectKind)}
            className={cx(
              'relative flex items-start gap-3 rounded-xl border p-4 text-left transition',
              active
                ? 'border-accent bg-accent/10 shadow-[0_0_0_1px_rgb(124_108_255/0.5)]'
                : 'border-border bg-panel hover:border-border-strong',
            )}
          >
            <span
              className={cx(
                'grid h-10 w-10 shrink-0 place-items-center rounded-lg',
                active ? 'bg-accent text-white' : 'bg-panel-2 text-muted',
              )}
            >
              <Icon size={20} />
            </span>
            <span className="min-w-0">
              <span className="block text-[15px] font-semibold">{label}</span>
              {desc && <span className="mt-0.5 block text-xs leading-relaxed text-muted">{desc}</span>}
            </span>
            {active && (
              <span className="absolute top-2.5 right-2.5 grid h-5 w-5 place-items-center rounded-full bg-accent text-white">
                <Check size={12} strokeWidth={3} />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
