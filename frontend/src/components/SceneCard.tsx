import { useEffect, useRef, useState } from 'react'
import {
  Check,
  ChevronDown,
  ChevronUp,
  Clapperboard,
  Clock,
  Download,
  ImageOff,
  MapPin,
  Mic,
  RefreshCw,
  ScanEye,
  Upload,
} from 'lucide-react'
import { useLang } from '../i18n'
import type { AspectRatio, AssetKind, ContentMode, Scene, ScenePatch, SceneReview, UploadKind } from '../types'
import { cx, formatSeconds } from '../utils'
import LinesEditor from './LinesEditor'
import { AI_VIDEO_MOTION } from './ProjectSettingsFields'
import SceneMenu from './SceneMenu'
import { SceneStatusDot, Spinner, StaleChip } from './ui'

export interface SceneActions {
  patch: (sceneId: string, body: ScenePatch) => Promise<boolean>
  regenerate: (sceneId: string, kinds: AssetKind[] | null) => Promise<void>
  upload: (sceneId: string, kind: UploadKind, file: File) => Promise<void>
  addBelow: (sceneId: string) => Promise<void>
  remove: (sceneId: string) => void
  move: (sceneId: string, dir: -1 | 1) => Promise<void>
}

interface SceneCardProps {
  scene: Scene
  index: number
  total: number
  aspect: AspectRatio
  busy: boolean
  actions: SceneActions
  contentMode?: ContentMode
  /** Character names for the drama speaker select; null = unknown (free text). */
  speakers?: string[] | null
  /** Project motion preset; 'ai_video' enables the video prompt / clip UI. */
  motion?: string
  /** AI review result for this scene, when a review exists. */
  review?: SceneReview | null
}

type TextField = 'narration' | 'image_prompt' | 'video_prompt'

const thumbWidth: Record<AspectRatio, string> = {
  '9:16': 'w-28 sm:w-32',
  '16:9': 'w-48 sm:w-60',
  '1:1': 'w-36 sm:w-40',
}
const thumbAspect: Record<AspectRatio, string> = { '9:16': '9 / 16', '16:9': '16 / 9', '1:1': '1 / 1' }

/** Editable textarea whose local draft is only replaced by server data while it is not focused. */
function useDraft(serverValue: string) {
  const [value, setValue] = useState(serverValue)
  const focused = useRef(false)
  useEffect(() => {
    if (!focused.current) setValue(serverValue)
  }, [serverValue])
  return { value, setValue, focused }
}

