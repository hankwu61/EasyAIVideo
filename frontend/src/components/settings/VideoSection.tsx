import { useEffect, useState } from 'react'
import { Info } from 'lucide-react'
import { useLang } from '../../i18n'
import type { IdLabel, VideoConfig, VideoMode, VideoProvider, VideoResolution, Workflows } from '../../types'
import { Field, SectionCard } from '../ui'
import { NumberInput, SecretInput } from './ProviderSections'
import TestButton from './TestButton'
import { WorkflowSelect } from './MediaSections'

const RESOLUTIONS: VideoResolution[] = ['480p', '720p', '1080p']

type MinimaxResolution = '480P' | '768P' | '2K'
const MINIMAX_INTL = 'https://api.minimax.io'
const MINIMAX_CN = 'https://api.minimaxi.com'
const MINIMAX_MODELS = ['MiniMax-H3', 'MiniMax-H3-Max']
/** Output resolutions per model (MiniMax API docs: H3 = 768P / 2K, H3-Max = 480P / 768P). */
const MINIMAX_RES: Record<string, MinimaxResolution[]> = {
  'MiniMax-H3': ['768P', '2K'],
  'MiniMax-H3-Max': ['480P', '768P'],
}
type ComfyH3Model = 'MiniMax H3' | 'MiniMax H3 Max' | 'MiniMax H3 Max Turbo'
const COMFY_H3_MODELS: ComfyH3Model[] = ['MiniMax H3', 'MiniMax H3 Max', 'MiniMax H3 Max Turbo']
const COMFY_H3_RES_KEY: Record<ComfyH3Model, string> = {
  'MiniMax H3': 'MiniMax-H3',
  'MiniMax H3 Max': 'MiniMax-H3-Max',
  'MiniMax H3 Max Turbo': 'MiniMax-H3-Max',
}
const COMFY_H3_HINT = {
  'MiniMax H3': 'comfy_h3_model_h3_hint',
  'MiniMax H3 Max': 'comfy_h3_model_max_hint',
  'MiniMax H3 Max Turbo': 'comfy_h3_model_turbo_hint',
} as const
/** USD per second from the ComfyUI node price badge (comfy_api_nodes/nodes_minimax.py). */
const COMFY_H3_PRICE: Record<ComfyH3Model, Record<string, string>> = {
  'MiniMax H3': { '768P': '0.1287', '2K': '0.1859' },
  'MiniMax H3 Max': { '480P': '0.0715', '768P': '0.1144' },
  'MiniMax H3 Max Turbo': { '480P': '0.03575', '768P': '0.0572' },
}
const AGNES_DEFAULTS = { base_url: 'https://apihub.agnes-ai.com/v1', model: 'agnes-video-2.5-flash' }

/** Mirrors the backend: strip /v1 or /v2; anything that is not a MiniMax host falls back to the international API. */
function minimaxRoot(baseUrl: string): string {
  let b = (baseUrl || '').trim().replace(/\/+$/, '')
  if (!b || !b.toLowerCase().includes('minimax')) return MINIMAX_INTL
  b = b.replace(/\/v[12]$/, '')
  return b
}

/** Default connection values when the provider is switched, so another provider's URL / model never leaks in. */
function providerDefaults(provider: VideoProvider, current: VideoConfig): Partial<VideoConfig> {
  if (provider === 'minimax') {
    const patch: Partial<VideoConfig> = {}
    if (!(current.base_url || '').toLowerCase().includes('minimax')) patch.base_url = MINIMAX_INTL
    if (!MINIMAX_MODELS.includes(current.model)) patch.model = 'MiniMax-H3'
    if (current.max_clip_seconds > 15 || current.max_clip_seconds < 4) patch.max_clip_seconds = Math.max(4, Math.min(15, current.max_clip_seconds))
    return patch
  }
  if (provider === 'comfyui_minimax') {
    const patch: Partial<VideoConfig> = {}
    if (current.max_clip_seconds > 15 || current.max_clip_seconds < 4) patch.max_clip_seconds = Math.max(4, Math.min(15, current.max_clip_seconds))
    if (!current.comfyui_url) patch.comfyui_url = 'http://127.0.0.1:8188'
    return patch
  }
  if (provider === 'agnes') {
    const patch: Partial<VideoConfig> = {}
    if (!(current.base_url || '').toLowerCase().includes('agnes')) patch.base_url = AGNES_DEFAULTS.base_url
    if (!(current.model || '').toLowerCase().startsWith('agnes')) patch.model = AGNES_DEFAULTS.model
    return patch
  }
  return {}
}

