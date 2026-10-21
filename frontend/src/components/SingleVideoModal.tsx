import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Download, ExternalLink, Film, Sparkles, Upload, X } from 'lucide-react'
import { createQuickVideo, getProject } from '../api'
import { useLang } from '../i18n'
import type { AspectRatio, Project, Task } from '../types'

interface SingleVideoModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function SingleVideoModal({ isOpen, onClose }: SingleVideoModalProps) {
  const { t } = useLang()
  const navigate = useNavigate()

  const [prompt, setPrompt] = useState('')
  const [title, setTitle] = useState('')
  const [aspect, setAspect] = useState<AspectRatio>('16:9')
  const [duration, setDuration] = useState(5)
  const [motion, setMotion] = useState('ai_video')
  const [withNarration, setWithNarration] = useState(false)
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [endImageFile, setEndImageFile] = useState<File | null>(null)
  const [endImagePreview, setEndImagePreview] = useState<string | null>(null)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeProject, setActiveProject] = useState<Project | null>(null)
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const endFileInputRef = useRef<HTMLInputElement>(null)

  // Clear state when opened
  useEffect(() => {
    if (isOpen) {
      setError(null)
      if (!activeProject) {
        setBusy(false)
      }
    }
  }, [isOpen])

  // Poll task progress while generating
  useEffect(() => {
    if (!busy || !activeProject) return
    const pollInterval = window.setInterval(async () => {
      try {
        const p = await getProject(activeProject.id)
        setActiveProject(p)
        if (p.active_task) {
          setActiveTask(p.active_task)
        } else {
          // Task ended
          setBusy(false)
          window.clearInterval(pollInterval)
        }
      } catch (e) {
        console.error('Polling error', e)
      }
    }, 1500)
    return () => window.clearInterval(pollInterval)
  }, [busy, activeProject])

  if (!isOpen) return null

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    const reader = new FileReader()
    reader.onload = () => {
      setImagePreview(reader.result as string)
    }
    reader.readAsDataURL(file)
  }

  const handleClearImage = () => {
    setImageFile(null)
    setImagePreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleEndImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setEndImageFile(file)
    const reader = new FileReader()
    reader.onload = () => {
      setEndImagePreview(reader.result as string)
    }
    reader.readAsDataURL(file)
  }

  const handleClearEndImage = () => {
    setEndImageFile(null)
    setEndImagePreview(null)
    if (endFileInputRef.current) endFileInputRef.current.value = ''
  }

  const handleGenerate = async () => {
    const pText = prompt.trim()
    if (!pText) {
      setError('請輸入提示詞')
      return
    }
    setError(null)
    setBusy(true)
    setActiveTask(null)

    try {
      const proj = await createQuickVideo({
        prompt: pText,
        title: title.trim() || undefined,
        aspect_ratio: aspect,
        duration,
        motion,
        video_mode: imagePreview ? 'i2v' : undefined,
        with_narration: withNarration,
        image_base64: imagePreview,
        end_image_base64: endImagePreview,
      })
      setActiveProject(proj)
      if (proj.active_task) {
        setActiveTask(proj.active_task)
      }
    } catch (e: any) {
      setError(e.detail || e.message || '生成失敗，請檢查設定與服務狀態')
      setBusy(false)
    }
  }

  const handleReset = () => {
    setActiveProject(null)
    setActiveTask(null)
    setBusy(false)
    setError(null)
    setPrompt('')
    setImageFile(null)
    setImagePreview(null)
    setEndImageFile(null)
    setEndImagePreview(null)
  }

  const isComplete = !busy && activeProject && !!activeProject.final_video_url

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm animate-fade-in">
      <div
        className="card relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden border border-border bg-panel-2 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-indigo-glow text-white shadow-sm">
              <Sparkles size={16} />
            </span>
            <div>
              <h3 className="font-semibold text-text">{t('single_video')}</h3>
              <p className="text-xs text-muted">{t('single_video_subtitle')}</p>
            </div>
          </div>
          <button
            type="button"
            className="btn-ghost btn-icon h-8 w-8 text-muted hover:text-text"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {error && (
            <div className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-2.5 text-xs text-danger">
              {error}
            </div>
          )}

          {/* Success View */}
          {isComplete && activeProject?.final_video_url ? (
            <div className="space-y-4 text-center">
              <div className="overflow-hidden rounded-xl border border-border bg-black">
                <video
                  src={activeProject.final_video_url}
                  controls
                  autoPlay
                  loop
                  className="mx-auto max-h-80 w-full object-contain"
                />
              </div>

              <div className="flex items-center justify-center gap-2 text-sm font-medium text-emerald-400">
                <CheckCircle2 size={16} />
                <span>{t('single_video_done')}</span>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                <a
                  href={activeProject.final_video_url}
                  download={`${activeProject.title || 'video'}.mp4`}
                  className="btn-primary"
                >
                  <Download size={15} />
                  {t('single_video_download')}
                </a>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    onClose()
                    navigate(`/projects/${activeProject.id}`)
                  }}
                >
                  <ExternalLink size={15} />
                  {t('single_video_open_studio')}
                </button>
                <button type="button" className="btn-ghost" onClick={handleReset}>
                  再產生一部
                </button>
              </div>
            </div>
          ) : busy ? (
            /* Generating View */
            <div className="flex flex-col items-center justify-center py-12 text-center space-y-4">
              <div className="relative">
                <div className="h-16 w-16 rounded-full border-4 border-accent/20 border-t-accent animate-spin" />
                <div className="absolute inset-0 grid place-items-center text-accent">
                  <Film size={22} />
                </div>
              </div>

              <div className="space-y-1">
                <h4 className="font-semibold text-text">{t('single_video_generating')}</h4>
                <p className="text-xs text-muted">
                  {activeTask?.message || 'AI 正在繪製畫面與渲染高畫質影片動態…'}
                </p>
              </div>

              {activeTask && typeof activeTask.progress === 'number' && (
                <div className="w-full max-w-xs space-y-1">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-panel">
                    <div
                      className="h-full bg-accent transition-all duration-300"
                      style={{ width: `${Math.round(activeTask.progress * 100)}%` }}
                    />
                  </div>
                  <div className="text-[11px] text-muted tabular-nums">
                    {Math.round(activeTask.progress * 100)}%
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Form View */
            <div className="space-y-4">
              {/* Prompt Input */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-text">
                  {t('single_video_prompt_label')} <span className="text-accent">*</span>
                </label>
                <textarea
                  className="input min-h-28 text-sm"
                  rows={4}
                  placeholder={t('single_video_prompt_placeholder')}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={busy}
                />
              </div>

              {/* Options Grid */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {/* Aspect Ratio */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted">{t('aspect_ratio')}</label>
                  <select
                    className="input text-xs"
                    value={aspect}
                    onChange={(e) => setAspect(e.target.value as AspectRatio)}
                    disabled={busy}
                  >
                    <option value="16:9">16:9 橫式 (1920×1080)</option>
                    <option value="9:16">9:16 直式 (1080×1920)</option>
                    <option value="1:1">1:1 正方形 (1080×1080)</option>
                  </select>
                </div>

                {/* Duration */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted">{t('single_video_duration')}</label>
                  <select
                    className="input text-xs"
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    disabled={busy}
                  >
                    <option value={3}>3 秒 (短片段)</option>
                    <option value={5}>5 秒 (標準)</option>
                    <option value={8}>8 秒 (慢速流暢)</option>
                    <option value={10}>10 秒 (長鏡頭)</option>
                  </select>
                </div>

                {/* Motion Engine */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted">{t('motion')}</label>
                  <select
                    className="input text-xs"
                    value={motion}
                    onChange={(e) => setMotion(e.target.value)}
                    disabled={busy}
                  >
                    <option value="ai_video">AI 影片生成 (Agnes / ComfyUI)</option>
                    <option value="kenburns">Ken Burns 鏡頭推拉 (速度快)</option>
                    <option value="static">靜態展示</option>
                  </select>
                </div>
              </div>

              {/* Optional Start & End Keyframes */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Start Frame */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-muted">
                      {t('single_video_start_image')}
                    </label>
                    {imagePreview && (
                      <button
                        type="button"
                        className="text-[11px] text-danger hover:underline"
                        onClick={handleClearImage}
                      >
                        移除
                      </button>
                    )}
                  </div>

                  {imagePreview ? (
                    <div className="flex items-center gap-3 rounded-lg border border-border bg-panel p-2">
                      <img
                        src={imagePreview}
                        alt="start frame"
                        className="h-14 w-20 rounded object-cover"
                      />
                      <div className="min-w-0 flex-1 text-xs">
                        <p className="truncate font-medium text-text">{imageFile?.name}</p>
                        <p className="text-[11px] text-muted">首幀起點圖</p>
                      </div>
                    </div>
                  ) : (
                    <div
                      className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border py-3 transition hover:border-accent hover:bg-accent/5"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Upload size={16} className="text-muted" />
                      <p className="mt-1 text-[11px] text-muted">上傳首幀起點圖 (選填)</p>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={handleImageUpload}
                      />
                    </div>
                  )}
                </div>

                {/* End Frame */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-muted">
                      {t('single_video_end_image')}
                    </label>
                    {endImagePreview && (
                      <button
                        type="button"
                        className="text-[11px] text-danger hover:underline"
                        onClick={handleClearEndImage}
                      >
                        移除
                      </button>
                    )}
                  </div>

                  {endImagePreview ? (
                    <div className="flex items-center gap-3 rounded-lg border border-border bg-panel p-2">
                      <img
                        src={endImagePreview}
                        alt="end frame"
                        className="h-14 w-20 rounded object-cover"
                      />
                      <div className="min-w-0 flex-1 text-xs">
                        <p className="truncate font-medium text-text">{endImageFile?.name}</p>
                        <p className="text-[11px] text-muted">尾幀終點圖</p>
                      </div>
                    </div>
                  ) : (
                    <div
                      className="flex cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border py-3 transition hover:border-accent hover:bg-accent/5"
                      onClick={() => endFileInputRef.current?.click()}
                    >
                      <Upload size={16} className="text-muted" />
                      <p className="mt-1 text-[11px] text-muted">上傳尾幀終點圖 (選填)</p>
                      <input
                        ref={endFileInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={handleEndImageUpload}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Optional Title & Narration */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted">
                    {t('title_label')} · {t('optional')}
                  </label>
                  <input
                    className="input text-xs"
                    placeholder="留空將自動以提示詞命名"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    disabled={busy}
                  />
                </div>

                <div className="flex items-center pt-6">
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-text">
                    <input
                      type="checkbox"
                      checked={withNarration}
                      onChange={(e) => setWithNarration(e.target.checked)}
                      disabled={busy}
                      className="rounded border-border"
                    />
                    <span>{t('single_video_with_narration')}</span>
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {!isComplete && !busy && (
          <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-3.5 bg-panel">
            <button type="button" className="btn-ghost" onClick={onClose} disabled={busy}>
              {t('cancel')}
            </button>
            <button
              type="button"
              className="btn-primary gap-1.5"
              onClick={handleGenerate}
              disabled={busy || !prompt.trim()}
            >
              <Sparkles size={15} />
              <span>{t('single_video_generate')}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
