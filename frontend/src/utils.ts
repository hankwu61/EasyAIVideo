import { t } from './i18n'

/** 65.4 -> "1:05"; 3725 -> "1:02:05" */
export function formatDuration(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec)) return '--:--'
  const total = Math.max(0, Math.round(sec))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m)
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** Short seconds display for scene durations: 5.83 -> "5.8s" */
export function formatSeconds(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec)) return '--'
  return `${sec.toFixed(1)}s`
}

export function formatBytes(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '--'
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[i]}`
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return ''
  const diff = Math.max(0, Date.now() - then)
  const min = Math.floor(diff / 60000)
  if (min < 1) return t('just_now')
  if (min < 60) return t('minutes_ago', { n: min })
  const hr = Math.floor(min / 60)
  if (hr < 24) return t('hours_ago', { n: hr })
  const day = Math.floor(hr / 24)
  if (day < 30) return t('days_ago', { n: day })
  return new Date(iso).toLocaleDateString()
}

/** Tailwind class joiner. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

export function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}
