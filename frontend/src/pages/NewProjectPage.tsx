import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, FileUp, Info, LayoutTemplate, Presentation, ScanSearch, Sparkles, Video, Wand2 } from 'lucide-react'
import { analyzeProject, cloneVideoProject, createProject, createSlideProject, errorMessage, listTemplates, uploadSource } from '../api'
import KindPicker, { DEFAULT_KINDS } from '../components/new/KindPicker'
import SeriesContentCard, { DEFAULT_CONTENT_MODES, type SeriesContent } from '../components/new/SeriesContentCard'
import VisualCard, { type VisualSettings } from '../components/new/VisualCard'
import { DEFAULT_VIDEO_MODES, OutputSettingsFields, type OutputSettings } from '../components/ProjectSettingsFields'
import { TemplateCard } from '../components/templates/TemplateCard'
import { useToast } from '../components/Toast'
import { ErrorAlert, Field, PageHeader, SectionCard, Skeleton, Spinner } from '../components/ui'
import { useResources } from '../hooks/useResources'
import { useLang } from '../i18n'
import type { AspectRatio, InputMode, ProjectCreate, ProjectKind, Template } from '../types'
import { cx } from '../utils'

interface SlideContent {
  pptx_file: File | null
  guide_file: File | null
  guide_text: string
}

interface FormState {
  kind: ProjectKind
  input_mode: InputMode
  topic: string
  title: string
  language: string
  n_scenes: number
  visual: VisualSettings
  series: SeriesContent
  slide: SlideContent
  video_file: File | null
  output: OutputSettings
  template_id?: string | null
}

type Phase = 'start' | 'create' | 'upload' | null

