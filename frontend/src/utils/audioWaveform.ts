/**
 * Audio waveform decoding and DSP peak processing utilities
 * Uses standard Web Audio API (AudioContext.decodeAudioData) to generate real PCM waveforms.
 */

export interface DecodedAudioData {
  duration: number
  sampleRate: number
  peaks: Float32Array // Normalized 0.0 to 1.0 peak values
}

const audioDataCache = new Map<string, Promise<DecodedAudioData | null>>()

/**
 * Fetch and decode an audio or video file URL into normalized PCM peak arrays.
 * Cached by URL to ensure high performance without re-decoding.
 */
export async function getAudioPeaks(
  url: string,
  targetPointsPerSec = 50
): Promise<DecodedAudioData | null> {
  if (!url) return null

  if (audioDataCache.has(url)) {
    return audioDataCache.get(url)!
  }

  const promise = (async () => {
    try {
      const resp = await fetch(url)
      if (!resp.ok) return null
      const arrayBuf = await resp.arrayBuffer()

      const AudioContextClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      const audioCtx = new AudioContextClass()

      let audioBuf: AudioBuffer
      try {
        audioBuf = await audioCtx.decodeAudioData(arrayBuf)
      } finally {
        audioCtx.close().catch(() => {})
      }

      const duration = audioBuf.duration
      if (!duration || duration <= 0) return null

      // Use Channel 0 (left / mono)
      const rawData = audioBuf.getChannelData(0)
      const totalPoints = Math.max(100, Math.round(duration * targetPointsPerSec))
      const blockSize = Math.max(1, Math.floor(rawData.length / totalPoints))
      const peaks = new Float32Array(totalPoints)

      let globalMax = 0.001
      for (let i = 0; i < totalPoints; i++) {
        const start = i * blockSize
        let sum = 0
        let peak = 0
        const end = Math.min(start + blockSize, rawData.length)
        const count = end - start
        for (let j = start; j < end; j++) {
          const val = Math.abs(rawData[j])
          sum += val
          if (val > peak) peak = val
        }
        // Hybrid RMS + Peak for punchy visually pleasing DAW waveforms
        const avg = count > 0 ? sum / count : 0
        const combined = avg * 0.4 + peak * 0.6
        peaks[i] = combined
        if (combined > globalMax) globalMax = combined
      }

      // Normalize so loudest peak reaches ~0.95
      const normFactor = 0.95 / globalMax
      for (let i = 0; i < totalPoints; i++) {
        peaks[i] = Math.min(1.0, peaks[i] * normFactor)
      }

      return {
        duration,
        sampleRate: audioBuf.sampleRate,
        peaks,
      }
    } catch (err) {
      console.warn('Audio decoding failed for URL:', url, err)
      return null
    }
  })()

  audioDataCache.set(url, promise)
  return promise
}

export interface PeakProcessOptions {
  gain?: number // e.g. 1.0 = 100%, 1.5 = 150%
  denoiseLevel?: 'off' | 'low' | 'med' | 'high'
  antiClip?: boolean
}

/**
 * Extract peak bars for a specific time range [startTime, endTime] (e.g. for a subtitle cue).
 * Applies volume gain, noise gate / denoise threshold, and soft-clipping limiter.
 */
export function extractCuePeaks(
  decoded: DecodedAudioData | null,
  totalMediaDuration: number,
  startTime: number,
  endTime: number,
  numBars = 16,
  options: PeakProcessOptions = {}
): number[] {
  const { gain = 1.0, denoiseLevel = 'med', antiClip = true } = options
  const count = Math.max(4, numBars)

  // Noise floor thresholds for denoise levels
  const noiseThresholds: Record<string, number> = {
    off: 0.0,
    low: 0.04,
    med: 0.08,
    high: 0.14,
  }
  const noiseFloor = noiseThresholds[denoiseLevel] ?? 0.08

  if (!decoded || !decoded.peaks || decoded.peaks.length === 0) {
    // Natural human voice speech cadence fallback with syllabic bursts and micro-pauses
    return Array.from({ length: count }, (_, idx) => {
      const t = idx / (count - 1 || 1)
      const syllable = Math.sin(t * Math.PI * 4.5) * 0.35 + 0.35
      const transient = Math.abs(Math.sin(idx * 2.1 + Math.cos(idx * 0.8))) * 0.35
      const pause = Math.sin(t * Math.PI * 2) < -0.65 ? 0.05 : 1.0
      let val = (syllable + transient) * pause * gain
      if (antiClip && val > 0.95) val = 0.95 + (val - 0.95) * 0.1
      return Math.min(1.0, Math.max(0.03, val))
    })
  }

  const { duration: mediaDur, peaks } = decoded
  const totalDuration = totalMediaDuration > 0 ? totalMediaDuration : mediaDur
  const startRatio = Math.max(0, Math.min(1, startTime / totalDuration))
  const endRatio = Math.max(0, Math.min(1, endTime / totalDuration))

  const startIdx = Math.floor(startRatio * peaks.length)
  const endIdx = Math.max(startIdx + 1, Math.floor(endRatio * peaks.length))
  const sliceLen = endIdx - startIdx

  const result: number[] = []
  const step = sliceLen / count

  for (let i = 0; i < count; i++) {
    const s = Math.floor(startIdx + i * step)
    const e = Math.min(peaks.length, Math.floor(startIdx + (i + 1) * step))
    let maxVal = 0
    for (let k = s; k < e; k++) {
      if (peaks[k] > maxVal) maxVal = peaks[k]
    }

    // Apply Denoise (Noise Gate thresholding)
    if (maxVal < noiseFloor) {
      maxVal = maxVal * 0.15 // sharply attenuate background noise
    } else {
      // Expand speech dynamics above noise floor
      maxVal = (maxVal - noiseFloor) / (1 - noiseFloor)
    }

    // Apply Volume Gain
    let scaled = maxVal * gain

    // Apply Anti-Clipping Limiter (Soft saturation curve)
    if (antiClip) {
      if (scaled > 0.85) {
        // Soft-knee compression: smoothly compresses overdriven peaks towards 1.0
        scaled = 0.85 + 0.15 * Math.tanh((scaled - 0.85) / 0.3)
      }
    }

    result.push(Math.min(1.0, Math.max(0.04, scaled)))
  }

  return result
}

