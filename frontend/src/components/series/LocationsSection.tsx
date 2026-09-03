import { MapPin, Plus, Trash2 } from 'lucide-react'
import { errorMessage, patchProject } from '../../api'
import { useLang } from '../../i18n'
import type { Location, Project } from '../../types'
import { useToast } from '../Toast'
import { SectionCard } from '../ui'
import { useSyncedList, type Keyed } from './useSyncedList'

interface LocalLocation extends Keyed, Location {}

let seq = 0
const newKey = () => `new-${++seq}`

export default function LocationsSection({
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

  const { items, update } = useSyncedList<LocalLocation>({
    project,
    fromProject: (p) => p.locations.map((l, i) => ({ key: `loc-${i}`, name: l.name, description: l.description })),
    save: (list) =>
      patchProject(project.id, { locations: list.map(({ name, description }) => ({ name, description })) }),
    onProject,
    onError: (e) => toast.error(errorMessage(e)),
    onSaved: () => toast.success(t('locations_saved')),
  })

  const edit = (key: string, patch: Partial<Location>) =>
    update((list) => list.map((l) => (l.key === key ? { ...l, ...patch } : l)))

  return (
    <SectionCard
      title={t('section_locations')}
      actions={
        <button
          type="button"
          className="btn-secondary btn-sm"
          disabled={disabled}
          onClick={() => update((list) => [...list, { key: newKey(), name: '', description: '' }])}
        >
          <Plus size={13} />
          {t('add_location')}
        </button>
      }
    >
      {items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border-strong px-4 py-6 text-center text-sm text-muted">
          {t('locations_empty')}
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((loc) => (
            <li
              key={loc.key}
              className="grid grid-cols-1 items-start gap-2 rounded-lg border border-border bg-bg-elev p-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]"
            >
              <div className="relative">
                <MapPin size={13} className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-faint" />
                <input
                  className="input pl-8"
                  placeholder={t('location_name_placeholder')}
                  value={loc.name}
                  disabled={disabled}
                  onChange={(e) => edit(loc.key, { name: e.target.value })}
                />
              </div>
              <input
                className="input"
                placeholder={t('location_desc_placeholder')}
                value={loc.description}
                disabled={disabled}
                onChange={(e) => edit(loc.key, { description: e.target.value })}
              />
              <button
                type="button"
                className="btn-ghost btn-icon text-muted hover:text-danger"
                disabled={disabled}
                title={t('delete')}
                aria-label={t('delete')}
                onClick={() => update((list) => list.filter((l) => l.key !== loc.key))}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
