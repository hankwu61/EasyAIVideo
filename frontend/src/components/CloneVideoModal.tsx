import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Copy, Film, ImagePlus, Link2, Upload, Video, Wand2, X } from 'lucide-react'
import { cloneVideoProject } from '../api'
import { useResources } from '../hooks/useResources'
import { useLang } from '../i18n'
import type { Project } from '../types'
import { Spinner } from './ui'

interface CloneVideoModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function CloneVideoModal({ isOpen, onClose }: CloneVideoModalProps) {
  const { t } = useLang()
  const navigate = useNavigate()
  const { resources } = useResources()

  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [videoDuration, setVideoDuration] = useState<number | null>(null)

  const [title, setTitle] = useState('')
  const [language, setLanguage] = useState('zh-TW')
  const [generationMode, setGenerationMode] = useState<string>('minimax_h3')
  const [h3Mode, setH3Mode] = useState<string>('ref2va')
  const [characterReplacement, setCharacterReplacement] = useState<string>('')
  const [motion, setMotion] = useState<string>('ai_video')
  const [styleId, setStyleId] = useState('')
  const [autoStart, setAutoStart] = useState(false)
  const [sourceType, setSourceType] = useState<'file' | 'url'>('file')
  const [sourceUrl, setSourceUrl] = useState('')
  const [refImages, setRefImages] = useState<File[]>([])
  const [refPreviews, setRefPreviews] = useState<string[]>([])
  const [useRefVideo, setUseRefVideo] = useState(true)
  const [useRefAudio, setUseRefAudio] = useState(true)
  const picInputRef = useRef<HTMLInputElement>(null)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createdProject, setCreatedProject] = useState<Project | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const videoElemRef = useRef<HTMLVideoElement>(null)

  // Clear or reset on open
  useEffect(() => {
    if (isOpen) {
      setError(null)
      if (!createdProject) {
        setBusy(false)
      }
    }
  }, [isOpen])

  // Handle video selection
  const handleFileChange = (file: File | null) => {
    if (!file) return
    setVideoFile(file)
    setError(null)
    const url = URL.createObjectURL(file)
    setVideoUrl(url)
    if (!title) {
      const guessed = file.name.replace(/\.[^/.]+$/, '')
      setTitle(guessed)
    }
  }

  const handleLoadedMetadata = () => {
    if (videoElemRef.current) {
      setVideoDuration(videoElemRef.current.duration)
    }
  }

  const addRefImages = (files: FileList | null) => {
    if (!files) return
    const picked = Array.from(files).filter((f) => /\.(jpe?g|png|webp)$/i.test(f.name))
    const next = [...refImages, ...picked].slice(0, 9)
    refPreviews.forEach((u) => URL.revokeObjectURL(u))
    setRefImages(next)
    setRefPreviews(next.map((f) => URL.createObjectURL(f)))
    if (picInputRef.current) picInputRef.current.value = ''
  }

  const removeRefImage = (idx: number) => {
    const next = refImages.filter((_, i) => i !== idx)
    refPreviews.forEach((u) => URL.revokeObjectURL(u))
    setRefImages(next)
    setRefPreviews(next.map((f) => URL.createObjectURL(f)))
  }

  const handleClearFile = () => {
    if (videoUrl) URL.revokeObjectURL(videoUrl)
    setVideoFile(null)
    setVideoUrl(null)
    setVideoDuration(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const url = sourceUrl.trim()
    if (sourceType === 'file' && !videoFile) {
      setError('請選擇要復刻的短影片檔案。')
      return
    }
    if (sourceType === 'url') {
      if (!url) {
        setError(t('clone_url_required'))
        return
      }
      if (!/^https?:\/\/\S+$/i.test(url)) {
        setError(t('clone_url_invalid'))
        return
      }
    }

    setBusy(true)
    setError(null)

    const fd = new FormData()
    if (sourceType === 'file' && videoFile) fd.append('video_file', videoFile, videoFile.name)
    else fd.append('source_url', url)
    if (title.trim()) fd.append('title', title.trim())
    fd.append('language', language)
    fd.append('motion', motion)
    if (styleId) fd.append('style_id', styleId)
    fd.append('auto_start', String(autoStart))
    fd.append('generation_mode', generationMode)
    fd.append('h3_mode', h3Mode)
    if (characterReplacement.trim()) fd.append('character_replacement', characterReplacement.trim())
    if (generationMode === 'minimax_h3') {
      fd.append('use_ref_video', String(useRefVideo))
      fd.append('use_ref_audio', String(useRefAudio))
      if (h3Mode === 'ref2va') refImages.forEach((f) => fd.append('reference_images', f, f.name))
    }

    try {
      const proj = await cloneVideoProject(fd)
      setCreatedProject(proj)
      setBusy(false)
      // Navigate to project page
      onClose()
      navigate(`/projects/${proj.id}`)
    } catch (err: any) {
      setError(err.detail || err.message || '短影片分析失敗，請檢查檔案格式與伺服器狀態。')
      setBusy(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm animate-fade-in">
      <div className="card relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden border border-border bg-panel-2 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent/20 text-accent">
              <Copy size={18} />
            </span>
            <div>
              <h2 className="text-base font-semibold text-text">{t('clone_video')}</h2>
              <p className="text-xs text-muted">{t('clone_video_subtitle')}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="btn-ghost btn-icon text-muted hover:text-text disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5">
          {error && (
            <div className="rounded-xl border border-danger/40 bg-danger/10 p-3.5 text-xs text-danger leading-relaxed">
              {error}
            </div>
          )}

          {/* Source switch: upload a file or paste a URL */}
          <div className="flex gap-1 rounded-xl border border-border bg-panel p-1">
            {(['file', 'url'] as const).map((kind) => (
              <button
                key={kind}
                type="button"
                disabled={busy}
                onClick={() => {
                  setSourceType(kind)
                  setError(null)
                }}
                className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 ${
                  sourceType === kind ? 'bg-accent text-white shadow-sm' : 'text-muted hover:bg-panel-2 hover:text-text'
                }`}
              >
                {kind === 'file' ? <Upload size={14} /> : <Link2 size={14} />}
                {kind === 'file' ? t('clone_source_file') : t('clone_source_url')}
              </button>
            ))}
          </div>

          {sourceType === 'url' && (
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-text">{t('clone_url_label')}</label>
              <input
                className="input w-full font-mono text-sm"
                type="url"
                inputMode="url"
                autoComplete="off"
                placeholder={t('clone_url_placeholder')}
                value={sourceUrl}
                disabled={busy}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
              <p className="mt-1 text-[11px] text-muted">{t('clone_url_hint')}</p>
            </div>
          )}

          {/* Video upload dropzone */}
          {sourceType === 'file' && (
          <div>
            <label className="block text-xs font-semibold text-text mb-1.5">
              {t('clone_video_upload_label')}
            </label>
            {videoUrl ? (
              <div className="relative overflow-hidden rounded-xl border border-border bg-panel p-3">
                <div className="flex items-start gap-4">
                  <div className="relative aspect-[9/16] h-36 max-h-40 w-auto shrink-0 overflow-hidden rounded-lg bg-black">
                    <video
                      ref={videoElemRef}
                      src={videoUrl}
                      onLoadedMetadata={handleLoadedMetadata}
                      className="h-full w-full object-contain"
                      controls
                      playsInline
                    />
                  </div>
                  <div className="flex-1 min-w-0 space-y-1.5 py-1">
                    <div className="flex items-center gap-1.5 font-medium text-text text-sm">
                      <Film size={15} className="text-accent shrink-0" />
                      <span className="truncate">{videoFile?.name}</span>
                    </div>
                    <div className="text-xs text-muted flex flex-wrap gap-x-4 gap-y-1">
                      <span>大小：{videoFile ? (videoFile.size / (1024 * 1024)).toFixed(2) : 0} MB</span>
                      {videoDuration !== null && <span>時長：{videoDuration.toFixed(1)} 秒</span>}
                    </div>
                    <p className="text-[11px] text-accent/90 pt-1">
                      ✓ AI 將依據此影片的時間軸與鏡頭變化抽取關鍵畫面進行分鏡重製
                    </p>
                    <button
                      type="button"
                      onClick={handleClearFile}
                      disabled={busy}
                      className="text-xs text-danger hover:underline pt-2 disabled:opacity-50"
                    >
                      更換影片檔案
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div
                className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-border py-8 transition hover:border-accent hover:bg-accent/5"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault()
                  const file = e.dataTransfer.files?.[0]
                  if (file) handleFileChange(file)
                }}
              >
                <div className="grid h-12 w-12 place-items-center rounded-2xl bg-accent/15 text-accent mb-2">
                  <Video size={24} />
                </div>
                <p className="text-sm font-medium text-text">{t('clone_video_upload_hint')}</p>
                <p className="text-xs text-muted mt-1">支援 5 秒 ~ 60 秒直式/橫式短影片</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv"
                  className="hidden"
                  onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                />
              </div>
            )}
          </div>

          )}

          {/* Options */}
          <div className="rounded-xl border border-border bg-panel p-4 space-y-4">
            <h3 className="text-xs font-semibold text-text uppercase tracking-wider">{t('clone_video_options')}</h3>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-text mb-1">{t('clone_mode')}</label>
                <select
                  className="input text-sm font-medium border-accent/40 bg-accent/5 text-accent"
                  value={generationMode}
                  disabled={busy}
                  onChange={(e) => setGenerationMode(e.target.value)}
                >
                  <option value="minimax_h3">{t('clone_mode_minimax_h3')}</option>
                  <option value="standard">{t('clone_mode_standard')}</option>
                </select>
              </div>

              {generationMode === 'minimax_h3' && (
                <div>
                  <label className="block text-xs font-medium text-text mb-1">{t('h3_mode_label')}</label>
                  <select
                    className="input text-sm font-mono"
                    value={h3Mode}
                    disabled={busy}
                    onChange={(e) => setH3Mode(e.target.value)}
                  >
                    <option value="ref2va">{t('h3_mode_ref2va')}</option>
                    <option value="i2va">{t('h3_mode_i2va')}</option>
                    <option value="t2va">{t('h3_mode_t2va')}</option>
                    <option value="fl2va">{t('h3_mode_fl2va')}</option>
                  </select>
                </div>
              )}
            </div>

            {generationMode === 'minimax_h3' && (
              <p className="text-[11px] text-muted">{t('h3_auto_segment_hint')}</p>
            )}

            {generationMode === 'minimax_h3' && h3Mode === 'ref2va' && (
              <div className="rounded-lg border border-border bg-panel-2 p-3 space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-text mb-1">{t('h3_ref_images_label')}</label>
                  <div className="flex flex-wrap items-center gap-2">
                    {refPreviews.map((url, i) => (
                      <div key={url} className="relative h-16 w-16 overflow-hidden rounded-lg border border-border bg-black">
                        <img src={url} alt={`Picture ${i + 1}`} className="h-full w-full object-cover" />
                        <span className="absolute left-0 top-0 rounded-br bg-black/70 px-1 text-[10px] text-white">{i + 1}</span>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => removeRefImage(i)}
                          className="absolute right-0 top-0 rounded-bl bg-black/70 p-0.5 text-white hover:text-danger"
                          aria-label="remove"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                    {refImages.length < 9 && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => picInputRef.current?.click()}
                        className="flex h-16 w-16 flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-border text-[10px] text-muted hover:border-accent hover:text-accent disabled:opacity-50"
                      >
                        <ImagePlus size={16} />
                        {t('h3_ref_images_add')}
                      </button>
                    )}
                    <input
                      ref={picInputRef}
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                      className="hidden"
                      onChange={(e) => addRefImages(e.target.files)}
                    />
                  </div>
                  <p className="mt-1 text-[11px] text-muted">{t('h3_ref_images_hint')}</p>
                </div>
                <label className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-accent"
                    checked={useRefVideo}
                    disabled={busy}
                    onChange={(e) => setUseRefVideo(e.target.checked)}
                  />
                  <span className="text-xs text-text">{t('h3_use_ref_video')}</span>
                </label>
                <label className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-accent"
                    checked={useRefAudio}
                    disabled={busy}
                    onChange={(e) => setUseRefAudio(e.target.checked)}
                  />
                  <span className="text-xs text-text">{t('h3_use_ref_audio')}</span>
                </label>
              </div>
            )}

            {generationMode === 'minimax_h3' && (
              <div className="rounded-lg border border-accent/20 bg-accent/5 p-3 space-y-1.5">
                <label className="block text-xs font-semibold text-accent">
                  {t('character_replacement_label')}
                </label>
                <textarea
                  className="input text-xs w-full resize-none h-16"
                  placeholder={t('character_replacement_placeholder')}
                  value={characterReplacement}
                  disabled={busy}
                  onChange={(e) => setCharacterReplacement(e.target.value)}
                />
                <p className="text-[11px] text-muted">{t('character_replacement_hint')}</p>
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-muted mb-1">{t('language')}</label>
                <select
                  className="input text-sm"
                  value={language}
                  disabled={busy}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="zh-TW">繁體中文 (Traditional Chinese)</option>
                  <option value="zh-CN">简体中文 (Simplified Chinese)</option>
                  <option value="en">English</option>
                  <option value="ja">日本語</option>
                  <option value="ko">한국어</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-muted mb-1">{t('clone_video_motion')}</label>
                <select
                  className="input text-sm"
                  value={motion}
                  disabled={busy}
                  onChange={(e) => setMotion(e.target.value)}
                >
                  <option value="ai_video">AI 影片生成（MiniMax / Agnes / ComfyUI）</option>
                  <option value="kenburns">Ken Burns 運鏡變焦</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs font-medium text-muted mb-1">
                  {t('clone_video_style_optional')}
                </label>
                <select
                  className="input text-sm"
                  value={styleId}
                  disabled={busy}
                  onChange={(e) => setStyleId(e.target.value)}
                >
                  <option value="">{t('clone_video_auto_detect_style')}</option>
                  {resources?.styles.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-muted mb-1">{t('title_label')} (可選)</label>
                <input
                  className="input text-sm"
                  placeholder="留空將由 AI 自動從影片主題命名"
                  value={title}
                  disabled={busy}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
            </div>

            {/* Auto start checkbox */}
            <div className="border-t border-border/60 pt-3">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoStart}
                  disabled={busy}
                  onChange={(e) => setAutoStart(e.target.checked)}
                  className="mt-0.5 accent-accent"
                />
                <div>
                  <span className="text-xs font-medium text-text">{t('clone_video_start_now')}</span>
                  <p className="text-[11px] text-muted">{t('clone_video_start_now_hint')}</p>
                </div>
              </label>
            </div>
          </div>

          {/* Busy analyzing status */}
          {busy && (
            <div className="rounded-xl border border-accent/30 bg-accent/10 p-4 text-center space-y-2 animate-pulse">
              <div className="flex items-center justify-center gap-2 text-accent font-medium text-sm">
                <Spinner size={16} />
                <span>{sourceType === 'url' ? t('clone_url_downloading') : t('clone_video_analyzing')}</span>
              </div>
              <p className="text-xs text-muted">{t('clone_video_analyzing_hint')}</p>
            </div>
          )}

          {/* Footer buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="btn-secondary text-sm disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={busy || (sourceType === 'file' ? !videoFile : !sourceUrl.trim())}
              className="btn-primary flex items-center gap-2 text-sm disabled:opacity-50"
            >
              {busy ? (
                <>
                  <Spinner size={16} />
                  <span>AI 分析中…</span>
                </>
              ) : (
                <>
                  <Wand2 size={16} />
                  <span>{t('clone_video_submit_btn')}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
