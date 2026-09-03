import { Clapperboard, FileAudio, ImagePlus, Mic, MoreHorizontal, Plus, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
import { useLang } from '../i18n'
import type { AssetKind } from '../types'
import Menu from './Menu'
import { Spinner } from './ui'

/** Overflow menu on a scene card. `aiVideo` adds the "regenerate video" entry. */
export default function SceneMenu({
  disabled,
  working,
  aiVideo,
  onRegenerate,
  onUploadImage,
  onUploadAudio,
  onAddBelow,
  onRemove,
}: {
  disabled: boolean
  working: boolean
  aiVideo: boolean
  onRegenerate: (kinds: AssetKind[] | null) => void
  onUploadImage: () => void
  onUploadAudio: () => void
  onAddBelow: () => void
  onRemove: () => void
}) {
  const { t } = useLang()
  const item = (close: () => void, action: () => void) => () => {
    close()
    action()
  }
  return (
    <Menu
      trigger={({ onClick }) => (
        <button
          type="button"
          className="btn-ghost btn-icon h-7 w-7"
          onClick={onClick}
          disabled={disabled}
          aria-label={t('scene_menu')}
          title={t('scene_menu')}
        >
          {working ? <Spinner size={14} /> : <MoreHorizontal size={15} />}
        </button>
      )}
    >
      {(close) => (
        <>
          <button className="menu-item" onClick={item(close, () => onRegenerate(['image']))}>
            <RefreshCw size={14} /> {t('regen_image')}
          </button>
          <button className="menu-item" onClick={item(close, () => onRegenerate(['audio']))}>
            <Mic size={14} /> {t('regen_audio')}
          </button>
          {aiVideo && (
            <button className="menu-item" onClick={item(close, () => onRegenerate(['video']))}>
              <Clapperboard size={14} /> {t('regen_video')}
            </button>
          )}
          <button className="menu-item" onClick={item(close, () => onRegenerate(null))}>
            <Sparkles size={14} /> {t('regen_all')}
          </button>
          <div className="menu-sep" />
          <button className="menu-item" onClick={item(close, onUploadImage)}>
            <ImagePlus size={14} /> {t('upload_image')}
          </button>
          <button className="menu-item" onClick={item(close, onUploadAudio)}>
            <FileAudio size={14} /> {t('upload_audio')}
          </button>
          <div className="menu-sep" />
          <button className="menu-item" onClick={item(close, onAddBelow)}>
            <Plus size={14} /> {t('add_scene_below')}
          </button>
          <button className="menu-item text-danger hover:bg-danger/10" onClick={item(close, onRemove)}>
            <Trash2 size={14} /> {t('delete_scene')}
          </button>
        </>
      )}
    </Menu>
  )
}
