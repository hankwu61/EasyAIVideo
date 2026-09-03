import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, FileText, Trash2, Upload } from 'lucide-react'
import { clearSource, errorMessage, getSource, uploadSource } from '../../api'
import { useLang } from '../../i18n'
import type { Project } from '../../types'
import ConfirmDialog from '../ConfirmDialog'
import { useToast } from '../Toast'
import { ErrorAlert, SectionCard, Spinner } from '../ui'

export const SOURCE_ACCEPT = '.txt,.md,.docx,.epub,.pdf'
const CHUNK = 3000

export default function SourceSection({
  project,
  busy,
  onProject,
}: {
  project: Project
  busy: boolean
  onProject: (p: Project) => void
}) {
  const { t } = useLang()
  const toast = useToast()
  const fileInput = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const [clearing, setClearing] = useState(false)

  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [total, setTotal] = useState<number | null>(null)
  const [loadingText, setLoadingText] = useState(false)
  const [textError, setTextError] = useState<string | null>(null)

  // Reset the preview whenever the source changes.
  useEffect(() => {
    setText('')
    setTotal(null)
    setTextError(null)
  }, [project.source_chars, project.source_files.length])

  const loadMore = async (offset: number) => {
    setLoadingText(true)
    setTextError(null)
    try {
      const res = await getSource(project.id, offset, CHUNK)
      setText((prev) => (offset === 0 ? res.text : prev + res.text))
      setTotal(res.total_chars)
    } catch (e) {
      setTextError(errorMessage(e))
    } finally {
      setLoadingText(false)
    }
  }

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next && text.length === 0 && total === null) void loadMore(0)
  }

  const onFile = async (file: File | undefined) => {
    if (!file) return
    setUploading(true)
    try {
      onProject(await uploadSource(project.id, file))
      toast.success(t('source_uploaded'))
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setUploading(false)
    }
  }

  const doClear = async () => {
    setClearing(true)
    try {
      onProject(await clearSource(project.id))
      toast.success(t('source_cleared'))
      setConfirmClear(false)
      setOpen(false)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setClearing(false)
    }
  }

  const hasSource = project.source_chars > 0 || project.source_files.length > 0
  const hasMore = total !== null && text.length < total

  return (
    <SectionCard
      title={t('section_source')}
      description={t('source_chars', { n: project.source_chars.toLocaleString() })}
      actions={
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary btn-sm"
            disabled={busy || uploading}
            onClick={() => fileInput.current?.click()}
          >
            {uploading ? <Spinner size={12} /> : <Upload size={13} />}
            {uploading ? t('uploading_source') : t('upload_source')}
          </button>
          <button
            type="button"
            className="btn-danger btn-sm"
            disabled={busy || uploading || !hasSource}
            onClick={() => setConfirmClear(true)}
          >
            <Trash2 size={13} />
            {t('clear_source')}
          </button>
          <input
            ref={fileInput}
            type="file"
            accept={SOURCE_ACCEPT}
            className="hidden"
            onChange={(e) => {
              void onFile(e.target.files?.[0])
              e.target.value = ''
            }}
          />
        </div>
      }
    >
      {project.source_files.length > 0 ? (
        <ul className="divide-y divide-border rounded-lg border border-border bg-bg-elev">
          {project.source_files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center gap-3 px-3 py-2 text-sm">
              <FileText size={15} className="shrink-0 text-accent" />
              <span className="min-w-0 flex-1 truncate">{f.name}</span>
              <span className="shrink-0 text-xs text-muted tabular-nums">
                {t('source_chars', { n: f.chars.toLocaleString() })}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-lg border border-dashed border-border-strong px-4 py-6 text-center text-sm text-muted">
          {hasSource ? t('source_chars', { n: project.source_chars.toLocaleString() }) : t('source_empty')}
        </p>
      )}

      {hasSource && (
        <div className="mt-3">
          <button type="button" className="btn-ghost btn-sm" onClick={toggle}>
            {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            {open ? t('hide_preview') : t('source_preview')}
          </button>
          {open && (
            <div className="mt-2 space-y-2">
              {textError && <ErrorAlert message={textError} onRetry={() => void loadMore(text.length)} />}
              <pre className="max-h-80 overflow-auto rounded-lg border border-border bg-bg-elev p-3 font-sans text-sm leading-relaxed whitespace-pre-wrap text-text/90">
                {text}
                {loadingText && text.length === 0 && (
                  <span className="text-muted">{t('loading')}</span>
                )}
              </pre>
              <div className="flex items-center gap-3 text-xs text-muted">
                {hasMore ? (
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    disabled={loadingText}
                    onClick={() => void loadMore(text.length)}
                  >
                    {loadingText && <Spinner size={12} />}
                    {t('load_more')}
                  </button>
                ) : (
                  total !== null && <span>{t('preview_end')}</span>
                )}
                {total !== null && (
                  <span className="tabular-nums">
                    {text.length.toLocaleString()} / {total.toLocaleString()}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirmClear}
        danger
        busy={clearing}
        title={t('clear_source')}
        message={t('clear_source_confirm')}
        confirmLabel={t('clear_source')}
        onCancel={() => !clearing && setConfirmClear(false)}
        onConfirm={() => void doClear()}
      />
    </SectionCard>
  )
}
