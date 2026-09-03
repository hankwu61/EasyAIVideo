import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Info, ScanSearch, Sparkles, Wand2 } from 'lucide-react'
import { analyzeProject, createProject, errorMessage, uploadSource } from '../api'
import KindPicker, { DEFAULT_KINDS } from '../components/new/KindPicker'
import SeriesContentCard, { DEFAULT_CONTENT_MODES, type SeriesContent } from '../components/new/SeriesContentCard'
import VisualCard, { type VisualSettings } from '../components/new/VisualCard'
import { DEFAULT_VIDEO_MODES, OutputSettingsFields, type OutputSettings } from '../components/ProjectSettingsFields'
import { useToast } from '../components/Toast'
import { ErrorAlert, Field, PageHeader, SectionCard, Skeleton, Spinner } from '../components/ui'
import { useResources } from '../hooks/useResources'
import { useLang } from '../i18n'
import type { AspectRatio, InputMode, ProjectCreate, ProjectKind } from '../types'
import { cx } from '../utils'

interface FormState {
  kind: ProjectKind
  input_mode: InputMode
  topic: string
  title: string
  language: string
  n_scenes: number
  visual: VisualSettings
  series: SeriesContent
  output: OutputSettings
}

type Phase = 'start' | 'create' | 'upload' | null

export default function NewProjectPage() {
  const { t } = useLang()
  const toast = useToast()
  const navigate = useNavigate()
  const { resources, loading, error, reload } = useResources()

  const [form, setForm] = useState<FormState | null>(null)
  const [submitting, setSubmitting] = useState<Phase>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)

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
      output: {
        voice: zhVoice?.id ?? '',
        tts_speed: 1.0,
        bgm: null,
        bgm_volume: 0.2,
        motion: presets.motions[0]?.id ?? 'kenburns',
        video_mode: null,
        subtitle_enabled: true,
        show_title: true,
      },
    })
  }, [resources, form])

  const update = (patch: Partial<FormState>) => setForm((f) => (f ? { ...f, ...patch } : f))

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
      n_scenes: form.n_scenes,
      ...form.output,
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

  const submit = async (autoStart: boolean) => {
    if (!form) return
    setSubmitError(null)
    try {
      if (form.kind === 'series') await submitSeries(form, autoStart)
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
  const isTopic = form.input_mode === 'topic'
  const startLabel = isSeries ? t('create_and_analyze') : t('create_and_start')
  const busy = submitting !== null

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        void submit(true)
      }}
    >
      {header}

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
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
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
                            onChange={() => update({ input_mode: m.id as InputMode })}
                            className="accent-accent"
                          />
                          {m.label}
                        </label>
                      )
                    })}
                  </div>
                </Field>

                <Field label={isTopic ? t('topic_label') : t('script_label')}>
                  <textarea
                    className="input min-h-40"
                    rows={isTopic ? 5 : 10}
                    placeholder={isTopic ? t('topic_placeholder') : t('script_placeholder')}
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
