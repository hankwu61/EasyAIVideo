import { useState } from 'react'
import { Download, Film, HardDrive, Scissors, Sparkles, Timer } from 'lucide-react'
import { getProjectSubtitles } from '../api'
import { useLang } from '../i18n'
import type { Project } from '../types'
import { formatBytes, formatDuration } from '../utils'
import TextExportMenu from './TextExportMenu'
import VideoStudioModal from './VideoStudioModal'

export default function PreviewPanel({ project }: { project: Project }) {
  const { t } = useLang()
  const [studioOpen, setStudioOpen] = useState(false)
  const url = project.final_video_url
  const portrait = project.aspect_ratio === '9:16'

  const hint =
    project.status === 'draft' || project.scenes.length === 0
      ? t('preview_empty_draft')
      : project.status === 'scripted'
        ? t('preview_empty_scripted')
        : t('preview_empty_assets')

  const handleDownloadSrtDirect = async () => {
    if (project.subtitles_url) {
      const a = document.createElement('a')
      a.href = project.subtitles_url
      a.download = `${project.title || 'subtitles'}.srt`
      a.click()
      return
    }
    try {
      const cues = await getProjectSubtitles(project.id)
      if (cues.length === 0) return
      const formatTime = (secs: number) => {
        const h = Math.floor(secs / 3600)
        const m = Math.floor((secs % 3600) / 60)
        const s = Math.floor(secs % 60)
        const ms = Math.floor((secs - Math.floor(secs)) * 1000)
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`
      }
      const blocks = cues.map((cue, i) => `${i + 1}\n${formatTime(cue.start)} --> ${formatTime(cue.end)}\n${cue.text.trim()}`)
      const blob = new Blob([blocks.join('\n\n') + '\n'], { type: 'text/plain;charset=utf-8' })
      const blobUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = `${project.title || 'subtitles'}.srt`
      a.click()
      URL.revokeObjectURL(blobUrl)
    } catch {
      /* ignore */
    }
  }

  return (
    <>
      <section className="card overflow-hidden">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold">{t('preview')}</h2>
          <div className="flex items-center gap-1.5">
            {url && (
              <button
                onClick={() => setStudioOpen(true)}
                className="btn-primary btn-sm gap-1 text-xs"
                title="編輯影片聲音、字幕、波形與剪輯"
              >
                <Scissors size={13} />
                影音字幕剪輯
              </button>
            )}
            {(project.subtitles_url || project.scenes.length > 0) && (
              <button
                onClick={handleDownloadSrtDirect}
                className="btn-ghost btn-sm gap-1 text-xs"
                title="下載字幕檔 (SRT)"
              >
                <Download size={13} />
                下載字幕 (SRT)
              </button>
            )}
            {project.scenes.length > 0 && <TextExportMenu project={project} compact />}
            {url && (
              <a href={url} download={`${project.title || 'video'}.mp4`} className="btn-secondary btn-sm gap-1 text-xs">
                <Download size={13} />
                下載影片 (MP4)
              </a>
            )}
          </div>
        </div>

        {url ? (
          <div>
            <div className="grid place-items-center bg-black">
              <video
                key={url}
                controls
                preload="metadata"
                src={url}
                className={portrait ? 'max-h-[480px] w-auto' : 'w-full'}
                style={{ aspectRatio: portrait ? '9 / 16' : project.aspect_ratio === '1:1' ? '1 / 1' : '16 / 9' }}
              />
            </div>
            <div className="grid grid-cols-2 gap-2 p-4 text-xs">
              <div className="rounded-lg border border-border bg-bg-elev px-3 py-2">
                <div className="flex items-center gap-1 text-faint">
                  <Timer size={11} />
                  {t('duration_label')}
                </div>
                <div className="mt-0.5 text-sm font-semibold tabular-nums">{formatDuration(project.final_video_duration)}</div>
              </div>
              <div className="rounded-lg border border-border bg-bg-elev px-3 py-2">
                <div className="flex items-center gap-1 text-faint">
                  <HardDrive size={11} />
                  {t('preview_size')}
                </div>
                <div className="mt-0.5 text-sm font-semibold tabular-nums">{formatBytes(project.final_video_size)}</div>
              </div>
            </div>
            <div className="border-t border-border px-4 py-2.5 bg-bg-elev/40 flex justify-between items-center">
              <span className="text-[11px] text-muted flex items-center gap-1">
                <Sparkles size={12} className="text-primary" />
                支援綠色波形軌道、逐句字幕即時編輯與無損剪輯
              </span>
              <button
                onClick={() => setStudioOpen(true)}
                className="btn-ghost btn-sm text-xs text-primary hover:underline"
              >
                開啟剪輯工作台 →
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center px-6 py-10 text-center">
            <span className="grid h-12 w-12 place-items-center rounded-2xl border border-dashed border-border-strong text-faint">
              <Film size={22} strokeWidth={1.5} />
            </span>
            <p className="mt-3 max-w-xs text-xs leading-relaxed text-muted">{hint}</p>
          </div>
        )}
      </section>

      {studioOpen && (
        <VideoStudioModal
          project={project}
          onClose={() => setStudioOpen(false)}
          onProjectUpdated={() => {
            // refresh
          }}
        />
      )}
    </>
  )
}