/**
 * Extract full-track timeline peak bars (for continuous BGM or master audio).
 * Handles looping if timeline duration exceeds BGM media duration.
 */
export function extractTimelinePeaks(
  decoded: DecodedAudioData | null,
  timelineDuration: number,
  numBars: number,
  options: PeakProcessOptions = {}
): number[] {
  const { gain = 1.0, antiClip = true } = options
  const count = Math.max(20, numBars)

  if (!decoded || !decoded.peaks || decoded.peaks.length === 0) {
    // Musical beat envelope fallback while loading
    return Array.from({ length: count }, (_, i) => {
      const beat = (i % 4 === 0 ? 0.8 : 0.4) + Math.sin(i * 0.2) * 0.25
      let val = beat * gain
      if (antiClip && val > 0.92) val = 0.92 + (val - 0.92) * 0.15
      return Math.min(1.0, Math.max(0.1, val))
    })
  }

  const { duration: bgmDur, peaks } = decoded
  const result: number[] = []

  for (let i = 0; i < count; i++) {
    // Calculate timeline second for this bar
    const currentSec = (i / count) * timelineDuration
    // Loop modulo BGM duration
    const loopedSec = bgmDur > 0 ? currentSec % bgmDur : 0
    const ratio = loopedSec / bgmDur
    const peakIdx = Math.min(peaks.length - 1, Math.floor(ratio * peaks.length))
    const rawVal = peaks[peakIdx] || 0.3

    let scaled = rawVal * gain
    if (antiClip && scaled > 0.88) {
      scaled = 0.88 + 0.12 * Math.tanh((scaled - 0.88) / 0.25)
    }

    result.push(Math.min(1.0, Math.max(0.06, scaled)))
  }

  return result
}

/**
 * Convert linear gain (1.0 = 100%) to human-readable decibels (dB).
 * e.g. 1.0 -> "0.0 dB", 0.79 -> "-2.0 dB", 1.41 -> "+3.0 dB"
 */
export function gainToDb(gain: number): string {
  if (gain <= 0.001) return '-∞ dB'
  const db = 20 * Math.log10(gain)
  if (Math.abs(db) < 0.05) return '0.0 dB'
  const sign = db > 0 ? '+' : ''
  return `${sign}${db.toFixed(1)} dB`
}

/**
 * Convert decibels (dB) to linear gain multiplier.
 * e.g. 0.0 dB -> 1.0, -2.0 dB -> 0.794, +3.0 dB -> 1.413
 */
export function dbToGain(db: number): number {
  return Math.pow(10, db / 20)
}

/**
 * Generate a continuous solid-filled SVG path representing the authentic Final Cut Pro audio waveform silhouette.
 * Returns { pathD, strokeD, hasClipping }
 */
export function buildFcpWaveformPath(
  peaks: number[],
  width: number,
  height: number
): { pathD: string; strokeD: string; hasClipping: boolean } {
  if (!peaks || peaks.length < 2 || width <= 0 || height <= 0) {
    return { pathD: '', strokeD: '', hasClipping: false }
  }

  let hasClipping = false
  const fillPoints: string[] = []
  const strokePoints: string[] = []

  // Start at bottom-left corner for filled polygon
  fillPoints.push(`M 0,${height}`)

  const len = peaks.length
  for (let i = 0; i < len; i++) {
    const val = Math.max(0, Math.min(1.0, peaks[i]))
    if (val >= 0.98) {
      hasClipping = true
    }
    const x = ((i / (len - 1)) * width).toFixed(1)
    // Audio waveform baseline is at the bottom (y = height), rising up towards y = 0
    const y = Math.max(1, height - val * height).toFixed(1)

    if (i === 0) {
      strokePoints.push(`M ${x},${y}`)
    } else {
      strokePoints.push(`L ${x},${y}`)
    }
    fillPoints.push(`L ${x},${y}`)
  }

  // Close path at bottom-right corner and back to origin for filled silhouette
  fillPoints.push(`L ${width.toFixed(1)},${height} Z`)

  return {
    pathD: fillPoints.join(' '),
    strokeD: strokePoints.join(' '),
    hasClipping,
  }
}