export default function SceneCard({
  scene,
  index,
  total,
  aspect,
  busy,
  actions,
  contentMode = 'narration',
  speakers = null,
  motion,
  review = null,
}: SceneCardProps) {
  const { t } = useLang()
  const drafts = {
    narration: useDraft(scene.narration),
    image_prompt: useDraft(scene.image_prompt),
    video_prompt: useDraft(scene.video_prompt ?? ''),
  }
  const [savedFlash, setSavedFlash] = useState<TextField | null>(null)
  const [uploading, setUploading] = useState<UploadKind | null>(null)
  const [working, setWorking] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const imageInput = useRef<HTMLInputElement>(null)
  const audioInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!savedFlash) return
    const id = window.setTimeout(() => setSavedFlash(null), 1500)
    return () => window.clearTimeout(id)
  }, [savedFlash])

  const commit = async (field: TextField) => {
    const draft = drafts[field]
    draft.focused.current = false
    const original = scene[field] ?? ''
    if (draft.value === original) return
    const ok = await actions.patch(scene.id, { [field]: draft.value })
    if (ok) setSavedFlash(field)
  }

  const run = async (fn: () => Promise<void>) => {
    setWorking(true)
    try {
      await fn()
    } finally {
      setWorking(false)
    }
  }

  const onFile = async (kind: UploadKind, file: File | undefined) => {
    if (!file) return
    setUploading(kind)
    try {
      await actions.upload(scene.id, kind, file)
    } finally {
      setUploading(null)
    }
  }

  const disabled = busy || working
  const drama = contentMode === 'drama'
  const aiVideo = motion === AI_VIDEO_MOTION
  const label = (field: TextField, text: string) => (
    <div className="mb-1 flex items-center justify-between">
      <span className="text-[11px] font-medium tracking-wide text-muted">{text}</span>
      {savedFlash === field && (
        <span className="inline-flex items-center gap-1 text-[11px] text-success animate-fade-in">
          <Check size={11} />
          {t('saved')}
        </span>
      )}
    </div>
  )
  const textarea = (field: 'image_prompt' | 'video_prompt', placeholder: string) => {
    const draft = drafts[field]
    return (
      <textarea
        className="input min-h-14 font-mono text-xs"
        rows={2}
        placeholder={placeholder}
        value={draft.value}
        onFocus={() => (draft.focused.current = true)}
        onChange={(e) => draft.setValue(e.target.value)}
        onBlur={() => void commit(field)}
      />
    )
  }

  return (
    <div
      id={`scene-${scene.id}`}
      className={cx(
        'card relative flex gap-4 p-4 transition',
        scene.status === 'failed' && 'border-danger/30',
        working && 'opacity-70',
      )}
    >
      {/* Thumbnail */}
      <div className={cx('relative shrink-0 space-y-2', thumbWidth[aspect])}>
        <div
          className={cx(
            'relative w-full overflow-hidden rounded-lg border bg-bg-elev transition',
            dragOver ? 'border-accent ring-2 ring-accent/40' : 'border-border',
          )}
          style={{ aspectRatio: thumbAspect[aspect] }}
          onDragOver={(e) => {
            if (disabled) return
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            if (disabled) return
            const file = e.dataTransfer.files?.[0]
            if (file && file.type.startsWith('image/')) void onFile('image', file)
          }}
          title={t('drop_image_hint')}
        >
          {scene.image_url ? (
            <a href={scene.image_url} target="_blank" rel="noreferrer" title={t('open_image')}>
              <img src={scene.image_url} alt="" className="h-full w-full object-cover" loading="lazy" />
            </a>
          ) : (
            <div className="grid h-full w-full place-items-center border-2 border-dashed border-border-strong text-faint">
              <div className="flex flex-col items-center gap-1 text-[11px]">
                <ImageOff size={18} strokeWidth={1.5} />
                {t('no_image')}
              </div>
            </div>
          )}
          <span className="absolute top-1.5 left-1.5 grid h-6 min-w-6 place-items-center rounded-md bg-black/60 px-1.5 text-[11px] font-semibold text-white backdrop-blur">
            {index + 1}
          </span>
          {scene.image_stale && (
            <span className="absolute right-1.5 bottom-1.5">
              <StaleChip />
            </span>
          )}
          {uploading === 'image' && (
            <div className="absolute inset-0 grid place-items-center bg-black/50 text-white">
              <Spinner />
            </div>
          )}
        </div>

        {/* Image toolbar: regenerate / upload / download */}
        <div className="grid grid-cols-3 gap-1">
          <button
            type="button"
            className="btn-ghost btn-icon h-7 w-full"
            disabled={disabled}
            onClick={() => void run(() => actions.regenerate(scene.id, ['image']))}
            title={t('regen_image')}
            aria-label={t('regen_image')}
          >
            <RefreshCw size={13} />
          </button>
          <button
            type="button"
            className="btn-ghost btn-icon h-7 w-full"
            disabled={disabled}
            onClick={() => imageInput.current?.click()}
            title={t('upload_image')}
            aria-label={t('upload_image')}
          >
            <Upload size={13} />
          </button>
          {scene.image_url ? (
            <a
              className="btn-ghost btn-icon h-7 w-full"
              href={`${scene.image_url}?download=${encodeURIComponent(`scene${String(index + 1).padStart(2, '0')}`)}`}
              download
              title={t('download_image')}
              aria-label={t('download_image')}
            >
              <Download size={13} />
            </a>
          ) : (
            <button type="button" className="btn-ghost btn-icon h-7 w-full" disabled title={t('download_image')}>
              <Download size={13} />
            </button>
          )}
        </div>

        {aiVideo &&
          (scene.video_url ? (
            <video
              key={scene.video_url}
              src={scene.video_url}
              controls
              muted
              playsInline
              preload="metadata"
              className="w-full rounded-lg border border-border bg-black"
              style={{ aspectRatio: thumbAspect[aspect] }}
            />
          ) : (
            <div className="grid w-full place-items-center rounded-lg border-2 border-dashed border-border-strong px-2 py-3 text-faint">
              <div className="flex flex-col items-center gap-1 text-center text-[11px]">
                <Clapperboard size={16} strokeWidth={1.5} />
                {t('no_video')}
              </div>
            </div>
          ))}
      </div>

      {/* Body */}
      <div className="min-w-0 flex-1 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <SceneStatusDot status={scene.status} error={scene.error} />
          <span className="inline-flex items-center gap-1 text-[11px] text-muted tabular-nums">
            <Clock size={11} />
            {formatSeconds(scene.duration)}
          </span>
          {scene.location && (
            <span className="chip border-border-strong bg-panel-2 text-muted" title={t('location_chip')}>
              <MapPin size={10} />
              {scene.location}
            </span>
          )}
          {aiVideo && scene.video_stale && <StaleChip label={t('video_stale')} />}
          {review && review.issues.length > 0 && (
            <span
              className={cx(
                'chip',
                review.score <= 2 ? 'border-danger/40 bg-danger/10 text-danger' : 'border-warning/40 bg-warning/10 text-warning',
              )}
              title={review.issues[0]}
            >
              <ScanEye size={10} />
              {t('review_scene_chip', { n: review.issues.length })}
            </span>
          )}
          <span className="ml-auto flex items-center gap-1">
            <button
              type="button"
              className="btn-ghost btn-icon h-7 w-7"
              disabled={disabled || index === 0}
              onClick={() => void run(() => actions.move(scene.id, -1))}
              title={t('move_up')}
              aria-label={t('move_up')}
            >
              <ChevronUp size={15} />
            </button>
            <button
              type="button"
              className="btn-ghost btn-icon h-7 w-7"
              disabled={disabled || index === total - 1}
              onClick={() => void run(() => actions.move(scene.id, 1))}
              title={t('move_down')}
              aria-label={t('move_down')}
            >
              <ChevronDown size={15} />
            </button>
            <SceneMenu
              disabled={disabled}
              working={working}
              aiVideo={aiVideo}
              onRegenerate={(kinds) => void run(() => actions.regenerate(scene.id, kinds))}
              onUploadImage={() => imageInput.current?.click()}
              onUploadAudio={() => audioInput.current?.click()}
              onAddBelow={() => void run(() => actions.addBelow(scene.id))}
              onRemove={() => actions.remove(scene.id)}
            />
          </span>
        </div>

        {drama ? (
          <div>
            {label('narration', t('lines'))}
            <LinesEditor
              lines={scene.lines ?? []}
              speakers={speakers}
              disabled={disabled}
              onSave={async (lines) => {
                const ok = await actions.patch(scene.id, { lines })
                if (ok) setSavedFlash('narration')
                return ok
              }}
            />
          </div>
        ) : (
          <div>
            {label('narration', t('narration'))}
            <textarea
              className="input min-h-16"
              rows={2}
              placeholder={t('narration_placeholder')}
              value={drafts.narration.value}
              onFocus={() => (drafts.narration.focused.current = true)}
              onChange={(e) => drafts.narration.setValue(e.target.value)}
              onBlur={() => void commit('narration')}
            />
          </div>
        )}

        <div>
          {label('image_prompt', t('image_prompt'))}
          {textarea('image_prompt', t('image_prompt_placeholder'))}
        </div>

        {aiVideo && (
          <div>
            {label('video_prompt', t('video_prompt'))}
            {textarea('video_prompt', t('video_prompt_placeholder'))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {scene.audio_url ? (
            <audio controls preload="none" src={scene.audio_url} className="h-8 min-w-0 flex-1" key={scene.audio_url} />
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-border-strong px-2.5 py-1.5 text-[11px] text-faint">
              <Mic size={12} />
              {t('no_audio')}
            </span>
          )}
          {uploading === 'audio' && <Spinner size={14} className="text-muted" />}
          {scene.audio_stale && <StaleChip />}
        </div>

        {scene.status === 'failed' && scene.error && (
          <p className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger break-words">
            {scene.error}
          </p>
        )}
      </div>

      <input
        ref={imageInput}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => {
          void onFile('image', e.target.files?.[0])
          e.target.value = ''
        }}
      />
      <input
        ref={audioInput}
        type="file"
        accept="audio/*"
        className="hidden"
        onChange={(e) => {
          void onFile('audio', e.target.files?.[0])
          e.target.value = ''
        }}
      />
    </div>
  )
}
