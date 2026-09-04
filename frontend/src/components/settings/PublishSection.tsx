import { useLang } from '../../i18n'
import type { PublishConfig, PublishPrivacy } from '../../types'
import { Field, SectionCard } from '../ui'
import { SecretInput } from './ProviderSections'
import TestButton from './TestButton'

export default function PublishSection({
  value,
  onChange,
  beforeTest,
}: {
  value: PublishConfig
  onChange: (patch: Partial<PublishConfig>) => void
  beforeTest: () => Promise<boolean>
}) {
  const { t } = useLang()

  const yt = value.youtube
  const tt = value.tiktok
  const wh = value.webhook

  const updateYt = (patch: Partial<typeof yt>) => {
    onChange({ youtube: { ...yt, ...patch } })
  }

  const updateTt = (patch: Partial<typeof tt>) => {
    onChange({ tiktok: { ...tt, ...patch } })
  }

  const updateWh = (patch: Partial<typeof wh>) => {
    onChange({ webhook: { ...wh, ...patch } })
  }

  return (
    <SectionCard title={t('sec_publish')} description={t('sec_publish_desc')}>
      <div className="space-y-6">
        {/* YouTube Shorts */}
        <div className="rounded-xl border border-border bg-panel-2/30 p-4">
          <div className="flex items-center justify-between border-b border-border/60 pb-3">
            <div>
              <h3 className="text-sm font-semibold text-text">{t('yt_settings')}</h3>
              <p className="text-xs text-muted">YouTube Shorts (9:16)</p>
            </div>
            <TestButton kind="youtube" beforeTest={beforeTest} />
          </div>

          <div className="mt-4 space-y-4">
            <label className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-border/60 bg-bg-elev p-2.5 text-xs">
              <input
                type="checkbox"
                checked={yt.mock}
                onChange={(e) => updateYt({ mock: e.target.checked })}
                className="h-4 w-4 rounded accent-accent"
              />
              <span className="font-medium text-text">{t('yt_mock_mode')}</span>
            </label>

            {!yt.mock && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label={t('yt_client_id')}>
                  <input
                    type="text"
                    className="input font-mono text-xs"
                    value={yt.client_id}
                    onChange={(e) => updateYt({ client_id: e.target.value })}
                    placeholder="xxxxxxxx.apps.googleusercontent.com"
                  />
                </Field>
                <Field label={t('yt_client_secret')}>
                  <SecretInput
                    value={yt.client_secret}
                    onChange={(client_secret) => updateYt({ client_secret })}
                    placeholder="GOCSPX-..."
                  />
                </Field>
                <Field label={t('yt_refresh_token')} className="sm:col-span-2">
                  <SecretInput
                    value={yt.refresh_token}
                    onChange={(refresh_token) => updateYt({ refresh_token })}
                    placeholder="1//04..."
                  />
                </Field>
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label={t('publish_privacy')}>
                <select
                  className="input text-xs"
                  value={yt.default_privacy}
                  onChange={(e) => updateYt({ default_privacy: e.target.value as PublishPrivacy })}
                >
                  <option value="public">{t('privacy_public')}</option>
                  <option value="unlisted">{t('privacy_unlisted')}</option>
                  <option value="private">{t('privacy_private')}</option>
                </select>
              </Field>
              <Field label={t('publish_tags_label')}>
                <input
                  type="text"
                  className="input text-xs"
                  value={yt.default_tags}
                  onChange={(e) => updateYt({ default_tags: e.target.value })}
                  placeholder="Shorts, AI, Drama"
                />
              </Field>
            </div>
          </div>
        </div>

        {/* TikTok */}
        <div className="rounded-xl border border-border bg-panel-2/30 p-4">
          <div className="flex items-center justify-between border-b border-border/60 pb-3">
            <div>
              <h3 className="text-sm font-semibold text-text">{t('tt_settings')}</h3>
              <p className="text-xs text-muted">TikTok Content Posting API</p>
            </div>
            <TestButton kind="tiktok" beforeTest={beforeTest} />
          </div>

          <div className="mt-4 space-y-4">
            <label className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-border/60 bg-bg-elev p-2.5 text-xs">
              <input
                type="checkbox"
                checked={tt.mock}
                onChange={(e) => updateTt({ mock: e.target.checked })}
                className="h-4 w-4 rounded accent-accent"
              />
              <span className="font-medium text-text">{t('tt_mock_mode')}</span>
            </label>

            {!tt.mock && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label={t('tt_client_key')}>
                  <input
                    type="text"
                    className="input font-mono text-xs"
                    value={tt.client_key}
                    onChange={(e) => updateTt({ client_key: e.target.value })}
                  />
                </Field>
                <Field label={t('tt_client_secret')}>
                  <SecretInput
                    value={tt.client_secret}
                    onChange={(client_secret) => updateTt({ client_secret })}
                  />
                </Field>
                <Field label={t('tt_access_token')} className="sm:col-span-2">
                  <SecretInput
                    value={tt.access_token}
                    onChange={(access_token) => updateTt({ access_token })}
                    placeholder="act.example..."
                  />
                </Field>
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label={t('publish_privacy')}>
                <select
                  className="input text-xs"
                  value={tt.default_privacy}
                  onChange={(e) => updateTt({ default_privacy: e.target.value as PublishPrivacy })}
                >
                  <option value="public">{t('privacy_public')}</option>
                  <option value="unlisted">{t('privacy_unlisted')}</option>
                  <option value="private">{t('privacy_private')}</option>
                </select>
              </Field>
              <Field label={t('publish_tags_label')}>
                <input
                  type="text"
                  className="input text-xs"
                  value={tt.default_tags}
                  onChange={(e) => updateTt({ default_tags: e.target.value })}
                  placeholder="fyp, shorts, easyaivideo"
                />
              </Field>
            </div>
          </div>
        </div>

        {/* Webhook */}
        <div className="rounded-xl border border-border bg-panel-2/30 p-4">
          <div className="flex items-center justify-between border-b border-border/60 pb-3">
            <div>
              <h3 className="text-sm font-semibold text-text">{t('webhook_settings')}</h3>
              <p className="text-xs text-muted">Make / Zapier / n8n / Ayrshare</p>
            </div>
            <TestButton kind="webhook" beforeTest={beforeTest} />
          </div>

          <div className="mt-4 space-y-4">
            <label className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-border/60 bg-bg-elev p-2.5 text-xs">
              <input
                type="checkbox"
                checked={wh.enabled}
                onChange={(e) => updateWh({ enabled: e.target.checked })}
                className="h-4 w-4 rounded accent-accent"
              />
              <span className="font-medium text-text">{t('webhook_enable')}</span>
            </label>

            {wh.enabled && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label={t('webhook_url')} className="sm:col-span-2">
                  <input
                    type="url"
                    className="input font-mono text-xs"
                    value={wh.url}
                    onChange={(e) => updateWh({ url: e.target.value })}
                    placeholder="https://hook.make.com/..."
                  />
                </Field>
                <Field label={t('webhook_secret')} className="sm:col-span-2">
                  <SecretInput
                    value={wh.secret}
                    onChange={(secret) => updateWh({ secret })}
                    placeholder="Optional secret verification header"
                  />
                </Field>
              </div>
            )}
          </div>
        </div>
      </div>
    </SectionCard>
  )
}