const modeHintKey = {
  i2v: 'video_mode_hint_i2v',
  t2v: 'video_mode_hint_t2v',
  keyframes: 'video_mode_hint_keyframes',
} as const

export default function VideoSection({
  value,
  onChange,
  beforeTest,
  workflows,
  videoModes,
}: {
  value: VideoConfig
  onChange: (patch: Partial<VideoConfig>) => void
  beforeTest: () => Promise<boolean>
  workflows: Workflows | null
  videoModes: IdLabel[]
}) {
  const { t } = useLang()
  const comfy = value.provider === 'comfyui'
  const agnes = value.provider === 'agnes'
  const minimax = value.provider === 'minimax'
  const comfyMinimax = value.provider === 'comfyui_minimax'
  const cmModel: ComfyH3Model = COMFY_H3_MODELS.includes(value.comfyui_h3_model as ComfyH3Model)
    ? (value.comfyui_h3_model as ComfyH3Model)
    : 'MiniMax H3'
  const cmMinSec = cmModel === 'MiniMax H3' ? 4 : 5
  const cmResList = MINIMAX_RES[COMFY_H3_RES_KEY[cmModel]]
  const cmRes = cmResList.includes(value.minimax_resolution ?? '768P') ? (value.minimax_resolution ?? '768P') : '768P'
  const hintKey = modeHintKey[value.mode as VideoMode]
  const mmModel = MINIMAX_MODELS.includes(value.model) ? value.model : 'MiniMax-H3'
  const mmMinSec = mmModel === 'MiniMax-H3-Max' ? 5 : 4
  const mmRoot = minimaxRoot(value.base_url)
  const mmKnown = [MINIMAX_INTL, MINIMAX_CN].includes((value.base_url || '').trim().replace(/\/+$/, '').replace(/\/v[12]$/, ''))
  const [customEndpoint, setCustomEndpoint] = useState(false)
  const mmEndpointChoice = customEndpoint
    ? 'custom'
    : !(value.base_url || '').toLowerCase().includes('minimax')
      ? MINIMAX_INTL
      : mmKnown
        ? (value.base_url || '').trim().replace(/\/+$/, '').replace(/\/v[12]$/, '')
        : 'custom'
  // Settings saved before the MiniMax H3 integration may still carry another provider's URL / model.
  const needsMinimaxFix =
    minimax && (!(value.base_url || '').toLowerCase().includes('minimax') || !MINIMAX_MODELS.includes(value.model))
  useEffect(() => {
    if (needsMinimaxFix) onChange(providerDefaults('minimax', value))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needsMinimaxFix])
  const apiKeyLooksWrong = /^https?:\/\//i.test((value.api_key || '').trim())
  return (
    <SectionCard
      title={t('sec_video')}
      description={t('sec_video_desc')}
      actions={value.provider !== 'kenburns' ? <TestButton kind="video" beforeTest={beforeTest} /> : undefined}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label={t('provider')}>
          <select
            className="input"
            value={value.provider}
            onChange={(e) => {
              const provider = e.target.value as VideoProvider
              onChange({ provider, ...providerDefaults(provider, value) })
            }}
          >
            <option value="kenburns">{t('provider_kenburns')}</option>
            <option value="comfyui">{t('provider_comfyui')}</option>
            <option value="agnes">{t('provider_agnes')}</option>
            <option value="minimax">{t('provider_minimax')}</option>
            <option value="comfyui_minimax">{t('provider_comfyui_minimax')}</option>
          </select>
        </Field>
        <Field label={t('fps')}>
          <NumberInput value={value.fps} onChange={(fps) => onChange({ fps })} min={1} max={120} step={1} />
        </Field>

        {minimax && (
          <>
            <Field label={t('api_key')} hint={`${t('minimax_api_key_hint')} ${t('api_key_hint')}`} className="sm:col-span-2">
              <SecretInput value={value.api_key} onChange={(api_key) => onChange({ api_key })} placeholder="sk-api-…" />
            </Field>
            {apiKeyLooksWrong && (
              <p className="-mt-2 text-[11px] text-danger sm:col-span-2">{t('minimax_api_key_looks_like_url')}</p>
            )}
            <Field label={t('base_url')} hint={`${t('minimax_effective_endpoint')}: ${mmRoot}/v2/video_generation`}>
              <select
                className="input font-mono"
                value={mmEndpointChoice}
                onChange={(e) => {
                  const v = e.target.value
                  setCustomEndpoint(v === 'custom')
                  if (v !== 'custom') onChange({ base_url: v })
                }}
              >
                <option value={MINIMAX_INTL}>{t('minimax_endpoint_intl')}</option>
                <option value={MINIMAX_CN}>{t('minimax_endpoint_cn')}</option>
                <option value="custom">{t('minimax_endpoint_custom')}</option>
              </select>
              {mmEndpointChoice === 'custom' && (
                <input
                  className="input mt-2 font-mono"
                  value={value.base_url}
                  placeholder="https://your-proxy.example.com"
                  onChange={(e) => onChange({ base_url: e.target.value })}
                />
              )}
            </Field>
            <Field label={t('model')} hint={t(mmModel === 'MiniMax-H3-Max' ? 'minimax_model_h3max_hint' : 'minimax_model_h3_hint')}>
              <select
                className="input font-mono"
                value={mmModel}
                onChange={(e) => {
                  const model = e.target.value
                  const allowed = MINIMAX_RES[model]
                  const res = value.minimax_resolution ?? '768P'
                  onChange({ model, ...(allowed.includes(res) ? {} : { minimax_resolution: '768P' }) })
                }}
              >
                <option value="MiniMax-H3">MiniMax-H3</option>
                <option value="MiniMax-H3-Max">MiniMax-H3-Max</option>
              </select>
            </Field>
            <Field label={t('minimax_resolution')}>
              <select
                className="input"
                value={MINIMAX_RES[mmModel].includes(value.minimax_resolution ?? '768P') ? value.minimax_resolution ?? '768P' : '768P'}
                onChange={(e) => onChange({ minimax_resolution: e.target.value as MinimaxResolution })}
              >
                {MINIMAX_RES[mmModel].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('video_gen_mode')} hint={hintKey ? t(hintKey) : undefined}>
              <select className="input" value={value.mode} onChange={(e) => onChange({ mode: e.target.value as VideoMode })}>
                {!videoModes.some((m) => m.id === value.mode) && value.mode && (
                  <option value={value.mode}>{value.mode}</option>
                )}
                {videoModes.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('max_clip_seconds')} hint={t('minimax_clip_hint', { min: mmMinSec })}>
              <NumberInput
                value={Math.max(mmMinSec, Math.min(15, value.max_clip_seconds))}
                onChange={(max_clip_seconds) => onChange({ max_clip_seconds })}
                min={mmMinSec}
                max={15}
                step={1}
              />
            </Field>
            <Field label={t('concurrency')} hint={t('minimax_concurrency_hint')}>
              <NumberInput
                value={value.concurrency}
                onChange={(concurrency) => onChange({ concurrency })}
                min={1}
                max={4}
                step={1}
              />
            </Field>
            <Field label={t('poll_timeout')}>
              <NumberInput
                value={value.poll_timeout}
                onChange={(poll_timeout) => onChange({ poll_timeout })}
                min={60}
                max={7200}
                step={60}
              />
            </Field>
          </>
        )}

        {comfyMinimax && (
          <>
            <Field label={t('comfyui_url')}>
              <input
                className="input font-mono"
                value={value.comfyui_url}
                placeholder="http://127.0.0.1:8188"
                onChange={(e) => onChange({ comfyui_url: e.target.value })}
              />
            </Field>
            <Field label={t('comfy_api_key')} hint={`${t('comfy_api_key_hint')} ${t('api_key_hint')}`}>
              <SecretInput
                value={value.comfy_api_key ?? ''}
                onChange={(comfy_api_key) => onChange({ comfy_api_key })}
                placeholder="comfyui-…"
              />
            </Field>
            <Field label={t('model')} hint={t(COMFY_H3_HINT[cmModel])}>
              <select
                className="input font-mono"
                value={cmModel}
                onChange={(e) => {
                  const model = e.target.value as ComfyH3Model
                  const allowed = MINIMAX_RES[COMFY_H3_RES_KEY[model]]
                  const res = value.minimax_resolution ?? '768P'
                  onChange({ comfyui_h3_model: model, ...(allowed.includes(res) ? {} : { minimax_resolution: '768P' }) })
                }}
              >
                {COMFY_H3_MODELS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('minimax_resolution')} hint={t('comfy_h3_price_hint', { price: COMFY_H3_PRICE[cmModel][cmRes] })}>
              <select
                className="input"
                value={cmRes}
                onChange={(e) => onChange({ minimax_resolution: e.target.value as MinimaxResolution })}
              >
                {MINIMAX_RES[COMFY_H3_RES_KEY[cmModel]].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('video_gen_mode')} hint={hintKey ? t(hintKey) : undefined}>
              <select className="input" value={value.mode} onChange={(e) => onChange({ mode: e.target.value as VideoMode })}>
                {!videoModes.some((m) => m.id === value.mode) && value.mode && (
                  <option value={value.mode}>{value.mode}</option>
                )}
                {videoModes.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('max_clip_seconds')} hint={t('minimax_clip_hint', { min: cmMinSec })}>
              <NumberInput
                value={Math.max(cmMinSec, Math.min(15, value.max_clip_seconds))}
                onChange={(max_clip_seconds) => onChange({ max_clip_seconds })}
                min={cmMinSec}
                max={15}
                step={1}
              />
            </Field>
            <Field label={t('concurrency')} hint={t('minimax_concurrency_hint')}>
              <NumberInput value={value.concurrency} onChange={(concurrency) => onChange({ concurrency })} min={1} max={4} step={1} />
            </Field>
            <Field label={t('poll_timeout')}>
              <NumberInput value={value.poll_timeout} onChange={(poll_timeout) => onChange({ poll_timeout })} min={60} max={7200} step={60} />
            </Field>
            <p className="rounded-lg border border-accent/30 bg-accent/5 px-3 py-2 text-[11px] leading-relaxed text-muted sm:col-span-2">
              {t('comfy_h3_modes_note')}
            </p>
          </>
        )}

        {agnes && (
          <>
            <Field label={t('api_key')} hint={t('api_key_hint')} className="sm:col-span-2">
              <SecretInput value={value.api_key} onChange={(api_key) => onChange({ api_key })} placeholder="sk-…" />
            </Field>
            <Field label={t('base_url')}>
              <input
                className="input font-mono"
                value={value.base_url}
                placeholder="https://apihub.agnes-ai.com/v1"
                onChange={(e) => onChange({ base_url: e.target.value })}
              />
            </Field>
            <Field label={t('model')} hint={value.model?.includes('flash') ? t('agnes_flash_hint') : undefined}>
              <input
                className="input font-mono"
                value={value.model}
                placeholder="agnes-video-2.5-flash"
                list="agnes-video-models"
                onChange={(e) => onChange({ model: e.target.value })}
              />
              <datalist id="agnes-video-models">
                <option value="agnes-video-2.5-flash">agnes-video-2.5-flash（限時免費 / 720P）</option>
                <option value="agnes-video-2.5">agnes-video-2.5（標準版 / 支援 720P~2K）</option>
              </datalist>
            </Field>
            <Field label={t('resolution')}>
              <select
                className="input"
                value={value.resolution}
                onChange={(e) => onChange({ resolution: e.target.value as VideoResolution })}
              >
                {!RESOLUTIONS.includes(value.resolution) && value.resolution && (
                  <option value={value.resolution}>{value.resolution}</option>
                )}
                {RESOLUTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('video_gen_mode')} hint={hintKey ? t(hintKey) : undefined}>
              <select className="input" value={value.mode} onChange={(e) => onChange({ mode: e.target.value as VideoMode })}>
                {!videoModes.some((m) => m.id === value.mode) && value.mode && (
                  <option value={value.mode}>{value.mode}</option>
                )}
                {videoModes.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t('max_clip_seconds')}>
              <NumberInput
                value={value.max_clip_seconds}
                onChange={(max_clip_seconds) => onChange({ max_clip_seconds })}
                min={1}
                max={18}
                step={1}
              />
            </Field>
            <Field label={t('concurrency')}>
              <NumberInput
                value={value.concurrency}
                onChange={(concurrency) => onChange({ concurrency })}
                min={1}
                max={4}
                step={1}
              />
            </Field>
          </>
        )}

        {comfy && (
          <>
            <Field label={t('comfyui_url')}>
              <input
                className="input font-mono"
                value={value.comfyui_url}
                onChange={(e) => onChange({ comfyui_url: e.target.value })}
              />
            </Field>
            <Field label={t('comfyui_workflow')}>
              <WorkflowSelect
                options={workflows?.video ?? []}
                value={value.comfyui_workflow}
                onChange={(comfyui_workflow) => onChange({ comfyui_workflow })}
              />
            </Field>
          </>
        )}

        <p className="flex items-start gap-2 rounded-lg border border-border bg-bg-elev px-3 py-2 text-[11px] leading-relaxed text-muted sm:col-span-2">
          <Info size={13} className="mt-0.5 shrink-0 text-accent" />
          {minimax || comfyMinimax ? t('minimax_video_note') : t('ai_video_note')}
        </p>
      </div>
    </SectionCard>
  )
}
