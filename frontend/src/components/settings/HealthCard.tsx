import { Activity, AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'
import { useLang } from '../../i18n'
import type { Health } from '../../types'
import { cx } from '../../utils'
import { ErrorAlert, Skeleton } from '../ui'

function Pill({ ok, label, value }: { ok: boolean; label: string; value: string }) {
  return (
    <div
      className={cx(
        'flex items-center gap-2 rounded-lg border px-3 py-2 text-xs',
        ok ? 'border-success/30 bg-success/10 text-success' : 'border-danger/30 bg-danger/10 text-danger',
      )}
    >
      {ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
      <span className="text-muted">{label}</span>
      <span className="ml-auto font-medium">{value}</span>
    </div>
  )
}

export default function HealthCard({
  health,
  error,
  onRetry,
}: {
  health: Health | null
  error: string | null
  onRetry: () => void
}) {
  const { t } = useLang()

  return (
    <section className="card p-5">
      <div className="mb-3 flex items-center gap-2">
        <Activity size={16} className="text-accent" />
        <h2 className="text-base font-semibold">{t('health')}</h2>
        {health && (
          <span className="chip ml-auto border-border-strong bg-panel-2 text-muted">
            {t('health_version')} {health.version}
          </span>
        )}
      </div>

      {error && <ErrorAlert message={error} onRetry={onRetry} />}
      {!error && !health && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Skeleton className="h-9" />
          <Skeleton className="h-9" />
        </div>
      )}
      {health && (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Pill ok={health.ffmpeg} label={t('health_ffmpeg')} value={health.ffmpeg ? t('available') : t('unavailable')} />
            <Pill
              ok={health.config_valid}
              label={t('health_config_valid')}
              value={health.config_valid ? t('valid') : t('invalid')}
            />
          </div>
          {health.warnings.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {health.warnings.map((w, i) => (
                <li
                  key={i}
                  className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning"
                >
                  <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                  <span className="break-words">{w}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  )
}
