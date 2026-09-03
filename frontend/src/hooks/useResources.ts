import { useCallback, useEffect, useState } from 'react'
import { errorMessage, getBgm, getPresets, getStyles, getVoices } from '../api'
import type { BgmOption, Presets, StyleOption, VoiceOption } from '../types'

export interface Resources {
  presets: Presets
  styles: StyleOption[]
  voices: VoiceOption[]
  bgm: BgmOption[]
}

/**
 * Loads dropdown data. Presets and styles are required; voices and BGM degrade to
 * empty lists if their endpoint fails (e.g. TTS provider not configured yet).
 */
export function useResources() {
  const [data, setData] = useState<Resources | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [presets, styles] = await Promise.all([getPresets(), getStyles()])
      const [voicesRes, bgmRes] = await Promise.allSettled([getVoices(), getBgm()])
      setData({
        presets,
        styles,
        voices: voicesRes.status === 'fulfilled' ? voicesRes.value : [],
        bgm: bgmRes.status === 'fulfilled' ? bgmRes.value : [],
      })
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return { resources: data, loading, error, reload: load }
}