export default function NewProjectPage() {
  const { t } = useLang()
  const toast = useToast()
  const navigate = useNavigate()
  const { resources, loading, error, reload } = useResources()

  const [searchParams] = useSearchParams()
  const templateIdParam = searchParams.get('template_id')
  const [templates, setTemplates] = useState<Template[]>([])

  const [form, setForm] = useState<FormState | null>(null)
  const [submitting, setSubmitting] = useState<Phase>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    listTemplates().then(setTemplates).catch(console.error)
  }, [])

  // Seed the form once resources arrive.
  useEffect(() => {
    if (!resources || form) return
    const { presets, styles, voices } = resources
    const firstStyle = styles[0]
    const zhVoice = voices.find((v) => v.locale === 'zh-TW') ?? voices[0]
    const language = presets.languages[0]?.id ?? 'zh-TW'
    setForm({
      kind: 'single',
      input_mode: (presets.input_modes[0]?.id as InputMode) ?? 'topic',
      topic: '',
      title: '',
      language,
      n_scenes: 6,
      visual: {
        style_id: firstStyle?.id ?? '',
        style_prompt: firstStyle?.prompt ?? '',
        aspect_ratio: (presets.aspect_ratios[0]?.id as AspectRatio) ?? '9:16',
      },
      series: {
        source_file: null,
        source_text: '',
        title: '',
        language,
        content_mode: 'narration',
        episode_target_seconds: 120,
      },
      slide: {
        pptx_file: null,
        guide_file: null,
        guide_text: '',
      },
      video_file: null,
      output: {
        voice: zhVoice?.id ?? '',
        tts_speed: 1.0,
        bgm: null,
        bgm_volume: 0.2,
        motion: presets.motions[0]?.id ?? 'kenburns',
        video_mode: null,
        subtitle_enabled: true,
        show_title: true,
        font_family: 'msjh',
        font_size: 24,
        subtitle_position: 'bottom',
        transition: 'none',
        transition_duration: 0.5,
      },
    })
  }, [resources, form])

  const update = (patch: Partial<FormState>) => setForm((f) => (f ? { ...f, ...patch } : f))

  const applyTemplate = (tpl: Template | null) => {
    if (!form) return
    if (!tpl) {
      update({ template_id: null })
      return
    }
    update({
      template_id: tpl.id,
      visual: {
        ...form.visual,
        style_id: tpl.config.style_id,
        style_prompt: tpl.config.style_prompt,
      },
      output: {
        ...form.output,
        font_family: tpl.config.font_family,
        font_size: tpl.config.font_size,
        subtitle_position: tpl.config.subtitle_position,
        transition: tpl.config.transition,
        transition_duration: tpl.config.transition_duration,
        bgm: tpl.config.bgm,
        bgm_volume: tpl.config.bgm_volume,
      },
    })
  }

  // Pre-select template from URL if present
  useEffect(() => {
    if (!templates.length || !form) return
    if (templateIdParam && form.template_id !== templateIdParam) {
      const found = templates.find((t) => t.id === templateIdParam)
      if (found) applyTemplate(found)
    }
  }, [templates, templateIdParam, form])

  const submitSingle = async (form: FormState, autoStart: boolean) => {
    if (!form.topic.trim()) {
      setSubmitError(t('topic_required'))
      return
    }
    setSubmitting(autoStart ? 'start' : 'create')
    const body: ProjectCreate = {
      title: form.title.trim() || undefined,
      topic: form.topic,
      input_mode: form.input_mode,
      language: form.language,
      aspect_ratio: form.visual.aspect_ratio,
      style_id: form.visual.style_id,
      style_prompt: form.visual.style_prompt.trim() ? form.visual.style_prompt : null,
      n_scenes: form.input_mode === 'prompt' ? 1 : form.n_scenes,
      ...form.output,
      template_id: form.template_id ?? undefined,
      auto_start: autoStart,
    }
    const project = await createProject(body)
    toast.success(t('project_created'))
    navigate(`/projects/${project.id}`)
  }

  const submitSeries = async (form: FormState, autoStart: boolean) => {
    const s = form.series
    const hasFile = !!s.source_file
    if (!hasFile && !s.source_text.trim()) {
      setSubmitError(t('source_required'))
      return
    }
    setSubmitting(autoStart ? 'start' : 'create')
    const body: ProjectCreate = {
      kind: 'series',
      title: s.title.trim() || undefined,
      topic: '',
      input_mode: 'topic',
      language: s.language,
      aspect_ratio: form.visual.aspect_ratio,
      style_id: form.visual.style_id,
      style_prompt: form.visual.style_prompt.trim() ? form.visual.style_prompt : null,
      n_scenes: form.n_scenes,
      ...form.output,
      content_mode: s.content_mode,
      episode_target_seconds: s.episode_target_seconds,
      template_id: form.template_id ?? undefined,
      source_text: hasFile ? undefined : s.source_text,
      // With a file the analysis must wait until the upload has finished.
      auto_start: hasFile ? false : autoStart,
    }
    const project = await createProject(body)
    if (s.source_file) {
      setSubmitting('upload')
      try {
        await uploadSource(project.id, s.source_file)
        if (autoStart) await analyzeProject(project.id)
      } catch (e) {
        // The series exists; let the user retry the upload from its page.
        toast.error(errorMessage(e))
        navigate(`/series/${project.id}`)
        return
      }
    }
    toast.success(t('series_created'))
    navigate(`/series/${project.id}`)
  }

  const submitSlide = async (form: FormState, autoStart: boolean) => {
    if (!form.slide.pptx_file) {
      setSubmitError(t('pptx_required'))
      return
    }
    setSubmitting(autoStart ? 'start' : 'create')
    const fd = new FormData()
    fd.append('pptx_file', form.slide.pptx_file, form.slide.pptx_file.name)
    if (form.slide.guide_file) {
      fd.append('guide_file', form.slide.guide_file, form.slide.guide_file.name)
    }
    if (form.slide.guide_text.trim()) {
      fd.append('guide_text', form.slide.guide_text.trim())
    }
    if (form.title.trim()) {
      fd.append('title', form.title.trim())
    }
    fd.append('language', form.language)
    fd.append('aspect_ratio', form.visual.aspect_ratio)
    fd.append('voice', form.output.voice)
    fd.append('tts_speed', String(form.output.tts_speed))
    if (form.output.bgm) fd.append('bgm', form.output.bgm)
    fd.append('bgm_volume', String(form.output.bgm_volume))
    fd.append('subtitle_enabled', String(form.output.subtitle_enabled))
    if (form.output.subtitle_position) fd.append('subtitle_position', form.output.subtitle_position)
    if (form.output.font_family) fd.append('font_family', form.output.font_family)
    if (form.output.font_size) fd.append('font_size', String(form.output.font_size))
    fd.append('show_title', String(form.output.show_title))
    if (form.output.transition) fd.append('transition', form.output.transition)
    if (form.output.transition_duration) fd.append('transition_duration', String(form.output.transition_duration))
    fd.append('motion', form.output.motion)
    if (form.template_id) fd.append('template_id', form.template_id)
    fd.append('auto_start', String(autoStart))

    const project = await createSlideProject(fd)
    toast.success(t('project_created'))
    navigate(`/projects/${project.id}`)
  }

  const submitVideo = async (form: FormState, autoStart: boolean) => {
    if (!form.video_file) {
      setSubmitError(t('clone_video_file_required'))
      return
    }
    setSubmitting(autoStart ? 'start' : 'create')
    const fd = new FormData()
    fd.append('video_file', form.video_file, form.video_file.name)
    if (form.title.trim()) fd.append('title', form.title.trim())
    fd.append('language', form.language)
    if (form.visual.style_id) fd.append('style_id', form.visual.style_id)
    if (form.output.motion) fd.append('motion', form.output.motion)
    if (form.output.voice) fd.append('voice', form.output.voice)
    fd.append('auto_start', String(autoStart))
    fd.append('generation_mode', 'minimax_h3')
    fd.append('h3_mode', 'ref2va')

    const project = await cloneVideoProject(fd)
    toast.success(t('clone_video_success'))
    navigate(`/projects/${project.id}`)
  }

  const submit = async (autoStart: boolean) => {
    if (!form) return
    setSubmitError(null)
    try {
      if (form.kind === 'series') await submitSeries(form, autoStart)
      else if (form.input_mode === 'slide') await submitSlide(form, autoStart)
      else if (form.input_mode === 'video') await submitVideo(form, autoStart)
      else await submitSingle(form, autoStart)
    } catch (e) {
      setSubmitError(errorMessage(e))
      setSubmitting(null)
    }
  }

  const header = (
    <PageHeader
      title={
        <span className="flex items-center gap-3">
          <Link to="/" className="btn-ghost btn-icon" aria-label={t('back')}>
            <ArrowLeft size={18} />
          </Link>
          {t('new_title')}
        </span>
      }
      subtitle={t('new_subtitle')}
    />
  )

  if (error) {
    return (
      <div>
        {header}
        <ErrorAlert message={error} onRetry={() => void reload()} />
      </div>
    )
  }

  if (loading || !resources || !form) {
    return (
      <div>
        {header}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
          <Skeleton className="h-[520px]" />
          <Skeleton className="h-[520px]" />
        </div>
      </div>
    )
  }

  const { presets, styles, voices, bgm } = resources
  const isSeries = form.kind === 'series'
  const isPrompt = form.input_mode === 'prompt'
  const isTopic = form.input_mode === 'topic'
  const isVideo = form.input_mode === 'video'
  const startLabel = isSeries ? t('create_and_analyze') : isVideo ? t('clone_video_submit_btn') : t('create_and_start')
  const busy = submitting !== null

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        void submit(true)
      }}
    >
      {header}

      {/* Templates recommendation bar */}
      {templates.length > 0 && (
        <div className="mb-6 rounded-2xl border border-border bg-panel p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-text">
              <LayoutTemplate className="w-4 h-4 text-accent" />
              <span>{t('choose_template')}</span>
              <span className="text-xs font-normal text-muted">（點選自動套用風格、字型、字幕位置、轉場與 BGM）</span>
            </div>
            {form?.template_id && (
              <button
                type="button"
                onClick={() => applyTemplate(null)}
                className="text-xs text-accent hover:underline transition-colors"
              >
                清除模板套用
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {templates.map((tpl) => (
              <TemplateCard
                key={tpl.id}
                template={tpl}
                compact
                isSelected={form?.template_id === tpl.id}
                onSelect={() => applyTemplate(form?.template_id === tpl.id ? null : tpl)}
              />
            ))}
          </div>
        </div>
      )}

      <Field label={t('project_kind')} className="mb-6">
        <KindPicker kinds={presets.kinds ?? DEFAULT_KINDS} value={form.kind} onChange={(kind) => update({ kind })} />
      </Field>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
        {/* Left column: content + visual */}
        <div className="space-y-6">
          {isSeries ? (
            <SeriesContentCard
              value={form.series}
              onChange={(patch) => update({ series: { ...form.series, ...patch } })}
              languages={presets.languages}
              contentModes={presets.content_modes ?? DEFAULT_CONTENT_MODES}
            />
          ) : (
            <SectionCard title={t('section_content')}>
              <div className="space-y-4">
                <Field label={t('input_mode')}>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    {presets.input_modes.map((m) => {
                      const active = m.id === form.input_mode
                      return (
                        <label
                          key={m.id}
                          className={cx(
                            'flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition',
                            active
                              ? 'border-accent bg-accent/10 text-text'
                              : 'border-border bg-bg-elev text-muted hover:border-border-strong hover:text-text',
                          )}
                        >
                          <input
                            type="radio"
                            name="input_mode"
                            value={m.id}
                            checked={active}
                            onChange={() => {
                              const isSlideMode = m.id === 'slide'
                              const isPromptMode = m.id === 'prompt'
                              const isVideoMode = m.id === 'video'
                              update({
                                input_mode: m.id as InputMode,
                                n_scenes: isPromptMode ? 1 : form.n_scenes <= 1 ? 6 : form.n_scenes,
                                visual: {
                                  ...form.visual,
                                  aspect_ratio: isSlideMode ? '16:9' : form.visual.aspect_ratio,
                                },
                                output: {
                                  ...form.output,
                                  motion: isSlideMode ? 'static' : isPromptMode || isVideoMode ? 'ai_video' : form.output.motion,
                                  show_title: isSlideMode ? false : form.output.show_title,
                                },
                              })
                            }}
                            className="accent-accent"
                          />
                          {m.label}
                        </label>
                      )
                    })}
                  </div>
                </Field>

                {form.input_mode === 'slide' ? (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-accent/20 bg-accent/5 p-3.5 text-xs text-text leading-relaxed">
                      {t('slide_info_callout')}
                    </div>

                    {/* PPTX File Upload */}
                    <Field label={t('slide_upload_label')}>
                      <div
                        className={cx(
                          'relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition-all',
                          form.slide.pptx_file
                            ? 'border-accent bg-accent/5'
                            : 'border-border hover:border-accent/50 hover:bg-bg-elev/50 cursor-pointer',
                        )}
                      >
                        <input
                          type="file"
                          accept=".pptx"
                          className="absolute inset-0 cursor-pointer opacity-0"
                          onChange={(e) => {
                            const file = e.target.files?.[0] ?? null
                            if (file) {
                              const guessedTitle = file.name.replace(/\.[^/.]+$/, '')
                              update({
                                title: form.title || guessedTitle,
                                slide: { ...form.slide, pptx_file: file },
                              })
                            }
                          }}
                        />
                        <div className="flex flex-col items-center text-center">
                          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-accent/15 text-accent mb-2">
                            <Presentation size={24} />
                          </div>
                          {form.slide.pptx_file ? (
                            <div className="space-y-1">
                              <div className="flex items-center gap-1.5 font-medium text-accent">
                                <CheckCircle2 size={16} />
                                <span>{form.slide.pptx_file.name}</span>
                              </div>
                              <p className="text-xs text-muted">
                                {(form.slide.pptx_file.size / (1024 * 1024)).toFixed(2)} MB · 點擊可更換檔案
                              </p>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <p className="text-sm font-medium">{t('slide_upload_hint')}</p>
                              <p className="text-xs text-muted">支援 Office PowerPoint .pptx 格式</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </Field>

                    {/* Companion Speaker Guide */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-medium text-muted">{t('slide_guide_label')}</label>
                        <label className="btn-ghost btn-xs cursor-pointer flex items-center gap-1 text-accent">
                          <FileUp size={12} />
                          <span>{form.slide.guide_file ? form.slide.guide_file.name : t('slide_guide_file_btn')}</span>
                          <input
                            type="file"
                            accept=".md,.txt,.markdown"
                            className="hidden"
                            onChange={(e) => {
                              const f = e.target.files?.[0] ?? null
                              if (f) {
                                update({ slide: { ...form.slide, guide_file: f } })
                              }
                            }}
                          />
                        </label>
                      </div>
                      <textarea
                        className="input min-h-24 text-sm"
                        rows={4}
                        placeholder={t('slide_guide_placeholder')}
                        value={form.slide.guide_text}
                        onChange={(e) => update({ slide: { ...form.slide, guide_text: e.target.value } })}
                      />
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <Field label={`${t('title_label')} · ${t('optional')}`}>
                        <input
                          className="input"
                          placeholder={t('title_placeholder')}
                          value={form.title}
                          onChange={(e) => update({ title: e.target.value })}
                        />
                      </Field>
                      <Field label={t('language')}>
                        <select className="input" value={form.language} onChange={(e) => update({ language: e.target.value })}>
                          {presets.languages.map((l) => (
                            <option key={l.id} value={l.id}>
                              {l.label}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>
                  </div>
                ) : form.input_mode === 'video' ? (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-purple-500/20 bg-purple-500/5 p-3.5 text-xs text-text leading-relaxed">
                      {t('clone_video_subtitle')}
                    </div>

                    {/* Video File Upload */}
                    <Field label={t('clone_video_upload_label')}>
                      <div
                        className={cx(
                          'relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition-all',
                          form.video_file
                            ? 'border-purple-500 bg-purple-500/5'
                            : 'border-border hover:border-purple-500/50 hover:bg-bg-elev/50 cursor-pointer',
                        )}
                      >
                        <input
                          type="file"
                          accept="video/*,.mp4,.mov,.webm,.mkv"
                          className="absolute inset-0 cursor-pointer opacity-0"
                          onChange={(e) => {
                            const file = e.target.files?.[0] ?? null
                            if (file) {
                              const guessedTitle = file.name.replace(/\.[^/.]+$/, '')
                              update({
                                title: form.title || guessedTitle,
                                video_file: file,
                              })
                            }
                          }}
                        />
                        <div className="flex flex-col items-center text-center">
                          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-purple-500/15 text-purple-400 mb-2">
                            <Video size={24} />
                          </div>
                          {form.video_file ? (
                            <div className="space-y-1">
                              <div className="flex items-center gap-1.5 font-medium text-purple-400">
                                <CheckCircle2 size={16} />
                                <span>{form.video_file.name}</span>
                              </div>
                              <p className="text-xs text-muted">
                                {(form.video_file.size / (1024 * 1024)).toFixed(2)} MB · 點擊可更換影片檔案
                              </p>
                            </div>
                          ) : (
                            <div className="space-y-1">
                              <p className="text-sm font-medium">{t('clone_video_upload_hint')}</p>
                              <p className="text-xs text-muted">AI 將抽取關鍵畫面鏡頭、分析主題與視覺風格並建立分鏡</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </Field>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <Field label={`${t('title_label')} · ${t('optional')}`}>
                        <input
                          className="input"
                          placeholder={t('title_placeholder')}
                          value={form.title}
                          onChange={(e) => update({ title: e.target.value })}
                        />
                      </Field>
                      <Field label={t('language')}>
                        <select className="input" value={form.language} onChange={(e) => update({ language: e.target.value })}>
                          {presets.languages.map((l) => (
                            <option key={l.id} value={l.id}>
                              {l.label}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>
                  </div>
                ) : (
                  <>
                    <Field
                      label={
                        isPrompt
                          ? t('prompt_label')
                          : isTopic
                            ? t('topic_label')
                            : t('script_label')
                      }
                    >
                      <textarea
                        className="input min-h-40"
                        rows={isPrompt ? 4 : isTopic ? 5 : 10}
                        placeholder={
                          isPrompt
                            ? t('prompt_placeholder')
                            : isTopic
                              ? t('topic_placeholder')
                              : t('script_placeholder')
                        }
                        value={form.topic}
                        onChange={(e) => update({ topic: e.target.value })}
                        required
                      />
                    </Field>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                      <Field label={`${t('title_label')} · ${t('optional')}`}>
                        <input
                          className="input"
                          placeholder={t('title_placeholder')}
                          value={form.title}
                          onChange={(e) => update({ title: e.target.value })}
                        />
                      </Field>
                      <Field label={t('language')}>
                        <select className="input" value={form.language} onChange={(e) => update({ language: e.target.value })}>
                          {presets.languages.map((l) => (
                            <option key={l.id} value={l.id}>
                              {l.label}
                            </option>
                          ))}
                        </select>
                      </Field>
                    </div>

                    {isTopic && (
                      <Field label={t('n_scenes')} right={String(form.n_scenes)}>
                        <input
                          type="range"
                          min={3}
                          max={15}
                          step={1}
                          value={form.n_scenes}
                          onChange={(e) => update({ n_scenes: Number(e.target.value) })}
                        />
                      </Field>
                    )}
                  </>
                )}
              </div>
            </SectionCard>
          )}

          <VisualCard
            value={form.visual}
            onChange={(patch) => update({ visual: { ...form.visual, ...patch } })}
            styles={styles}
            ratios={presets.aspect_ratios}
          />
        </div>

        {/* Right column: audio + output */}
        <div className="space-y-6">
          <SectionCard title={t('section_audio')} description={isSeries ? t('series_defaults_note') : undefined}>
            <OutputSettingsFields
              value={form.output}
              onChange={(patch) => update({ output: { ...form.output, ...patch } })}
              voices={voices}
              bgm={bgm}
              motions={presets.motions}
              videoModes={presets.video_modes ?? DEFAULT_VIDEO_MODES}
            />
          </SectionCard>

          <div className="card sticky top-20 space-y-3 p-5">
            {submitError && <ErrorAlert message={submitError} />}
            {isSeries && (
              <p className="flex items-start gap-2 text-[11px] leading-relaxed text-muted">
                <Info size={13} className="mt-0.5 shrink-0 text-accent" />
                {t('kind_series_desc')}
              </p>
            )}
            <button type="submit" className="btn-primary w-full py-2.5" disabled={busy}>
              {submitting === 'start' || submitting === 'upload' ? (
                <Spinner size={16} />
              ) : isSeries ? (
                <ScanSearch size={16} />
              ) : (
                <Sparkles size={16} />
              )}
              {submitting === 'upload' ? t('uploading_source') : submitting === 'start' ? t('creating') : startLabel}
            </button>
            <button type="button" className="btn-secondary w-full" disabled={busy} onClick={() => void submit(false)}>
              {submitting === 'create' ? <Spinner size={16} /> : <Wand2 size={16} />}
              {submitting === 'create' ? t('creating') : t('create_only')}
            </button>
          </div>
        </div>
      </div>
    </form>
  )
}
