import { Archive, ChevronDown, Clapperboard, FileText, Image as ImageIcon, Mic } from 'lucide-react'
import { useLang } from '../i18n'
import type { Project } from '../types'
import { downloadProjectText } from '../utils/textExport'
import Menu from './Menu'

interface TextExportMenuProps {
  project: Project
  compact?: boolean
  className?: string
}

export default function TextExportMenu({ project, compact = false, className }: TextExportMenuProps) {
  const { t } = useLang()

  const handleExport = (close: () => void, kind: 'video_prompts' | 'image_prompts' | 'narration' | 'script') => {
    close()
    downloadProjectText(project, kind)
  }

  return (
    <Menu
      className={className}
      trigger={({ onClick }) => (
        <button
          type="button"
          onClick={onClick}
          className={
            compact
              ? 'btn-ghost btn-sm gap-1 text-xs'
              : 'btn-ghost btn-sm gap-1.5'
          }
          title="下載各類文字檔（提示詞、旁白）"
        >
          <FileText size={compact ? 13 : 14} />
          <span>{t('download_texts')}</span>
          <ChevronDown size={compact ? 11 : 12} className="opacity-60" />
        </button>
      )}
    >
      {(close) => (
        <div className="w-56 py-1">
          <button
            type="button"
            className="menu-item group flex items-start gap-2.5 px-3 py-2 text-left"
            onClick={() => handleExport(close, 'video_prompts')}
          >
            <Clapperboard size={15} className="mt-0.5 shrink-0 text-accent" />
            <div className="min-w-0">
              <div className="text-xs font-medium text-text">{t('download_video_prompts')}</div>
              <div className="text-[10px] text-muted">{t('download_video_prompts_desc')}</div>
            </div>
          </button>

          <button
            type="button"
            className="menu-item group flex items-start gap-2.5 px-3 py-2 text-left"
            onClick={() => handleExport(close, 'image_prompts')}
          >
            <ImageIcon size={15} className="mt-0.5 shrink-0 text-emerald-400" />
            <div className="min-w-0">
              <div className="text-xs font-medium text-text">{t('download_image_prompts')}</div>
              <div className="text-[10px] text-muted">{t('download_image_prompts_desc')}</div>
            </div>
          </button>

          <button
            type="button"
            className="menu-item group flex items-start gap-2.5 px-3 py-2 text-left"
            onClick={() => handleExport(close, 'narration')}
          >
            <Mic size={15} className="mt-0.5 shrink-0 text-amber-400" />
            <div className="min-w-0">
              <div className="text-xs font-medium text-text">{t('download_narration')}</div>
              <div className="text-[10px] text-muted">{t('download_narration_desc')}</div>
            </div>
          </button>

          <div className="menu-sep" />

          <button
            type="button"
            className="menu-item group flex items-start gap-2.5 px-3 py-2 text-left"
            onClick={() => handleExport(close, 'script')}
          >
            <FileText size={15} className="mt-0.5 shrink-0 text-primary" />
            <div className="min-w-0">
              <div className="text-xs font-medium text-text">{t('download_full_script')}</div>
              <div className="text-[10px] text-muted">{t('download_full_script_desc')}</div>
            </div>
          </button>

          <a
            href={`/api/projects/${project.id}/export/texts.zip`}
            download
            onClick={close}
            className="menu-item group flex items-start gap-2.5 px-3 py-2 text-left"
          >
            <Archive size={15} className="mt-0.5 shrink-0 text-purple-400" />
            <div className="min-w-0">
              <div className="text-xs font-medium text-text">{t('download_all_texts_zip')}</div>
              <div className="text-[10px] text-muted">包含以上所有提示詞與旁白</div>
            </div>
          </a>
        </div>
      )}
    </Menu>
  )
}
