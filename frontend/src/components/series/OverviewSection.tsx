import { useEffect, useRef, useState } from 'react'
import { ScanSearch } from 'lucide-react'
import { errorMessage, patchProject } from '../../api'
import { useLang } from '../../i18n'
import type { Overview, Project } from '../../types'
import { useToast } from '../Toast'
import { Field, SectionCard } from '../ui'

const EMPTY: Overview = { synopsis: '', genre: '', theme: '', world_setting: '' }
const DEBOUNCE_MS = 600

function same(a: Overview, b: Overview) {
  return a.synopsis === b.synopsis && a.genre === b.genre && a.theme === b.theme && a.world_setting === b.world_setting
}

export default function OverviewSection({
  project,
  disabled,
  onProject,
}: {
  project: Project
  disabled: boolean
  onProject: (p: Project) => void
}) {
  const { t } = useLang()
  const toast = useToast()
  const server = project.overview
  const [local, setLocal] = useState<Overview>(server ?? EMPTY)
  const dirty = useRef(false)
  const focused = useRef(false)
  const timer = useRef<number | null>(null)
  const latest = useRef(local)
  latest.current = local

  useEffect(() => {
    if (!dirty.current && !focused.current) setLocal(server ?? EMPTY)
  }, [server])

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )

  const flush = async () => {
    timer.current = null
    if (!dirty.current) return
    dirty.current = false
    const value = latest.current
    try {
      const updated = await patchProject(project.id, { overview: value })
      onProject(updated)
      toast.success(t('overview_saved'))
    } catch (e) {
      dirty.current = true
      toast.error(errorMessage(e))
    }
  }

  const onBlur = () => {
    focused.current = false
    if (server ? same(latest.current, server) : same(latest.current, EMPTY)) return
    dirty.current = true
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => void flush(), DEBOUNCE_MS)
  }

  const edit = (patch: Partial<Overview>) => setLocal((o) => ({ ...o, ...patch }))

  if (!server) {
    return (
      <SectionCard title={t('section_overview')}>
        <div className="flex flex-col items-center px-6 py-10 text-center">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-accent/15 text-accent">
            <ScanSearch size={22} />
          </span>
          <p className="mt-3 max-w-sm text-sm text-muted">{t('overview_empty')}</p>
        </div>
      </SectionCard>
    )
  }

  const common = {
    disabled,
    onFocus: () => (focused.current = true),
    onBlur,
  }

  return (
    <SectionCard title={t('section_overview')}>
      <div className="space-y-4">
        <Field label={t('synopsis')}>
          <textarea
            className="input min-h-24"
            rows={4}
            value={local.synopsis}
            onChange={(e) => edit({ synopsis: e.target.value })}
            {...common}
          />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('genre')}>
            <input className="input" value={local.genre} onChange={(e) => edit({ genre: e.target.value })} {...common} />
          </Field>
          <Field label={t('theme')}>
            <input className="input" value={local.theme} onChange={(e) => edit({ theme: e.target.value })} {...common} />
          </Field>
        </div>
        <Field label={t('world_setting')}>
          <textarea
            className="input min-h-20"
            rows={3}
            value={local.world_setting}
            onChange={(e) => edit({ world_setting: e.target.value })}
            {...common}
          />
        </Field>
      </div>
    </SectionCard>
  )
}
