import { useEffect, useState } from 'react'
import { ImagePlus, Plus, Trash2, User } from 'lucide-react'
import { errorMessage, patchProject } from '../../api'
import { useLang } from '../../i18n'
import type { Character, CharacterGender, CharacterInput, Project, VoiceOption } from '../../types'
import { VoiceSelect } from '../ProjectSettingsFields'
import { useToast } from '../Toast'
import { Field, SectionCard, Spinner } from '../ui'
import { useSyncedList, type Keyed } from './useSyncedList'

interface LocalCharacter extends Keyed, Omit<Character, 'id'> {
  id?: string
}

const GENDERS: CharacterGender[] = ['female', 'male', 'other']
let seq = 0
const newKey = () => `new-${++seq}`

function toInput(c: LocalCharacter): CharacterInput {
  const { name, description, appearance, gender, voice } = c
  return c.id ? { id: c.id, name, description, appearance, gender, voice } : { name, description, appearance, gender, voice }
}

export default function CharactersSection({
  project,
  voices,
  busy,
  onProject,
  onGenerateImage,
}: {
  project: Project
  voices: VoiceOption[]
  busy: boolean
  onProject: (p: Project) => void
  /** Resolves true when the task was accepted. */
  onGenerateImage: (charId: string) => Promise<boolean>
}) {
  const { t } = useLang()
  const toast = useToast()
  const [pendingImage, setPendingImage] = useState<string | null>(null)

  const imageTaskRunning = project.active_task?.type === 'character_image'
  useEffect(() => {
    if (!imageTaskRunning) setPendingImage(null)
  }, [imageTaskRunning])

  const { items, update } = useSyncedList<LocalCharacter>({
    project,
    fromProject: (p) => p.characters.map((c) => ({ ...c, key: c.id })),
    save: (list) => patchProject(project.id, { characters: list.map(toInput) }),
    onProject,
    onError: (e) => toast.error(errorMessage(e)),
    onSaved: () => toast.success(t('characters_saved')),
  })

  const edit = (key: string, patch: Partial<LocalCharacter>) =>
    update((list) => list.map((c) => (c.key === key ? { ...c, ...patch } : c)))

  const add = () =>
    update((list) => [
      ...list,
      { key: newKey(), name: '', description: '', appearance: '', gender: 'other', voice: '', image_url: null },
    ])

  const genImage = async (c: LocalCharacter) => {
    if (!c.id) return
    setPendingImage(c.id)
    const ok = await onGenerateImage(c.id)
    if (!ok) setPendingImage(null)
  }

  return (
    <SectionCard
      title={t('section_characters')}
      actions={
        <button type="button" className="btn-secondary btn-sm" onClick={add}>
          <Plus size={13} />
          {t('add_character')}
        </button>
      }
    >
      {items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border-strong px-4 py-6 text-center text-sm text-muted">
          {t('characters_empty')}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((c) => {
            const generating = pendingImage !== null && pendingImage === c.id && imageTaskRunning
            return (
              <div key={c.key} className="flex flex-col gap-3 rounded-xl border border-border bg-bg-elev p-3">
                <div className="flex gap-3">
                  <div className="relative h-24 w-24 shrink-0 overflow-hidden rounded-lg border border-border bg-panel">
                    {c.image_url ? (
                      <img src={c.image_url} alt="" className="h-full w-full object-cover" loading="lazy" />
                    ) : (
                      <div className="grid h-full w-full place-items-center text-faint">
                        <User size={30} strokeWidth={1.25} />
                      </div>
                    )}
                    {generating && (
                      <div className="absolute inset-0 grid place-items-center bg-black/50 text-white">
                        <Spinner />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1 space-y-2">
                    <input
                      className="input font-semibold"
                      placeholder={t('character_name_placeholder')}
                      value={c.name}
                      onChange={(e) => edit(c.key, { name: e.target.value })}
                    />
                    <select
                      className="input"
                      value={c.gender}
                      onChange={(e) => edit(c.key, { gender: e.target.value as CharacterGender })}
                    >
                      {GENDERS.map((g) => (
                        <option key={g} value={g}>
                          {t(`gender_${g}` as const)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <Field label={t('description')}>
                  <textarea
                    className="input min-h-16"
                    rows={2}
                    placeholder={t('character_desc_placeholder')}
                    value={c.description}
                    onChange={(e) => edit(c.key, { description: e.target.value })}
                  />
                </Field>
                <Field label={t('appearance')}>
                  <textarea
                    className="input min-h-16 font-mono text-xs"
                    rows={3}
                    placeholder={t('appearance_placeholder')}
                    value={c.appearance}
                    onChange={(e) => edit(c.key, { appearance: e.target.value })}
                  />
                </Field>
                <Field label={t('voice')}>
                  <VoiceSelect voices={voices} value={c.voice} onChange={(voice) => edit(c.key, { voice })} />
                </Field>

                <div className="mt-auto flex items-center justify-between gap-2 pt-1">
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    disabled={busy || !c.id || generating}
                    title={!c.id ? t('saving') : undefined}
                    onClick={() => void genImage(c)}
                  >
                    {generating ? <Spinner size={12} /> : <ImagePlus size={13} />}
                    {generating ? t('generating') : t('gen_character_image')}
                  </button>
                  <button
                    type="button"
                    className="btn-ghost btn-sm text-muted hover:text-danger"
                    onClick={() => update((list) => list.filter((x) => x.key !== c.key))}
                  >
                    <Trash2 size={13} />
                    {t('delete')}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </SectionCard>
  )
}
