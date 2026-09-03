import { Download, Film, HardDrive, Timer } from 'lucide-react'
import { useLang } from '../i18n'
import type { Project } from '../types'
import { formatBytes, formatDuration } from '../utils'

export default function PreviewPanel({ project }: { project: Project }) {
  const { t } = useLang()
  const url = project.final_video_url
  const portrait = project.aspect_ratio === '9:16'

  const hint =
    project.status === 'draft' || project.scenes.length === 0
      ? t('preview_empty_draft')
      : project.status === 'scripted'
        ? t('preview_empty_scripted')
        : t('preview_empty_assets')

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">{t('preview')}</h2>
        {url && (
          <a href={url} download className="btn-secondary btn-sm">
            <Download size={13} />
            {t('download_video')}
          </a>
        )}
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
  )
}
