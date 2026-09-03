import { useCallback, useSyncExternalStore } from 'react'
import zhTW from './locales/zh-TW'
import en from './locales/en'

export type Lang = 'zh-TW' | 'en'
export type LocaleKey = keyof typeof zhTW

const STORAGE_KEY = 'easyaivideo.lang'
const dictionaries: Record<Lang, Record<LocaleKey, string>> = { 'zh-TW': zhTW, en }

function readStored(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'en' || v === 'zh-TW') return v
  } catch {
    /* storage unavailable */
  }
  return 'zh-TW'
}

let current: Lang = readStored()
const listeners = new Set<() => void>()

export function getLang(): Lang {
  return current
}

export function setLang(lang: Lang) {
  if (lang === current) return
  current = lang
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lang
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Translate a key in the current language, substituting `{name}` placeholders. */
export function t(key: LocaleKey, vars?: Record<string, string | number>): string {
  let s = dictionaries[current][key] ?? dictionaries['zh-TW'][key] ?? key
  if (vars) {
    for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v))
  }
  return s
}

/** Hook: re-renders the component when the language changes. */
export function useLang() {
  const lang = useSyncExternalStore(subscribe, getLang, getLang)
  const toggle = useCallback(() => setLang(lang === 'zh-TW' ? 'en' : 'zh-TW'), [lang])
  return { lang, setLang, toggle, t }
}
