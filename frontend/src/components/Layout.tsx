import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Clapperboard, Languages, Settings2 } from 'lucide-react'
import { getHealth } from '../api'
import { useLang } from '../i18n'
import { cx } from '../utils'

type HealthState = 'checking' | 'ok' | 'bad'

function useHealthDot(): HealthState {
  const [state, setState] = useState<HealthState>('checking')
  useEffect(() => {
    let cancelled = false
    const ctrl = new AbortController()
    const check = async () => {
      try {
        const h = await getHealth(ctrl.signal)
        if (!cancelled) setState(h.status === 'ok' ? 'ok' : 'bad')
      } catch {
        if (!cancelled) setState('bad')
      }
    }
    void check()
    const id = window.setInterval(check, 30000)
    return () => {
      cancelled = true
      ctrl.abort()
      window.clearInterval(id)
    }
  }, [])
  return state
}

export default function Layout() {
  const { t, lang, toggle } = useLang()
  const health = useHealthDot()

  const navClass = ({ isActive }: { isActive: boolean }) =>
    cx(
      'rounded-lg px-3 py-1.5 text-sm font-medium transition',
      isActive ? 'bg-panel-2 text-text' : 'text-muted hover:bg-panel-2/60 hover:text-text',
    )

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-border bg-bg/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-3 px-4 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 pr-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-accent to-indigo-glow text-white shadow-[0_0_0_1px_rgb(124_108_255/0.4)]">
              <Clapperboard size={16} />
            </span>
            <span className="text-[15px] font-semibold tracking-tight">{t('app_name')}</span>
          </NavLink>

          <nav className="ml-2 flex items-center gap-1">
            <NavLink to="/" end className={navClass}>
              {t('nav_projects')}
            </NavLink>
            <NavLink to="/settings" className={navClass}>
              {t('nav_settings')}
            </NavLink>
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <div
              className="flex items-center gap-2 rounded-lg border border-border bg-panel px-2.5 py-1.5 text-xs text-muted"
              title={health === 'ok' ? t('health_ok') : health === 'bad' ? t('health_bad') : t('health_checking')}
            >
              <span
                className={cx(
                  'h-2 w-2 rounded-full',
                  health === 'ok' && 'bg-success shadow-[0_0_8px_rgb(52_211_153/0.7)]',
                  health === 'bad' && 'bg-danger shadow-[0_0_8px_rgb(248_113_113/0.7)]',
                  health === 'checking' && 'bg-faint animate-pulse',
                )}
              />
              <span className="hidden sm:inline">API</span>
            </div>
            <button
              type="button"
              onClick={toggle}
              className="btn-secondary btn-sm"
              title={lang === 'zh-TW' ? 'Switch to English' : '切換為繁體中文'}
            >
              <Languages size={14} />
              {t('lang_switch')}
            </button>
            <NavLink to="/settings" className="btn-ghost btn-icon sm:hidden" aria-label={t('nav_settings')}>
              <Settings2 size={16} />
            </NavLink>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
