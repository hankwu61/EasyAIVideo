import { useEffect, useRef, useState, type FocusEvent } from 'react'
import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react'
import { useLang } from '../i18n'
import type { SceneLine } from '../types'
import { formatSeconds } from '../utils'

function sameLines(a: SceneLine[], b: SceneLine[]) {
  if (a.length !== b.length) return false
  return a.every((l, i) => l.speaker === b[i].speaker && l.text === b[i].text)
}

/**
 * Drama-mode editor: one row per line (speaker + text). Text edits save when focus leaves the
 * editor; structural changes (add / remove / move) save immediately.
 */
export default function LinesEditor({
  lines,
  speakers,
  disabled,
  onSave,
}: {
  lines: SceneLine[]
  /** Character names from the series; null = unknown, use a free-text speaker input. */
  speakers: string[] | null
  disabled: boolean
  onSave: (lines: SceneLine[]) => Promise<boolean>
}) {
  const { t } = useLang()
  const [draft, setDraft] = useState<SceneLine[]>(lines)
  const dirty = useRef(false)
  const focused = useRef(false)
  const container = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!dirty.current && !focused.current) setDraft(lines)
  }, [lines])

  const save = async (next: SceneLine[]) => {
    if (sameLines(next, lines)) {
      dirty.current = false
      return
    }
    const ok = await onSave(next)
    if (ok) dirty.current = false
  }

  const edit = (i: number, patch: Partial<SceneLine>) => {
    dirty.current = true
    setDraft((d) => d.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  }

  const structural = (fn: (d: SceneLine[]) => SceneLine[]) => {
    const next = fn(draft)
    setDraft(next)
    dirty.current = true
    void save(next)
  }

  const onBlur = (e: FocusEvent<HTMLDivElement>) => {
    if (container.current?.contains(e.relatedTarget as Node | null)) return
    focused.current = false
    if (dirty.current) void save(draft)
  }

  const speakerOptions = speakers ?? []

  return (
    <div ref={container} onFocus={() => (focused.current = true)} onBlur={onBlur} className="space-y-1.5">
      {draft.length === 0 && <p className="text-xs text-faint">{t('lines_empty')}</p>}
      {draft.map((line, i) => {
        const unknownSpeaker = line.speaker && !speakerOptions.includes(line.speaker)
        return (
          <div key={i} className="flex items-center gap-1.5">
            {speakers ? (
              <select
                className="input w-32 shrink-0 text-xs"
                value={line.speaker ?? ''}
                disabled={disabled}
                title={t('speaker')}
                onChange={(e) => edit(i, { speaker: e.target.value || null })}
              >
                <option value="">{t('narrator')}</option>
                {unknownSpeaker && <option value={line.speaker ?? ''}>{line.speaker}</option>}
                {speakerOptions.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="input w-32 shrink-0 text-xs"
                placeholder={t('speaker_placeholder')}
                value={line.speaker ?? ''}
                disabled={disabled}
                onChange={(e) => edit(i, { speaker: e.target.value.trim() || null })}
              />
            )}
            <input
              className="input min-w-0 flex-1"
              placeholder={t('line_placeholder')}
              value={line.text}
              disabled={disabled}
              onChange={(e) => edit(i, { text: e.target.value })}
            />
            {line.duration != null && (
              <span className="w-10 shrink-0 text-right text-[11px] text-faint tabular-nums">{formatSeconds(line.duration)}</span>
            )}
            <button
              type="button"
              className="btn-ghost btn-icon h-7 w-7"
              disabled={disabled || i === 0}
              title={t('move_up')}
              aria-label={t('move_up')}
              onClick={() =>
                structural((d) => {
                  const n = [...d]
                  ;[n[i - 1], n[i]] = [n[i], n[i - 1]]
                  return n
                })
              }
            >
              <ChevronUp size={14} />
            </button>
            <button
              type="button"
              className="btn-ghost btn-icon h-7 w-7"
              disabled={disabled || i === draft.length - 1}
              title={t('move_down')}
              aria-label={t('move_down')}
              onClick={() =>
                structural((d) => {
                  const n = [...d]
                  ;[n[i], n[i + 1]] = [n[i + 1], n[i]]
                  return n
                })
              }
            >
              <ChevronDown size={14} />
            </button>
            <button
              type="button"
              className="btn-ghost btn-icon h-7 w-7 text-muted hover:text-danger"
              disabled={disabled}
              title={t('remove_line')}
              aria-label={t('remove_line')}
              onClick={() => structural((d) => d.filter((_, j) => j !== i))}
            >
              <Trash2 size={14} />
            </button>
          </div>
        )
      })}
      <button
        type="button"
        className="btn-ghost btn-sm"
        disabled={disabled}
        onClick={() => structural((d) => [...d, { speaker: null, text: '', duration: null }])}
      >
        <Plus size={13} />
        {t('add_line')}
      </button>
    </div>
  )
}
