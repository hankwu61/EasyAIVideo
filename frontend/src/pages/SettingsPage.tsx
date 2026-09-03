import { useCallback, useEffect, useRef, useState } from 'react'
import { Save } from 'lucide-react'
import { errorMessage, getConfig, getHealth, getPresets, getVoices, getWorkflows, putConfig } from '../api'
import HealthCard from '../components/settings/HealthCard'
import { ImageSection, RenderSection } from '../components/settings/MediaSections'
import { LlmSection, TtsSection } from '../components/settings/ProviderSections'
import VideoSection from '../components/settings/VideoSection'
import { DEFAULT_VIDEO_MODES } from '../components/ProjectSettingsFields'
import { useToast } from '../components/Toast'
import { ErrorAlert, PageHeader, Skeleton, Spinner } from '../components/ui'
import { useLang } from '../i18n'
import type { Config, Health, Presets, VoiceOption, Workflows } from '../types'

export default function SettingsPage() {
  const { t } = useLang()
  const toast = useToast()

  const [config, setConfig] = useState<Config | null>(null)
  const [saved, setSaved] = useState<Config | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [presets, setPresets] = useState<Presets | null>(null)
  const [workflows, setWorkflows] = useState<Workflows | null>(null)
  const [voices, setVoices] = useState<VoiceOption[]>([])

  const loadHealth = useCallback(async () => {
    setHealthError(null)
    try {
      setHealth(await getHealth())
    } catch (e) {
      setHealthError(errorMessage(e))
    }
  }, [])

  const loadVoices = useCallback(async () => {
    try {
      setVoices(await getVoices())
    } catch {
      setVoices([])
    }
  }, [])

  const load = useCallback(async () => {
    setLoadError(null)
    try {
      const cfg = await getConfig()
      setConfig(cfg)
      setSaved(cfg)
    } catch (e) {
      setLoadError(errorMessage(e))
    }
    void loadHealth()
    void loadVoices()
    void getPresets()
      .then(setPresets)
      .catch(() => setPresets(null))
    void getWorkflows()
      .then(setWorkflows)
      .catch(() => setWorkflows({ image: [], video: [] }))
  }, [loadHealth, loadVoices])

  useEffect(() => {
    void load()
  }, [load])

  const dirty = !!config && !!saved && JSON.stringify(config) !== JSON.stringify(saved)

  // Latest config in a ref so beforeTest closures always save the current draft.
  const configRef = useRef(config)
  configRef.current = config
  const savedRef = useRef(saved)
  savedRef.current = saved

  const save = useCallback(async (): Promise<boolean> => {
    const current = configRef.current
    if (!current) return false
    setSaving(true)
    try {
      const merged = await putConfig(current)
      setConfig(merged)
      setSaved(merged)
      toast.success(t('settings_saved'))
      void loadHealth()
      void loadVoices()
      return true
    } catch (e) {
      toast.error(errorMessage(e))
      return false
    } finally {
      setSaving(false)
    }
  }, [toast, t, loadHealth, loadVoices])

  /** Save unsaved changes before running a connection test, so the test reflects the form. */
  const beforeTest = useCallback(async () => {
    const isDirty = JSON.stringify(configRef.current) !== JSON.stringify(savedRef.current)
    return isDirty ? save() : true
  }, [save])

  const section =
    <K extends keyof Config>(key: K) =>
    (patch: Partial<Config[K]>) =>
      setConfig((c) => (c ? { ...c, [key]: { ...c[key], ...patch } } : c))

  return (
    <div>
      <PageHeader
        title={t('settings_title')}
        subtitle={t('settings_subtitle')}
        actions={
          <button type="button" className="btn-primary" onClick={() => void save()} disabled={!config || saving}>
            {saving ? <Spinner size={15} /> : <Save size={15} />}
            {saving ? t('saving') : t('save_settings')}
          </button>
        }
      />

      <div className="space-y-6">
        <HealthCard health={health} error={healthError} onRetry={() => void loadHealth()} />

        {loadError && <ErrorAlert message={loadError} onRetry={() => void load()} />}

        {!config && !loadError && (
          <div className="space-y-6">
            <Skeleton className="h-64" />
            <Skeleton className="h-56" />
            <Skeleton className="h-64" />
          </div>
        )}

        {config && (
          <>
            <LlmSection
              value={config.llm}
              onChange={section('llm')}
              beforeTest={beforeTest}
              presets={presets?.llm_presets ?? []}
            />
            <TtsSection value={config.tts} onChange={section('tts')} beforeTest={beforeTest} voices={voices} />
            <ImageSection value={config.image} onChange={section('image')} beforeTest={beforeTest} workflows={workflows} />
            <VideoSection
              value={config.video}
              onChange={section('video')}
              beforeTest={beforeTest}
              workflows={workflows}
              videoModes={presets?.video_modes ?? DEFAULT_VIDEO_MODES}
            />
            <RenderSection value={config.render} onChange={section('render')} />

            <div className="sticky bottom-4 flex justify-end">
              <div className="card flex items-center gap-3 px-4 py-3 shadow-2xl">
                <span className="text-xs text-muted">{dirty ? t('unsaved') : t('saved')}</span>
                <button type="button" className="btn-primary" onClick={() => void save()} disabled={saving || !dirty}>
                  {saving ? <Spinner size={15} /> : <Save size={15} />}
                  {saving ? t('saving') : t('save_settings')}
                </button>
              </div>
            </div>
            <p className="text-center text-[11px] text-faint">{t('test_hint')}</p>
          </>
        )}
      </div>
    </div>
  )
}
