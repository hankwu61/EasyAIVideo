import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Check,
  Download,
  Flame,
  Keyboard,
  Layout,
  Link2,
  ListVideo,
  Move,
  Palette,
  Pause,
  Play,
  Plus,
  RotateCcw,
  RotateCw,
  Scissors,
  Search,
  Shield,
  Sparkles,
  Trash2,
  Type,
  Upload,
  Volume2,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import {
  burnProjectSubtitles,
  getProject,
  getProjectSubtitles,
  patchProject,
  synthesizeCue,
  trimProjectVideo,
  updateProjectSubtitles,
} from '../api'
import { useLang } from '../i18n'
import type { Project, Scene, SubtitleCue, SubtitleStyleConfig } from '../types'
import { formatDuration } from '../utils'
import { useToast } from './Toast'
import FcpTimeline from './fcp/FcpTimeline'
import FcpInspector, { VideoAdjustments } from './fcp/FcpInspector'
import FcpEffectsBrowser, { FCP_FILTERS } from './fcp/FcpEffectsBrowser'
import { getAudioPeaks, DecodedAudioData } from '../utils/audioWaveform'

export const DEFAULT_ADJUSTMENTS: VideoAdjustments = {
  scale: 100,
  rotation: 0,
  brightness: 100,
  contrast: 100,
  saturation: 100,
  temperature: 0,
  volume: 100,
  muted: false,
}

function formatFcpTimecode(seconds: number, fps = 30): string {
  if (isNaN(seconds) || seconds < 0) return '00:00:00:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const f = Math.floor((seconds % 1) * fps)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}:${String(f).padStart(2, '0')}`
}

interface VideoStudioModalProps {
  project: Project
  onClose: () => void
  onProjectUpdated?: () => void
}

export default function VideoStudioModal({ project, onClose, onProjectUpdated }: VideoStudioModalProps) {
  const { t } = useLang()
  const toast = useToast()

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const timelineRef = useRef<HTMLDivElement | null>(null)
  const activeItemRef = useRef<HTMLDivElement | null>(null)

  // Subtitle cues state
  const [cues, setCues] = useState<SubtitleCue[]>([])
  const [history, setHistory] = useState<SubtitleCue[][]>([])
  const [historyIdx, setHistoryIdx] = useState<number>(-1)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [burning, setBurning] = useState(false)
  const [trimming, setTrimming] = useState(false)
  const [synthesizingId, setSynthesizingId] = useState<number | null>(null)

  // Player state
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(project.final_video_duration || 0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState<number>(1.0)
  const [zoom, setZoom] = useState<number>(0.42) // 42% default like screenshot
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCueId, setSelectedCueId] = useState<number | null>(null)

  // FCP & Studio Mode toggles
  const [editorMode, setEditorMode] = useState<'fcp' | 'transcript'>('fcp')
  const [activeFilter, setActiveFilter] = useState<string>('none')
  const [adjustments, setAdjustments] = useState<VideoAdjustments>({
    scale: 100,
    rotation: 0,
    brightness: 100,
    contrast: 100,
    saturation: 100,
    temperature: 0,
    volume: 100,
    muted: false,
  })
  const [scenes, setScenes] = useState<Scene[]>(project.scenes || [])

  useEffect(() => {
    if ((!project.scenes || project.scenes.length === 0) && project.id) {
      getProject(project.id).then((p) => {
        if (p.scenes && p.scenes.length > 0) {
          setScenes(p.scenes)
        }
      }).catch(() => {})
    }
  }, [project.id, project.scenes])

  // UI toggles
  const [showSafeFrame, setShowSafeFrame] = useState(false)
  const [showStyleModal, setShowStyleModal] = useState(false)
  const [showShortcutsModal, setShowShortcutsModal] = useState(false)
  const [showImportModal, setShowImportModal] = useState(false)
  const [showTrimModal, setShowTrimModal] = useState(false)
  const [importText, setImportText] = useState('')
  const [trimStart, setTrimStart] = useState('0')
  const [trimEnd, setTrimEnd] = useState('10')

  // Subtitle Styling & Positioning
  const [styleConfig, setStyleConfig] = useState<SubtitleStyleConfig>({
    preset: 'pill',
    fontSize: 22,
    textColor: '#ffffff',
    bgColor: '#2563eb', // deep blue pill
    bgOpacity: 90,
    borderRadius: 8,
    fontFamily: 'Microsoft JhengHei',
    fontWeight: 'bold',
    strokeWidth: 0,
    strokeColor: '#000000',
    shadow: true,
    x: 50, // 50% horizontal center
    y: 86, // 86% near bottom
  })

  // Dragging state for subtitle position
  const [isDraggingSubtitle, setIsDraggingSubtitle] = useState(false)
  const videoContainerRef = useRef<HTMLDivElement | null>(null)
  const [customFontInput, setCustomFontInput] = useState('')

  // Audio peaks for waveform
  // Audio peaks for transcript waveform
  const [audioPeaks, setAudioPeaks] = useState<number[]>([])

  // Real Decoded Audio Waveform Data & DSP State
  const [voiceAudioData, setVoiceAudioData] = useState<DecodedAudioData | null>(null)
  const [bgmAudioData, setBgmAudioData] = useState<DecodedAudioData | null>(null)
  const [denoiseLevel, setDenoiseLevel] = useState<'off' | 'low' | 'med' | 'high'>('med')
  const [antiClip, setAntiClip] = useState<boolean>(true)

  // Audio Channels Mixing & Controls (Voice A1 & BGM A2)
  const [voiceVolume, setVoiceVolume] = useState<number>(100)
  const [voiceMuted, setVoiceMuted] = useState<boolean>(false)
  const [voiceSolo, setVoiceSolo] = useState<boolean>(false)

  const [activeBgm, setActiveBgm] = useState<string | null>(project.bgm || null)
  const [bgmVolume, setBgmVolume] = useState<number>(
    project.bgm_volume !== undefined ? Math.round(project.bgm_volume * 100) : 40
  )
  const [bgmMuted, setBgmMuted] = useState<boolean>(false)
  const [bgmSolo, setBgmSolo] = useState<boolean>(false)
  const [audioDucking, setAudioDucking] = useState<boolean>(true)
  const [effectsBrowserTab, setEffectsBrowserTab] = useState<'clips' | 'filters' | 'audio'>('clips')

  const bgmAudioRef = useRef<HTMLAudioElement | null>(null)

  // Load subtitles on open
  const loadSubtitles = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getProjectSubtitles(project.id)
      setCues(data)
      setHistory([data])
      setHistoryIdx(0)
    } catch {
      toast.error('無法載入字幕資料')
    } finally {
      setLoading(false)
    }
  }, [project.id, toast])

  useEffect(() => {
    loadSubtitles()
  }, [loadSubtitles])

  // Fetch authentic real voice and BGM audio waveform peaks from backend endpoint
  useEffect(() => {
    let cancelled = false

    const fetchWaveforms = async () => {
      try {
        const bgmParam = activeBgm ? `?bgm=${encodeURIComponent(activeBgm)}` : ''
        const res = await fetch(`/api/projects/${project.id}/audio-waveform${bgmParam}`)
        if (!res.ok) throw new Error('Waveform API error')
        const data = await res.json()
        if (cancelled || !data.ok) return

        if (data.voice && data.voice.peaks && data.voice.peaks.length > 0) {
          const vData: DecodedAudioData = {
            duration: data.voice.duration,
            sampleRate: data.voice.sampleRate || 30,
            peaks: new Float32Array(data.voice.peaks),
          }
          setVoiceAudioData(vData)
          setAudioPeaks(Array.from(vData.peaks.slice(0, 300)))
        }

        if (data.bgm && data.bgm.peaks && data.bgm.peaks.length > 0) {
          const bData: DecodedAudioData = {
            duration: data.bgm.duration,
            sampleRate: data.bgm.sampleRate || 30,
            peaks: new Float32Array(data.bgm.peaks),
          }
          setBgmAudioData(bData)
        } else if (!activeBgm) {
          setBgmAudioData(null)
        }
      } catch (err) {
        console.warn('Backend audio waveform fetch failed, falling back to Web Audio:', err)
        const videoUrl = project.raw_video_url || project.final_video_url
        if (videoUrl) {
          getAudioPeaks(videoUrl, 40).then((data) => {
            if (!cancelled && data) {
              setVoiceAudioData(data)
              setAudioPeaks(Array.from(data.peaks.slice(0, 300)))
            }
          })
        }
      }
    }

    fetchWaveforms()

    return () => {
      cancelled = true
    }
  }, [project.id, project.raw_video_url, project.final_video_url, activeBgm])

  // Update cues with undo/redo stack
  const updateCuesWithHistory = useCallback(
    (newCues: SubtitleCue[]) => {
      setCues(newCues)
      setHistory((prev) => {
        const next = prev.slice(0, historyIdx + 1)
        next.push(newCues)
        return next
      })
      setHistoryIdx((prev) => prev + 1)
    },
    [historyIdx],
  )

  const handleUndo = () => {
    if (historyIdx > 0) {
      setHistoryIdx((prev) => prev - 1)
      setCues(history[historyIdx - 1])
    }
  }

  const handleRedo = () => {
    if (historyIdx < history.length - 1) {
      setHistoryIdx((prev) => prev + 1)
      setCues(history[historyIdx + 1])
    }
  }

  // FCP Filter and Transform styles
  const activeFilterObj = useMemo(() => {
    return FCP_FILTERS.find((f) => f.id === activeFilter)
  }, [activeFilter])

  const videoFilterStyle = useMemo(() => {
    const parts: string[] = []
    if (activeFilterObj && activeFilterObj.cssFilter !== 'none') {
      parts.push(activeFilterObj.cssFilter)
    }
    if (adjustments.brightness !== 100) parts.push(`brightness(${adjustments.brightness}%)`)
    if (adjustments.contrast !== 100) parts.push(`contrast(${adjustments.contrast}%)`)
    if (adjustments.saturation !== 100) parts.push(`saturate(${adjustments.saturation}%)`)
    if (adjustments.temperature !== 0) {
      if (adjustments.temperature > 0) {
        parts.push(`sepia(${adjustments.temperature * 0.008})`)
      } else {
        parts.push(`hue-rotate(${adjustments.temperature * 0.4}deg)`)
      }
    }
    return parts.join(' ') || 'none'
  }, [activeFilterObj, adjustments])

  const videoTransformStyle = useMemo(() => {
    return `scale(${adjustments.scale / 100}) rotate(${adjustments.rotation}deg)`
  }, [adjustments.scale, adjustments.rotation])

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.muted = adjustments.muted
      videoRef.current.volume = Math.min(1.0, adjustments.volume / 100)
    }
  }, [adjustments.muted, adjustments.volume])

  const handleSplitCue = useCallback(
    (cueId: number, splitTime?: number) => {
      const targetIdx = cues.findIndex((c) => c.id === cueId)
      if (targetIdx === -1) return
      const target = cues[targetIdx]
      const actualCut = splitTime ?? currentTime
      if (actualCut <= target.start + 0.1 || actualCut >= target.end - 0.1) {
        toast.error('分割點須在字幕區間內部')
        return
      }

      const ratio = (actualCut - target.start) / (target.end - target.start)
      const splitCharIdx = Math.max(1, Math.round(target.text.length * ratio))
      const textPart1 = target.text.slice(0, splitCharIdx) || target.text
      const textPart2 = target.text.slice(splitCharIdx) || '...'

      const newCue1: SubtitleCue = {
        ...target,
        end: actualCut,
        text: textPart1,
      }
      const maxId = Math.max(...cues.map((c) => c.id), 0)
      const newCue2: SubtitleCue = {
        id: maxId + 1,
        start: actualCut,
        end: target.end,
        text: textPart2,
      }

      const nextCues = [
        ...cues.slice(0, targetIdx),
        newCue1,
        newCue2,
        ...cues.slice(targetIdx + 1),
      ]
      updateCuesWithHistory(nextCues)
      toast.success(`✂ 已在 ${actualCut.toFixed(2)}s 刀片分割字幕片段`)
    },
    [cues, currentTime, updateCuesWithHistory, toast]
  )

  const handleDeleteCue = useCallback(
    (cueId: number) => {
      const nextCues = cues.filter((c) => c.id !== cueId)
      updateCuesWithHistory(nextCues)
      if (selectedCueId === cueId) setSelectedCueId(null)
      toast.success('已刪除選取片段')
    },
    [cues, selectedCueId, updateCuesWithHistory, toast]
  )

  const handleUpdateCueTime = useCallback(
    (cueId: number, start: number, end: number) => {
      const nextCues = cues.map((c) => (c.id === cueId ? { ...c, start, end } : c))
      updateCuesWithHistory(nextCues)
    },
    [cues, updateCuesWithHistory]
  )

  // Save cues and audio settings to backend
  const handleSaveSubtitles = async () => {
    setSaving(true)
    try {
      await updateProjectSubtitles(project.id, cues)
      await patchProject(project.id, {
        bgm: activeBgm,
        bgm_volume: bgmVolume / 100,
      })
      toast.success('字幕與配樂設定已成功儲存')
      if (onProjectUpdated) onProjectUpdated()
    } catch {
      toast.error('儲存字幕與配樂失敗')
    } finally {
      setSaving(false)
    }
  }

  // Burn-in subtitles
  const handleBurnSubtitles = async () => {
    if (burning) return
    setBurning(true)
    const totalMins = Math.max(1, Math.round(duration / 60))
    toast.success(`開始燒錄字幕！全片約 ${totalMins} 分鐘，FFmpeg 正全力逐幀渲染編碼，完成後將自動下載新影片，請稍候…`)
    try {
      // First save latest subtitles and audio settings
      await updateProjectSubtitles(project.id, cues)
      await patchProject(project.id, {
        bgm: activeBgm,
        bgm_volume: bgmVolume / 100,
      })

      // Convert hex color (#RRGGBB) to ASS color (&HAABBGGRR)
      const hexToAss = (hex: string, alphaPercent = 0) => {
        const clean = hex.replace('#', '')
        if (clean.length !== 6) return '&H00FFFFFF'
        const r = clean.slice(0, 2)
        const g = clean.slice(2, 4)
        const b = clean.slice(4, 6)
        const aVal = Math.round(((100 - alphaPercent) / 100) * 255)
        const aHex = aVal.toString(16).padStart(2, '0').toUpperCase()
        return `&H${aHex}${b}${g}${r}`.toUpperCase()
      }

      // Calculate vertical margin from top or bottom based on y coordinate (0~100%)
      const isTopHalf = styleConfig.y < 45
      const isCenter = styleConfig.y >= 45 && styleConfig.y <= 55
      const alignment = isTopHalf ? 5 : isCenter ? 8 : 2 // 5 = top-center, 8 = mid-center, 2 = bottom-center

      // Video height estimate
      const estHeight = project.aspect_ratio === '9:16' ? 1920 : project.aspect_ratio === '1:1' ? 1080 : 1080
      let marginV = 40
      if (alignment === 2) {
        marginV = Math.max(10, Math.round(((100 - styleConfig.y) / 100) * estHeight))
      } else if (alignment === 5) {
        marginV = Math.max(10, Math.round((styleConfig.y / 100) * estHeight))
      }

      const res = await burnProjectSubtitles(project.id, {
        font_name: styleConfig.fontFamily,
        font_size: styleConfig.fontSize,
        primary_color: hexToAss(styleConfig.textColor, 100),
        back_color: hexToAss(styleConfig.bgColor, styleConfig.bgOpacity),
        border_style: styleConfig.preset === 'pill' || styleConfig.preset === 'box' ? 3 : 1,
        outline: styleConfig.strokeWidth > 0 ? styleConfig.strokeWidth : styleConfig.preset === 'outline' ? 3 : 0,
        outline_color: hexToAss(styleConfig.strokeColor, 100),
        alignment,
        margin_v: marginV,
      })
      toast.success('🎉 影片與字幕已成功燒錄完成！已為您啟動下載全新影片')
      if (videoRef.current) {
        videoRef.current.src = res.burned_video_url
        videoRef.current.load()
      }
      if (onProjectUpdated) onProjectUpdated()

      // Prompt immediate download of the newly burned video
      const a = document.createElement('a')
      a.href = res.burned_video_url
      a.download = `${project.title || 'video'}_burned.mp4`
      a.click()
    } catch {
      toast.error('燒錄字幕失敗，請稍後重試')
    } finally {
      setBurning(false)
    }
  }

  // Export / Download SRT directly from current cues
  const handleDownloadSrt = () => {
    if (cues.length === 0) {
      toast.error('目前沒有字幕資料可匯出')
      return
    }
    const formatTime = (secs: number) => {
      const h = Math.floor(secs / 3600)
      const m = Math.floor((secs % 3600) / 60)
      const s = Math.floor(secs % 60)
      const ms = Math.floor((secs - Math.floor(secs)) * 1000)
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`
    }

    const sorted = [...cues].sort((a, b) => a.start - b.start)
    const blocks = sorted.map((cue, i) => {
      return `${i + 1}\n${formatTime(cue.start)} --> ${formatTime(cue.end)}\n${cue.text.trim()}`
    })

    const blob = new Blob([blocks.join('\n\n') + '\n'], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${project.title || 'subtitles'}.srt`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('已匯出最新字幕檔 (.srt)')
  }

  // Export / Download current video file
  const handleDownloadVideo = () => {
    const videoSrc = videoRef.current?.src || project.final_video_url
    if (!videoSrc) {
      toast.error('尚未有已生成的影片檔')
      return
    }
    const a = document.createElement('a')
    a.href = videoSrc
    a.download = `${project.title || 'video'}.mp4`
    a.click()
    toast.success('開始下載影片檔 (.mp4)')
  }

  // Trim video
  const handleTrimVideo = async () => {
    const s = parseFloat(trimStart)
    const e = parseFloat(trimEnd)
    if (isNaN(s) || isNaN(e) || s >= e || s < 0) {
      toast.error('請輸入正確的開始與結束時間')
      return
    }
    setTrimming(true)
    try {
      const res = await trimProjectVideo(project.id, s, e)
      toast.success(`影片已成功剪輯 (時長: ${res.duration} 秒)`)
      setShowTrimModal(false)
      if (videoRef.current) {
        videoRef.current.src = res.trimmed_video_url
        videoRef.current.load()
      }
      if (onProjectUpdated) onProjectUpdated()
    } catch {
      toast.error('剪輯影片失敗')
    } finally {
      setTrimming(false)
    }
  }

  // Synthesize cue audio preview
  const handleSynthesizeCue = async (cue: SubtitleCue) => {
    setSynthesizingId(cue.id)
    try {
      const res = await synthesizeCue(project.id, cue.text, project.voice, project.tts_speed || 1.0)
      const audio = new Audio(res.audio_url)
      audio.play()
      toast.success(`單句配音生成完成 (${res.duration}s)`)
    } catch {
      toast.error('單句語音合成失敗')
    } finally {
      setSynthesizingId(null)
    }
  }

  // Player controls
  const togglePlay = () => {
    if (!videoRef.current) return
    if (videoRef.current.paused) {
      videoRef.current.play()
      setIsPlaying(true)
      if (bgmAudioRef.current && activeBgm) {
        bgmAudioRef.current.play().catch(() => {})
      }
    } else {
      videoRef.current.pause()
      setIsPlaying(false)
      if (bgmAudioRef.current) {
        bgmAudioRef.current.pause()
      }
    }
  }

  const handleSeek = (time: number) => {
    const clamped = Math.max(0, Math.min(time, duration || 99999))
    if (videoRef.current) {
      videoRef.current.currentTime = clamped
    }
    if (bgmAudioRef.current) {
      if (bgmAudioRef.current.duration && !isNaN(bgmAudioRef.current.duration)) {
        bgmAudioRef.current.currentTime = clamped % bgmAudioRef.current.duration
      } else {
        bgmAudioRef.current.currentTime = clamped
      }
    }
    setCurrentTime(clamped)
  }

  // Synchronize BGM audio source and playback with video
  useEffect(() => {
    const bgmEl = bgmAudioRef.current
    if (!bgmEl) return

    if (!activeBgm) {
      bgmEl.pause()
      bgmEl.removeAttribute('src')
      return
    }

    const bgmSrc = `/api/files/_bgm/${encodeURIComponent(activeBgm)}`
    if (!bgmEl.src.endsWith(bgmSrc)) {
      bgmEl.src = bgmSrc
      bgmEl.load()
    }

    if (isPlaying) {
      if (bgmEl.paused) {
        bgmEl.play().catch(() => {})
      }
    } else {
      if (!bgmEl.paused) {
        bgmEl.pause()
      }
    }
  }, [isPlaying, activeBgm])

  // Synthesize cue audio preview helper
  const handleSynthesizeCueById = async (cueId: number) => {
    const cue = cues.find((c) => c.id === cueId)
    if (!cue) return
    await handleSynthesizeCue(cue)
  }

  const cyclePlaybackRate = () => {
    const rates = [0.75, 1.0, 1.25, 1.5, 2.0]
    const curIdx = rates.indexOf(playbackRate)
    const nextRate = rates[(curIdx + 1) % rates.length]
    setPlaybackRate(nextRate)
    if (videoRef.current) {
      videoRef.current.playbackRate = nextRate
    }
  }

  // Find active cue at currentTime
  const activeCue = useMemo(() => {
    return cues.find((c) => currentTime >= c.start && currentTime <= c.end) || null
  }, [cues, currentTime])

  // Dual-channel volume, real-time audio ducking & anti-clip limiter
  useEffect(() => {
    if (videoRef.current) {
      let effectiveVoiceVol = (voiceVolume / 100) * (adjustments.volume / 100)
      if (antiClip && effectiveVoiceVol > 1.0) {
        effectiveVoiceVol = 0.95 + 0.05 * Math.tanh(effectiveVoiceVol - 1.0)
      }
      if (voiceMuted || bgmSolo) effectiveVoiceVol = 0

      videoRef.current.volume = Math.min(1.0, Math.max(0, effectiveVoiceVol))
      videoRef.current.muted = voiceMuted || bgmSolo || adjustments.muted
    }

    if (bgmAudioRef.current) {
      let effectiveBgmVol = bgmMuted || voiceSolo ? 0 : bgmVolume / 100
      // Ducking: drop BGM volume to 25% when voice dialogue cue is actively speaking
      if (audioDucking && activeCue && effectiveBgmVol > 0) {
        effectiveBgmVol *= 0.25
      }
      if (antiClip && effectiveBgmVol > 1.0) {
        effectiveBgmVol = 0.95 + 0.05 * Math.tanh(effectiveBgmVol - 1.0)
      }
      bgmAudioRef.current.volume = Math.min(1, Math.max(0, effectiveBgmVol))
      bgmAudioRef.current.muted = bgmMuted || voiceSolo
    }
  }, [
    voiceVolume,
    voiceMuted,
    voiceSolo,
    bgmVolume,
    bgmMuted,
    bgmSolo,
    audioDucking,
    activeCue,
    antiClip,
    adjustments.volume,
    adjustments.muted,
  ])

  // Active cue or selected cue for stats and screen display
  const focusedCue = useMemo(() => {
    if (selectedCueId) {
      return cues.find((c) => c.id === selectedCueId) || activeCue
    }
    return activeCue
  }, [cues, selectedCueId, activeCue])

  const selectedCue = useMemo(() => {
    if (!selectedCueId) return null
    return cues.find((c) => c.id === selectedCueId) || null
  }, [cues, selectedCueId])

  // Display cue on screen (prioritizes user selected cue, falls back to active playback cue)
  const displayCue = focusedCue || activeCue

  // Auto-scroll transcript list to active item
  useEffect(() => {
    if (activeCue && activeItemRef.current) {
      activeItemRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [activeCue?.id])

  // Subtitle cue operations: Edit text, Split, Merge, Delete, Insert
  const handleTextChange = (cueId: number, newText: string) => {
    const updated = cues.map((c) => (c.id === cueId ? { ...c, text: newText } : c))
    updateCuesWithHistory(updated)
  }

  const handleMergeNext = (cueId: number) => {
    const idx = cues.findIndex((c) => c.id === cueId)
    if (idx === -1 || idx >= cues.length - 1) return
    const c1 = cues[idx]
    const c2 = cues[idx + 1]

    const merged: SubtitleCue = {
      id: c1.id,
      start: c1.start,
      end: c2.end,
      text: `${c1.text.trim()} ${c2.text.trim()}`,
    }

    const nextCues = [...cues.slice(0, idx), merged, ...cues.slice(idx + 2)]
    nextCues.forEach((c, i) => {
      c.id = i + 1
    })
    updateCuesWithHistory(nextCues)
    toast.success('已合併為單一句子')
  }

  const handleInsertCue = () => {
    const insertTime = currentTime
    const newCue: SubtitleCue = {
      id: cues.length + 1,
      start: roundTo3(insertTime),
      end: roundTo3(insertTime + 2.0),
      text: '新增字幕內容',
    }
    const nextCues = [...cues, newCue].sort((a, b) => a.start - b.start)
    nextCues.forEach((c, i) => {
      c.id = i + 1
    })
    updateCuesWithHistory(nextCues)
    setSelectedCueId(newCue.id)
  }

  const handleImportSubtitles = () => {
    if (!importText.trim()) return
    const blocks = importText.replace(/\r\n/g, '\n').trim().split(/\n\s*\n/)
    const parsed: SubtitleCue[] = []
    blocks.forEach((block, idx) => {
      const lines = block.split('\n').map((l) => l.trim()).filter(Boolean)
      const timeLine = lines.find((l) => l.includes('-->'))
      if (timeLine) {
        const parts = timeLine.split('-->')
        const parseTime = (tStr: string) => {
          const m = tStr.trim().replace('.', ',').match(/(\d+):(\d+):(\d+)(?:,(\d+))?/)
          if (!m) return 0
          return (
            parseInt(m[1]) * 3600 +
            parseInt(m[2]) * 60 +
            parseInt(m[3]) +
            parseInt((m[4] || '0').padEnd(3, '0').slice(0, 3)) / 1000
          )
        }
        const start = parseTime(parts[0])
        const end = parseTime(parts[1])
        const timeIdx = lines.indexOf(timeLine)
        const text = lines.slice(timeIdx + 1).join(' ')
        if (text) {
          parsed.push({ id: idx + 1, start, end, text })
        }
      }
    })
    if (parsed.length > 0) {
      updateCuesWithHistory(parsed)
      toast.success(`成功匯入 ${parsed.length} 句字幕`)
      setShowImportModal(false)
      setImportText('')
    } else {
      toast.error('無法辨識 SRT 格式，請確認格式包含 00:00:01,000 --> 00:00:03,000')
    }
  }


  // Waveform Canvas Rendering
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height

    ctx.clearRect(0, 0, width, height)

    // Background
    ctx.fillStyle = '#f8fafc'
    ctx.fillRect(0, 0, width, height)

    // Center baseline
    ctx.strokeStyle = '#e2e8f0'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(0, height / 2)
    ctx.lineTo(width, height / 2)
    ctx.stroke()

    // Draw green waveform bars
    const peaks = audioPeaks.length > 0 ? audioPeaks : Array.from({ length: 200 }, () => 0.4)
    const barWidth = width / peaks.length
    ctx.fillStyle = '#22c55e' // vibrant green matching screenshot

    peaks.forEach((peak, i) => {
      const x = i * barWidth
      const barH = Math.max(3, peak * (height - 16))
      const y = (height - barH) / 2
      ctx.beginPath()
      ctx.roundRect ? ctx.roundRect(x, y, Math.max(1.5, barWidth - 1), barH, 2) : ctx.fillRect(x, y, Math.max(1.5, barWidth - 1), barH)
      ctx.fill()
    })
  }, [audioPeaks])

  // Keyboard shortcuts (Supports FCP Pro standards)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') {
        return
      }
      if (e.code === 'Space') {
        e.preventDefault()
        togglePlay()
      } else if (e.code === 'KeyC') {
        // FCP C key: split at playhead
        e.preventDefault()
        const activeCue = cues.find((c) => currentTime >= c.start && currentTime < c.end)
        if (activeCue) {
          handleSplitCue(activeCue.id, currentTime)
        }
      } else if (e.code === 'Delete' || e.code === 'Backspace') {
        if (selectedCueId) {
          e.preventDefault()
          handleDeleteCue(selectedCueId)
        }
      } else if (e.code === 'KeyJ') {
        // FCP J: Rewind / Step back
        e.preventDefault()
        handleSeek(Math.max(0, currentTime - 1.0))
      } else if (e.code === 'KeyK') {
        // FCP K: Pause
        e.preventDefault()
        if (videoRef.current && !videoRef.current.paused) {
          videoRef.current.pause()
          setIsPlaying(false)
        }
      } else if (e.code === 'KeyL') {
        // FCP L: Play forward
        e.preventDefault()
        if (videoRef.current && videoRef.current.paused) {
          videoRef.current.play()
          setIsPlaying(true)
        }
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault()
        handleSeek(Math.max(0, currentTime - (e.shiftKey ? 1.0 : 0.1)))
      } else if (e.code === 'ArrowRight') {
        e.preventDefault()
        handleSeek(Math.min(duration, currentTime + (e.shiftKey ? 1.0 : 0.1)))
      } else if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        if (e.shiftKey) handleRedo()
        else handleUndo()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentTime, isPlaying, historyIdx, history, cues, selectedCueId, handleSplitCue, handleDeleteCue, duration])

  // Filtered cues
  const filteredCues = useMemo(() => {
    if (!searchQuery.trim()) return cues
    return cues.filter((c) => c.text.toLowerCase().includes(searchQuery.toLowerCase()))
  }, [cues, searchQuery])

  // Dragging handler for subtitle position on video preview
  useEffect(() => {
    if (!isDraggingSubtitle) return

    const handleMouseMove = (e: MouseEvent) => {
      if (!videoContainerRef.current) return
      const rect = videoContainerRef.current.getBoundingClientRect()
      const clientX = e.clientX
      const clientY = e.clientY

      let newX = ((clientX - rect.left) / rect.width) * 100
      let newY = ((clientY - rect.top) / rect.height) * 100

      // Clamp within 5% to 95%
      newX = Math.max(5, Math.min(95, Math.round(newX * 10) / 10))
      newY = Math.max(5, Math.min(95, Math.round(newY * 10) / 10))

      setStyleConfig((c) => ({ ...c, x: newX, y: newY }))
    }

    const handleMouseUp = () => {
      setIsDraggingSubtitle(false)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDraggingSubtitle])

  // Reading rate metrics for focused cue
  const cueStats = useMemo(() => {
    if (!focusedCue) return null
    const dur = Math.max(0.1, focusedCue.end - focusedCue.start)
    const chars = focusedCue.text.replace(/\s+/g, '').length
    const cps = chars / dur
    const speedRating = cps > 6.0 ? '偏快' : cps < 3.0 ? '偏慢' : '適中'
    return {
      dur: dur.toFixed(2),
      chars,
      cps: cps.toFixed(1),
      speedRating,
      startFormatted: formatTimestamp(focusedCue.start),
      endFormatted: formatTimestamp(focusedCue.end),
    }
  }, [focusedCue])

  const handleSetPlaybackRate = (rate: number) => {
    setPlaybackRate(rate)
    if (videoRef.current) {
      videoRef.current.playbackRate = rate
    }
  }

  const renderVideoViewer = (maxHeightStyle = 'calc(100vh - 430px)') => (
    <div
      ref={videoContainerRef}
      className={`relative flex max-h-full items-center justify-center overflow-hidden rounded-lg shadow-2xl select-none ${
        isDraggingSubtitle ? 'cursor-grabbing ring-2 ring-primary' : ''
      }`}
      style={{
        aspectRatio:
          project.aspect_ratio === '9:16' ? '9 / 16' : project.aspect_ratio === '1:1' ? '1 / 1' : '16 / 9',
        maxHeight: maxHeightStyle,
      }}
    >
      {(project.raw_video_url || project.final_video_url) ? (
        <video
          ref={videoRef}
          src={project.raw_video_url || project.final_video_url || ''}
          onTimeUpdate={() => {
            if (videoRef.current) setCurrentTime(videoRef.current.currentTime)
          }}
          onLoadedMetadata={() => {
            if (videoRef.current) setDuration(videoRef.current.duration)
          }}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          className="h-full w-full object-contain pointer-events-auto"
          playsInline
          style={{
            filter: videoFilterStyle,
            transform: videoTransformStyle,
            transition: 'filter 0.15s ease, transform 0.15s ease',
          }}
        />
      ) : (
        <div className="flex flex-col items-center justify-center p-12 text-slate-500">
          <p>無可預覽的影片檔</p>
        </div>
      )}

      {/* Hidden BGM Audio element synchronized with video */}
      <audio ref={bgmAudioRef} loop className="hidden" preload="auto" />

      {/* Draggable Live Subtitle Overlay on Video Player */}
      {(displayCue || showStyleModal || isDraggingSubtitle) && (
        <div
          style={{
            left: `${styleConfig.x}%`,
            top: `${styleConfig.y}%`,
            transform: 'translate(-50%, -50%)',
          }}
          onMouseDown={(e) => {
            e.preventDefault()
            e.stopPropagation()
            setIsDraggingSubtitle(true)
          }}
          className={`absolute z-30 max-w-[90%] select-none cursor-grab active:cursor-grabbing transition-transform group ${
            isDraggingSubtitle ? 'scale-105 ring-2 ring-primary ring-offset-2 ring-offset-black/50' : 'hover:scale-[1.02]'
          }`}
          title="按住滑鼠可拖曳到畫面任何位置"
        >
          {/* Visual Drag Handle & Coordinate Badge */}
          <div className={`absolute -top-7 left-1/2 -translate-x-1/2 flex items-center gap-1 rounded bg-black/85 px-1.5 py-0.5 text-[10px] font-mono text-cyan-300 shadow whitespace-nowrap pointer-events-none transition-opacity ${
            isDraggingSubtitle ? 'opacity-100' : 'opacity-0 group-hover:opacity-90'
          }`}>
            <Move size={10} className="text-primary" />
            <span>X: {styleConfig.x}% Y: {styleConfig.y}% (拖曳定位)</span>
          </div>

          {/* Subtitle Body with dynamic styles */}
          <div
            style={{
              fontFamily: styleConfig.fontFamily ? `"${styleConfig.fontFamily}", sans-serif` : 'sans-serif',
              fontSize: `${styleConfig.fontSize}px`,
              fontWeight: styleConfig.fontWeight === '900' ? 900 : styleConfig.fontWeight === 'bold' ? 700 : 500,
              color: styleConfig.textColor || '#ffffff',
              backgroundColor:
                styleConfig.preset === 'outline' || styleConfig.preset === 'clean'
                  ? 'transparent'
                  : `${styleConfig.bgColor}${Math.round((styleConfig.bgOpacity / 100) * 255).toString(16).padStart(2, '0')}`,
              backgroundImage:
                styleConfig.preset === 'gradient'
                  ? 'linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(245, 158, 11, 0.95))'
                  : 'none',
              borderRadius: `${styleConfig.borderRadius}px`,
              padding:
                styleConfig.preset === 'clean' || styleConfig.preset === 'outline'
                  ? '4px 10px'
                  : '8px 20px',
              WebkitTextStroke:
                styleConfig.strokeWidth > 0
                  ? `${styleConfig.strokeWidth}px ${styleConfig.strokeColor}`
                  : '0px transparent',
              paintOrder: 'stroke fill',
              textShadow:
                styleConfig.preset === 'neon'
                  ? '0 0 8px #06b6d4, 0 0 16px #0891b2'
                  : styleConfig.shadow
                    ? '0 2px 4px rgba(0,0,0,0.85)'
                    : 'none',
              letterSpacing: '0.04em',
              lineHeight: 1.6,
              maxHeight: '40vh',
              overflowY: 'auto',
            }}
            className="text-center tracking-wide shadow-2xl border border-transparent hover:border-cyan-400/40"
          >
            <span
              style={{
                color: styleConfig.textColor || '#ffffff',
                WebkitTextFillColor: styleConfig.textColor || '#ffffff',
                WebkitTextStroke:
                  styleConfig.strokeWidth > 0
                    ? `${styleConfig.strokeWidth}px ${styleConfig.strokeColor}`
                    : '0px transparent',
                paintOrder: 'stroke fill',
                display: 'inline-block',
              }}
            >
              {displayCue ? displayCue.text : (
                <span className="opacity-90 italic">
                  〔拖曳此處調整字幕位置：點擊按住拖動〕
                </span>
              )}
            </span>
          </div>
        </div>
      )}

      {/* Dragging Axis Guidelines */}
      {isDraggingSubtitle && (
        <>
          <div
            style={{ top: `${styleConfig.y}%` }}
            className="pointer-events-none absolute inset-x-0 h-px border-t border-dashed border-cyan-400/70"
          />
          <div
            style={{ left: `${styleConfig.x}%` }}
            className="pointer-events-none absolute inset-y-0 w-px border-l border-dashed border-cyan-400/70"
          />
        </>
      )}

      {/* Safety Frame Overlay */}
      {showSafeFrame && (
        <div className="pointer-events-none absolute inset-6 border border-dashed border-cyan-400/60">
          <div className="absolute top-1 left-1 font-mono text-[9px] text-cyan-300">SAFE AREA 90%</div>
        </div>
      )}
    </div>
  )

  return createPortal(
    <div className="fixed inset-0 z-[999999] flex flex-col bg-bg text-fg overflow-hidden">
      {/* Top Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-bg-elev px-4 shadow-sm">
        <div className="flex items-center gap-3">
          <button onClick={onClose} className="btn-ghost btn-sm" title={t('close')}>
            <X size={16} />
          </button>
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold tracking-tight">影音字幕剪輯工作台</h1>
            <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {project.title || '專案'}
            </span>
          </div>

          {/* FCP / Transcript Mode Switcher */}
          <div className="ml-3 flex items-center rounded-lg bg-slate-800/90 p-0.5 border border-slate-700/80">
            <button
              onClick={() => setEditorMode('fcp')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition ${
                editorMode === 'fcp'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
              title="切換至 Final Cut Pro 專業剪輯模式 (多軌磁性時間軸、濾鏡素材庫、屬性檢查器)"
            >
              <Layout size={13} />
              Final Cut Pro 專業剪輯
            </button>
            <button
              onClick={() => setEditorMode('transcript')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition ${
                editorMode === 'transcript'
                  ? 'bg-primary text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
              title="切換至逐字稿字幕模式 (逐行編輯、重配音試聽)"
            >
              <ListVideo size={13} />
              逐字稿字幕模式
            </button>
          </div>
        </div>

        {/* Primary Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownloadSrt}
            className="btn-secondary btn-sm gap-1 text-xs"
            title="下載當前編輯的所有字幕檔案 (.srt)"
          >
            <Download size={13} className="text-primary" />
            匯出字幕檔 (SRT)
          </button>

          <button
            onClick={handleDownloadVideo}
            className="btn-secondary btn-sm gap-1 text-xs"
            title="下載目前的影片檔案 (.mp4)"
          >
            <Download size={13} />
            匯出影片 (MP4)
          </button>

          <button
            onClick={() => {
              setTrimStart('0')
              setTrimEnd(duration ? duration.toFixed(1) : '10')
              setShowTrimModal(true)
            }}
            className="btn-secondary btn-sm gap-1 text-xs"
            title="裁切影片片段並匯出"
          >
            <Scissors size={13} />
            剪輯影片
          </button>

          <button
            onClick={handleBurnSubtitles}
            disabled={burning || cues.length === 0}
            className="btn-secondary btn-sm gap-1 text-xs text-amber-500 font-medium"
            title="將最新字幕永久燒錄進影片中並自動下載新影片"
          >
            <Flame size={13} className={burning ? 'animate-pulse' : ''} />
            {burning ? '燒錄匯出中…' : '燒錄字幕並匯出新影片'}
          </button>

          <button
            onClick={handleSaveSubtitles}
            disabled={saving}
            className="btn-primary btn-sm gap-1.5 text-xs font-medium"
            title="將字幕修改儲存至專案中"
          >
            <Check size={14} />
            {saving ? '儲存中…' : '儲存字幕'}
          </button>
        </div>
      </header>

      {/* Studio Workspace: Switchable FCP Pro Editing Mode vs Classic Transcript Mode */}
      {editorMode === 'fcp' ? (
        <div className="flex flex-1 flex-col overflow-hidden bg-[#0d1117]">
          {/* Upper 3-column Workspace: Effects Browser (L) + Center Video Monitor + Inspector (R) */}
          <div className="flex flex-1 min-h-0 overflow-hidden border-b border-slate-800/80">
            {/* Left: Effects & Scenes Browser */}
            <FcpEffectsBrowser
              project={project}
              scenes={scenes}
              activeFilter={activeFilter}
              onSelectFilter={setActiveFilter}
              onSeekToScene={(idx) => {
                if (scenes && scenes.length > 0) {
                  let t = 0
                  for (let i = 0; i < idx && i < scenes.length; i++) {
                    t += scenes[i].duration || (duration / scenes.length)
                  }
                  handleSeek(t)
                }
              }}
              activeBgmName={activeBgm}
              onSelectBgm={(bgmName) => {
                setActiveBgm(bgmName)
                toast.success(bgmName ? `已套用配樂：${bgmName}` : '已設為無配樂')
              }}
              tab={effectsBrowserTab}
              onChangeTab={setEffectsBrowserTab}
            />

            {/* Center: Video Viewer Monitor + FCP Mini Transport Bar */}
            <div className="flex flex-1 flex-col items-center justify-between overflow-hidden bg-[#080a0f] p-3">
              {/* Center Video Viewport */}
              <div className="relative flex flex-1 w-full items-center justify-center overflow-hidden">
                {renderVideoViewer('calc(100vh - 430px)')}
              </div>

              {/* FCP Mini Transport & Controls Bar */}
              <div className="flex h-11 w-full shrink-0 items-center justify-between rounded-lg border border-slate-800/90 bg-slate-900/90 px-4 text-xs shadow-inner mt-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleSeek(Math.max(0, currentTime - 1 / 30))}
                    className="btn-ghost btn-xs h-7 px-1.5 text-slate-400 hover:text-white"
                    title="上一幀 (←)"
                  >
                    ◀
                  </button>
                  <button
                    onClick={togglePlay}
                    className="grid h-7 w-7 place-items-center rounded-full bg-primary text-white shadow hover:opacity-90"
                    title={isPlaying ? '暫停 (Space)' : '播放 (Space)'}
                  >
                    {isPlaying ? <Pause size={13} /> : <Play size={13} className="ml-0.5" />}
                  </button>
                  <button
                    onClick={() => handleSeek(Math.min(duration, currentTime + 1 / 30))}
                    className="btn-ghost btn-xs h-7 px-1.5 text-slate-400 hover:text-white"
                    title="下一幀 (→)"
                  >
                    ▶
                  </button>

                  <div className="mx-1 h-4 w-px bg-slate-800" />

                  {/* Timecode (00:00:00:00) */}
                  <div className="flex items-center gap-1 font-mono text-xs tabular-nums">
                    <span className="font-semibold text-emerald-400">{formatFcpTimecode(currentTime)}</span>
                    <span className="text-slate-600">/</span>
                    <span className="text-slate-400">{formatFcpTimecode(duration)}</span>
                  </div>

                  <div className="mx-1 h-4 w-px bg-slate-800" />

                  {/* Blade quick split button */}
                  <button
                    onClick={() => {
                      if (activeCue) {
                        handleSplitCue(activeCue.id, currentTime)
                      } else {
                        toast.info('當前播放指針處無字幕可切分')
                      }
                    }}
                    className="flex items-center gap-1 rounded bg-slate-800/80 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-slate-700 hover:text-emerald-300 transition"
                    title="在當前播放指針精準刀片切分字幕 (快速鍵 C)"
                  >
                    <Scissors size={12} className="text-emerald-400" />
                    <span>刀片切分 (C)</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  {/* Active Filter Pill */}
                  {activeFilter !== 'none' && (
                    <span className="flex items-center gap-1 rounded bg-primary/20 px-2 py-0.5 text-[11px] font-medium text-primary">
                      <Sparkles size={11} />
                      {activeFilterObj?.name}
                    </span>
                  )}

                  {/* Playback speed */}
                  <button
                    onClick={cyclePlaybackRate}
                    className="rounded bg-slate-800/80 px-2 py-1 font-mono text-[11px] text-slate-300 hover:text-white"
                    title="播放倍速"
                  >
                    {playbackRate}x
                  </button>

                  <div className="mx-1 h-4 w-px bg-slate-800" />

                  {/* Subtitle style modal trigger */}
                  <button
                    onClick={() => setShowStyleModal(true)}
                    className={`btn-ghost btn-sm h-7 gap-1 text-xs ${showStyleModal ? 'bg-primary/20 text-primary' : 'text-slate-300 hover:text-white'}`}
                    title="字幕外觀與字型樣式"
                  >
                    <Type size={12} />
                    字幕樣式
                  </button>

                  {/* Safe frame trigger */}
                  <button
                    onClick={() => setShowSafeFrame((v) => !v)}
                    className={`btn-ghost btn-sm h-7 gap-1 text-xs ${showSafeFrame ? 'bg-primary/20 text-primary' : 'text-slate-400 hover:text-white'}`}
                    title="安全框顯示"
                  >
                    <Shield size={12} />
                    安全框
                  </button>
                </div>
              </div>
            </div>

            {/* Right: FCP Inspector */}
            <FcpInspector
              selectedCue={selectedCue}
              adjustments={adjustments}
              onChangeAdjustments={setAdjustments}
              playbackRate={playbackRate}
              onChangePlaybackRate={handleSetPlaybackRate}
              duration={duration}
              currentTime={currentTime}
              isPlaying={isPlaying}
              voiceVolume={voiceVolume}
              onChangeVoiceVolume={setVoiceVolume}
              voiceMuted={voiceMuted}
              onToggleVoiceMute={() => setVoiceMuted((v) => !v)}
              voiceSolo={voiceSolo}
              onToggleVoiceSolo={() => setVoiceSolo((v) => !v)}
              denoiseLevel={denoiseLevel}
              onChangeDenoiseLevel={setDenoiseLevel}
              antiClip={antiClip}
              onToggleAntiClip={() => setAntiClip((v) => !v)}
              bgmVolume={bgmVolume}
              onChangeBgmVolume={setBgmVolume}
              bgmMuted={bgmMuted}
              onToggleBgmMute={() => setBgmMuted((v) => !v)}
              bgmSolo={bgmSolo}
              onToggleBgmSolo={() => setBgmSolo((v) => !v)}
              audioDucking={audioDucking}
              onToggleAudioDucking={() => setAudioDucking((v) => !v)}
              activeBgmName={activeBgm}
              onOpenBgmSelector={() => setEffectsBrowserTab('audio')}
              onSynthesizeCue={handleSynthesizeCueById}
            />
          </div>

          {/* Lower Section: FCP Magnetic Multi-track Timeline */}
          <div className="h-[370px] shrink-0 border-t border-slate-800/80 bg-[#10131a]">
            <FcpTimeline
              duration={duration}
              currentTime={currentTime}
              isPlaying={isPlaying}
              cues={cues}
              scenes={scenes}
              audioPeaks={audioPeaks}
              voiceAudioData={voiceAudioData}
              bgmAudioData={bgmAudioData}
              denoiseLevel={denoiseLevel}
              onToggleDenoise={() => {
                const cycle: Record<string, 'off' | 'low' | 'med' | 'high'> = {
                  off: 'low',
                  low: 'med',
                  med: 'high',
                  high: 'off',
                }
                setDenoiseLevel((prev) => cycle[prev] || 'med')
              }}
              antiClip={antiClip}
              onToggleAntiClip={() => setAntiClip((v) => !v)}
              selectedCueId={selectedCueId}
              onSeek={handleSeek}
              onTogglePlay={togglePlay}
              onSelectCue={(id) => {
                setSelectedCueId(id)
                if (id !== null) {
                  const c = cues.find((x) => x.id === id)
                  if (c) handleSeek(c.start)
                }
              }}
              onSplitCue={handleSplitCue}
              onDeleteCue={handleDeleteCue}
              onUpdateCueTimes={handleUpdateCueTime}
              voiceMuted={voiceMuted}
              onToggleVoiceMute={() => setVoiceMuted((v) => !v)}
              voiceSolo={voiceSolo}
              onToggleVoiceSolo={() => setVoiceSolo((v) => !v)}
              voiceVolume={voiceVolume}
              onChangeVoiceVolume={setVoiceVolume}
              bgmMuted={bgmMuted}
              onToggleBgmMute={() => setBgmMuted((v) => !v)}
              bgmSolo={bgmSolo}
              onToggleBgmSolo={() => setBgmSolo((v) => !v)}
              bgmVolume={bgmVolume}
              onChangeBgmVolume={setBgmVolume}
              audioDucking={audioDucking}
              onToggleAudioDucking={() => setAudioDucking((v) => !v)}
              activeBgmName={activeBgm}
              onOpenBgmSelector={() => setEffectsBrowserTab('audio')}
              onSynthesizeCue={handleSynthesizeCueById}
            />
          </div>
        </div>
      ) : (
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* TOP SECTION: Waveform Track with Subtitle Segment Blocks */}
          <section className="relative border-b border-border bg-slate-900/90 text-slate-100">
        {/* Track Top Status Bar */}
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-1.5 text-[11px] text-slate-400">
          <div className="flex items-center gap-2">
            {focusedCue ? (
              <span>
                這句 開始 <span className="font-mono text-emerald-400">{focusedCue.start.toFixed(3)}</span> 結束{' '}
                <span className="font-mono text-emerald-400">{focusedCue.end.toFixed(3)}</span>{' '}
                <span className="font-mono text-slate-300">{(focusedCue.end - focusedCue.start).toFixed(3)} 秒</span>
              </span>
            ) : (
              <span>全片時長 {formatDuration(duration)}</span>
            )}
            <span className="rounded bg-emerald-500/20 px-1.5 py-0.2 text-[10px] font-medium text-emerald-300">
              切點偵測
            </span>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => activeCue && handleSplitCue(activeCue.id)}
              disabled={!activeCue}
              className="flex items-center gap-1 hover:text-emerald-400 disabled:opacity-40"
              title="在當前時間點切分此句"
            >
              <Scissors size={12} />
              切點分割
            </button>
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-[10px] text-slate-400">縮放</span>
              <button
                onClick={() => setZoom((z) => Math.max(0.1, z - 0.1))}
                className="hover:text-white"
                title="縮小時間軸"
              >
                <ZoomOut size={12} />
              </button>
              <span className="w-8 text-center font-mono text-[11px]">{Math.round(zoom * 100)}%</span>
              <button
                onClick={() => setZoom((z) => Math.min(2.0, z + 0.1))}
                className="hover:text-white"
                title="放大時間軸"
              >
                <ZoomIn size={12} />
              </button>
            </div>
          </div>
        </div>

        {/* Waveform & Cues Timeline Area */}
        <div
          ref={timelineRef}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect()
            const clickX = e.clientX - rect.left
            const pct = clickX / rect.width
            handleSeek(pct * duration)
          }}
          className="relative h-28 cursor-pointer select-none overflow-hidden bg-slate-950 px-2"
        >
          {/* Waveform Canvas */}
          <canvas ref={canvasRef} width={1200} height={112} className="h-full w-full opacity-85" />

          {/* Subtitle Cue Boxes overlaid on the timeline */}
          <div className="pointer-events-none absolute inset-0 flex items-center">
            {duration > 0 &&
              cues.map((cue) => {
                const leftPct = (cue.start / duration) * 100
                const widthPct = Math.max(1.5, ((cue.end - cue.start) / duration) * 100)
                const isActive = (displayCue?.id ?? activeCue?.id) === cue.id

                return (
                  <div
                    key={cue.id}
                    style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedCueId(cue.id)
                      handleSeek(cue.start + 0.05)
                    }}
                    className={`pointer-events-auto absolute top-2 bottom-2 flex flex-col justify-between overflow-hidden rounded-md border px-1.5 py-1 text-[11px] transition-all cursor-pointer ${
                      isActive
                        ? 'border-emerald-400 bg-emerald-500/35 text-white shadow-lg ring-1 ring-emerald-400'
                        : 'border-slate-700/80 bg-slate-800/80 text-slate-200 hover:border-slate-500 hover:bg-slate-700/80'
                    }`}
                  >
                    <span className="truncate font-medium leading-tight">{cue.text}</span>
                    <div className="flex items-center justify-between text-[9px] text-slate-400">
                      <span>{cue.start.toFixed(1)}s</span>
                      <span>{cue.end.toFixed(1)}s</span>
                    </div>
                  </div>
                )
              })}
          </div>

          {/* Draggable Playhead */}
          {duration > 0 && (
            <div
              style={{ left: `${(currentTime / duration) * 100}%` }}
              className="pointer-events-none absolute top-0 bottom-0 z-20 w-0.5 bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]"
            >
              <div className="-translate-x-1/2 absolute top-0 h-3 w-3 rounded-full border border-white bg-red-600 shadow" />
            </div>
          )}
        </div>
      </section>

      {/* MID TOOLBAR: Play controls, Time, Speed, Style, Safe Frame */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-bg-elev px-4 text-xs">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlay}
            className="grid h-7 w-7 place-items-center rounded-full bg-primary text-primary-fg transition hover:opacity-90"
            title={isPlaying ? '暫停 (Space)' : '播放 (Space)'}
          >
            {isPlaying ? <Pause size={13} /> : <Play size={13} className="ml-0.5" />}
          </button>

          <div className="font-mono text-xs tabular-nums text-muted">
            <span className="font-semibold text-fg">{formatTimestamp(currentTime)}</span>
            <span className="mx-1">/</span>
            <span>{formatTimestamp(duration)}</span>
          </div>

          <button
            onClick={cyclePlaybackRate}
            className="btn-ghost btn-sm h-7 px-2 font-mono text-xs"
            title="切換播放倍率"
          >
            {playbackRate}x
          </button>

          <div className="mx-1 h-4 w-px bg-border" />

          <button
            onClick={handleUndo}
            disabled={historyIdx <= 0}
            className="btn-ghost btn-sm h-7 px-1.5 disabled:opacity-30"
            title="復原 (Ctrl+Z)"
          >
            <RotateCcw size={13} />
          </button>
          <button
            onClick={handleRedo}
            disabled={historyIdx >= history.length - 1}
            className="btn-ghost btn-sm h-7 px-1.5 disabled:opacity-30"
            title="重做 (Ctrl+Shift+Z)"
          >
            <RotateCw size={13} />
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick Action Buttons in Toolbar */}
          <button
            onClick={handleDownloadSrt}
            className="btn-secondary btn-sm h-7 gap-1 px-2.5 text-xs font-medium"
            title="立即下載當前編輯的所有字幕檔案 (.srt)"
          >
            <Download size={12} className="text-primary" />
            匯出字幕 (SRT)
          </button>

          <button
            onClick={handleDownloadVideo}
            className="btn-secondary btn-sm h-7 gap-1 px-2.5 text-xs font-medium"
            title="下載目前的影片檔案 (.mp4)"
          >
            <Download size={12} />
            匯出影片 (MP4)
          </button>

          <button
            onClick={handleBurnSubtitles}
            disabled={burning || cues.length === 0}
            className="btn-secondary btn-sm h-7 gap-1 px-2.5 text-xs text-amber-500 font-semibold"
            title="將最新字幕永久燒錄進影片中並自動下載新影片"
          >
            <Flame size={12} className={burning ? 'animate-pulse' : ''} />
            {burning ? '燒錄匯出中…' : '燒錄字幕並匯出'}
          </button>

          <button
            onClick={handleSaveSubtitles}
            disabled={saving}
            className="btn-primary btn-sm h-7 gap-1 px-2.5 text-xs font-semibold"
            title="將字幕修改儲存至專案中"
          >
            <Check size={12} />
            {saving ? '儲存中…' : '儲存字幕'}
          </button>

          <div className="mx-1 h-4 w-px bg-border" />

          <button
            onClick={() => setShowStyleModal((v) => !v)}
            className={`btn-ghost btn-sm h-7 gap-1 ${showStyleModal ? 'bg-primary/10 text-primary' : ''}`}
            title="自訂字幕外觀樣式"
          >
            <Type size={13} />
            字幕樣式
          </button>

          <button
            onClick={() => setShowSafeFrame((v) => !v)}
            className={`btn-ghost btn-sm h-7 gap-1 ${showSafeFrame ? 'bg-primary/10 text-primary' : ''}`}
            title="顯示 9:16 / 16:9 安全框"
          >
            <Shield size={13} />
            安全框
          </button>

          <button
            onClick={() => setShowImportModal(true)}
            className="btn-ghost btn-sm h-7 gap-1"
            title="匯入或貼上 SRT 字幕"
          >
            <Upload size={13} />
            匯入修正字幕
          </button>

          <button
            onClick={() => setShowShortcutsModal(true)}
            className="btn-ghost btn-sm h-7 gap-1"
            title="檢視快捷鍵"
          >
            <Keyboard size={13} />
            快捷鍵
          </button>
        </div>
      </div>

      {/* MAIN STUDIO BODY: Left Video Preview + Right Transcript List */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT: Video Player + Real-time Styled Subtitle Overlay */}
        <div className="relative flex flex-1 flex-col items-center justify-center bg-black/95 p-4 overflow-hidden">
          {renderVideoViewer('calc(100vh - 240px)')}
        </div>

        {/* RIGHT: Subtitle Transcript List */}
        <div className="flex w-[480px] shrink-0 flex-col border-l border-border bg-bg">
          {/* Search & Add Cue Bar */}
          <div className="flex items-center gap-2 border-b border-border p-3">
            <div className="relative flex-1">
              <Search size={14} className="absolute top-2.5 left-2.5 text-muted" />
              <input
                type="text"
                placeholder="搜尋字幕…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input input-sm h-8 w-full pl-8 text-xs"
              />
            </div>
            <button
              onClick={handleInsertCue}
              className="btn-secondary btn-sm h-8 shrink-0 gap-1 text-xs"
              title="在當前時間插入新句子"
            >
              <Plus size={13} />
              新增句子
            </button>
            <button
              onClick={handleDownloadSrt}
              className="btn-ghost btn-sm h-8 shrink-0 gap-1 text-xs"
              title="下載目前編輯的字幕檔 (.srt)"
            >
              <Download size={13} />
              匯出 SRT
            </button>
          </div>

          {/* Subtitle Cue List */}
          <div className="flex-1 overflow-y-auto p-2">
            {loading ? (
              <div className="py-12 text-center text-xs text-muted">載入字幕清單中…</div>
            ) : filteredCues.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted">無字幕記錄</div>
            ) : (
              <div className="space-y-1.5">
                {filteredCues.map((cue, idx) => {
                  const isActive = (displayCue?.id ?? activeCue?.id) === cue.id
                  const isSelected = selectedCueId === cue.id

                  return (
                    <div
                      key={cue.id}
                      ref={isActive ? activeItemRef : null}
                      onClick={() => {
                        setSelectedCueId(cue.id)
                        handleSeek(cue.start + 0.05)
                      }}
                      className={`group relative flex items-start gap-2.5 rounded-lg border p-2 text-xs transition cursor-pointer ${
                        isActive
                          ? 'border-emerald-500 bg-emerald-500/10 shadow-sm'
                          : isSelected
                            ? 'border-primary bg-primary/5'
                            : 'border-border/60 bg-bg-elev/50 hover:border-border hover:bg-bg-elev'
                      }`}
                    >
                      {/* Timestamp Badge */}
                      <span
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedCueId(cue.id)
                          handleSeek(cue.start + 0.05)
                        }}
                        className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-mono text-[11px] font-medium select-none cursor-pointer ${
                          isActive
                            ? 'bg-emerald-500 text-white'
                            : 'bg-muted/15 text-muted hover:bg-muted/25 hover:text-fg'
                        }`}
                      >
                        {formatShortTimestamp(cue.start)}
                      </span>

                      {/* Subtitle Text (Editable inline) */}
                      <textarea
                        rows={1}
                        value={cue.text}
                        onFocus={() => {
                          setSelectedCueId(cue.id)
                          handleSeek(cue.start + 0.05)
                        }}
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedCueId(cue.id)
                          handleSeek(cue.start + 0.05)
                        }}
                        onChange={(e) => handleTextChange(cue.id, e.target.value)}
                        className="flex-1 resize-none bg-transparent p-0 text-xs font-normal leading-relaxed text-fg focus:outline-none"
                      />

                      {/* Character Count & Action Buttons */}
                      <div className="flex shrink-0 items-center gap-1">
                        <span className="font-mono text-[10px] text-muted">
                          {cue.text.replace(/\s+/g, '').length}
                        </span>

                        {/* Split Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleSplitCue(cue.id)
                          }}
                          className="btn-ghost h-6 w-6 p-0 text-muted opacity-0 group-hover:opacity-100 hover:text-emerald-500"
                          title="在切點分割"
                        >
                          <Scissors size={11} />
                        </button>

                        {/* Merge Button */}
                        {idx < filteredCues.length - 1 && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleMergeNext(cue.id)
                            }}
                            className="btn-ghost h-6 w-6 p-0 text-muted opacity-0 group-hover:opacity-100 hover:text-primary"
                            title="與下一句合併"
                          >
                            <Link2 size={11} />
                          </button>
                        )}

                        {/* TTS Synthesize Preview */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleSynthesizeCue(cue)
                          }}
                          disabled={synthesizingId === cue.id}
                          className="btn-ghost h-6 w-6 p-0 text-muted opacity-0 group-hover:opacity-100 hover:text-amber-500"
                          title="重新配音試聽"
                        >
                          <Volume2 size={11} className={synthesizingId === cue.id ? 'animate-pulse text-amber-500' : ''} />
                        </button>

                        {/* Delete Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDeleteCue(cue.id)
                          }}
                          className="btn-ghost h-6 w-6 p-0 text-muted opacity-0 group-hover:opacity-100 hover:text-red-500"
                          title="刪除"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Bottom Info Bar: Timing, Words & CPS Speed analysis (matching user screenshot) */}
          {cueStats && (
            <div className="flex items-center justify-between border-t border-border bg-bg-elev/80 px-4 py-2 font-mono text-[11px] text-muted">
              <div>
                <span>{cueStats.startFormatted}</span>
                <span className="mx-2">·</span>
                <span>{cueStats.dur} 秒</span>
                <span className="mx-2">·</span>
                <span>{cueStats.chars} 字</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-fg">{cueStats.cps} 字/秒</span>
                <span
                  className={`rounded px-1.5 py-0.2 text-[10px] font-medium ${
                    cueStats.speedRating === '偏快'
                      ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400'
                      : 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400'
                  }`}
                >
                  {cueStats.speedRating}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )}

      {/* Subtitle Style & Visual Effects Modal */}
      {showStyleModal && (
        <div className="fixed inset-0 z-[1000000] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="card w-full max-w-xl max-h-[90vh] flex flex-col p-5 shadow-2xl overflow-hidden border border-border">
            <div className="flex items-center justify-between border-b border-border pb-3 shrink-0">
              <div className="flex items-center gap-2">
                <div className="grid h-7 w-7 place-items-center rounded bg-primary/10 text-primary">
                  <Palette size={16} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold">字幕樣式、字型與特效設定</h3>
                  <p className="text-[11px] text-muted">自由拖曳畫面位置，自訂豐富字型與視覺包裝風格</p>
                </div>
              </div>
              <button onClick={() => setShowStyleModal(false)} className="btn-ghost btn-sm">
                <X size={14} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 py-4 pr-1 text-xs">
              {/* Preset Visual Styles */}
              <div>
                <label className="text-muted block mb-2 font-medium flex items-center gap-1.5">
                  <Sparkles size={13} className="text-amber-400" />
                  精選樣式預設
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() =>
                      setStyleConfig((c) => ({
                        ...c,
                        preset: 'pill',
                        bgColor: '#2563eb',
                        bgOpacity: 90,
                        textColor: '#ffffff',
                        borderRadius: 8,
                        fontWeight: 'bold',
                        strokeWidth: 0,
                        strokeColor: '#000000',
                        shadow: true,
                      }))
                    }
                    className={`rounded-lg border p-2 text-left transition ${
                      styleConfig.preset === 'pill' ? 'border-primary bg-primary/10 text-primary font-medium ring-1 ring-primary' : 'border-border hover:bg-muted/10'
                    }`}
                  >
                    <div className="font-semibold">深藍膠囊 (預設)</div>
                    <div className="text-[10px] text-muted">科技沉穩、清晰可讀</div>
                  </button>

                  <button
                    onClick={() =>
                      setStyleConfig((c) => ({
                        ...c,
                        preset: 'punch',
                        bgColor: '#facc15',
                        bgOpacity: 95,
                        textColor: '#000000',
                        borderRadius: 6,
                        fontWeight: '900',
                        strokeWidth: 0,
                        strokeColor: '#000000',
                        shadow: true,
                      }))
                    }
                    className={`rounded-lg border p-2 text-left transition ${
                      styleConfig.preset === 'punch' ? 'border-primary bg-primary/10 text-primary font-medium ring-1 ring-primary' : 'border-border hover:bg-muted/10'
                    }`}
                  >
                    <div className="font-semibold text-amber-500">💥 活力鮮黃黑字</div>
                    <div className="text-[10px] text-muted">YouTube/TikTok 爆款解說</div>
                  </button>

                  <button
                    onClick={() =>
                      setStyleConfig((c) => ({
                        ...c,
                        preset: 'gradient',
                        bgColor: '#ef4444',
                        bgOpacity: 95,
                        textColor: '#ffffff',
                        borderRadius: 12,
                        fontWeight: 'bold',
                        strokeWidth: 1,
                        strokeColor: '#7f1d1d',
                        shadow: true,
                      }))
                    }
                    className={`rounded-lg border p-2 text-left transition ${
                      styleConfig.preset === 'gradient' ? 'border-primary bg-primary/10 text-primary font-medium ring-1 ring-primary' : 'border-border hover:bg-muted/10'
                    }`}
                  >
                    <div className="font-semibold text-rose-500">🔥 綜藝漸層紅橘</div>
                    <div className="text-[10px] text-muted">吸睛強烈、氛圍突出</div>
                  </button>

                  <button
                    onClick={() =>
                      setStyleConfig((c) => ({
                        ...c,
                        preset: 'neon',
                        bgColor: '#000000',
                        bgOpacity: 70,
                        textColor: '#22d3ee',
                        borderRadius: 10,
                        fontWeight: 'bold',
                        strokeWidth: 1,
                        strokeColor: '#0891b2',
                        shadow: true,
                      }))
                    }
                    className={`rounded-lg border p-2 text-left transition ${
                      styleConfig.preset === 'neon' ? 'border-primary bg-primary/10 text-primary font-medium ring-1 ring-primary' : 'border-border hover:bg-muted/10'
                    }`}
                  >
                    <div className="font-semibold text-cyan-400">⚡ 賽博霓虹發光</div>
                    <div className="text-[10px] text-muted">光暈投影、未來科技感</div>
                  </button>

                  <button
                    onClick={() =>
                      setStyleConfig((c) => ({
                        ...c,
                        preset: 'box',
                        bgColor: '#000000',
                        bgOpacity: 85,
                        textColor: '#ffffff',
                        borderRadius: 6,
                        fontWeight: 'bold',
                        strokeWidth: 0,
                        strokeColor: '#000000',
                        shadow: false,
                      }))
                    }
                    className={`rounded-lg border p-2 text-left transition ${
                      styleConfig.preset === 'box' ? 'border-primary bg-primary/10 text-primary font-medium ring-1 ring-primary' : 'border-border hover:bg-muted/10'
                    }`}
                  >
                    <div className="font-semibold">經典黑底白字</div>
                    <div className="text-[10px] text-muted">高對比、不遮擋畫面</div>
                  </button>

                  <button
                    onClick={() =>
                      setStyleConfig((c) => ({
                        ...c,
                        preset: 'outline',
                        bgColor: '#000000',
                        bgOpacity: 0,
                        textColor: '#ffffff',
                        borderRadius: 0,
                        fontWeight: 'bold',
                        strokeWidth: 2,
                        strokeColor: '#000000',
                        shadow: true,
                      }))
                    }
                    className={`rounded-lg border p-2 text-left transition ${
                      styleConfig.preset === 'outline' ? 'border-primary bg-primary/10 text-primary font-medium ring-1 ring-primary' : 'border-border hover:bg-muted/10'
                    }`}
                  >
                    <div className="font-semibold">透底黑描邊</div>
                    <div className="text-[10px] text-muted">簡約俐落、大片電影感</div>
                  </button>
                </div>
              </div>

              {/* Font Selection and Custom Font */}
              <div className="rounded-lg border border-border p-3 space-y-3 bg-muted/5">
                <label className="text-muted block font-medium flex items-center justify-between">
                  <span>字型選擇與新增</span>
                  <span className="text-[10px] text-primary">支援本機與自訂字型</span>
                </label>

                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: '微軟正黑體 (推薦繁中)', font: 'Microsoft JhengHei' },
                    { label: '思源黑體 (Noto Sans)', font: 'Noto Sans TC' },
                    { label: '標楷體 / 書法體', font: 'DFKai-SB' },
                    { label: '圓體 / 可愛俏皮', font: 'YouYuan' },
                    { label: 'Arial (簡約英數)', font: 'Arial' },
                    { label: 'Impact (厚重粗體)', font: 'Impact' },
                  ].map((f) => (
                    <button
                      key={f.font}
                      onClick={() => setStyleConfig((c) => ({ ...c, fontFamily: f.font }))}
                      style={{ fontFamily: `"${f.font}", sans-serif` }}
                      className={`truncate rounded border px-2.5 py-1.5 text-left text-xs transition ${
                        styleConfig.fontFamily === f.font
                          ? 'border-primary bg-primary/15 text-primary font-semibold'
                          : 'border-border hover:bg-muted/15'
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>

                {/* Custom Font Input */}
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="text"
                    placeholder="輸入本機字型名稱 (例: GenYoGothic, PingFang TC, 芫荽...)"
                    value={customFontInput}
                    onChange={(e) => setCustomFontInput(e.target.value)}
                    className="input input-sm flex-1 text-xs"
                  />
                  <button
                    onClick={() => {
                      if (!customFontInput.trim()) return
                      setStyleConfig((c) => ({ ...c, fontFamily: customFontInput.trim() }))
                      toast.success(`已套用字型: ${customFontInput.trim()}`)
                    }}
                    className="btn-secondary btn-sm shrink-0 text-xs"
                  >
                    套用自訂字型
                  </button>
                </div>
                {styleConfig.fontFamily && (
                  <div className="text-[10px] text-muted">
                    目前生效字型：<span className="font-mono text-primary font-medium">{styleConfig.fontFamily}</span>
                  </div>
                )}
              </div>

              {/* Color, Size, Stroke and Effects Customization */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-muted font-medium">字體大小 ({styleConfig.fontSize}px)</label>
                  </div>
                  <input
                    type="range"
                    min={14}
                    max={48}
                    value={styleConfig.fontSize}
                    onChange={(e) => setStyleConfig((c) => ({ ...c, fontSize: parseInt(e.target.value, 10) }))}
                    className="w-full"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-muted font-medium">字體粗細</label>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    {(['normal', 'bold', '900'] as const).map((w) => (
                      <button
                        key={w}
                        onClick={() => setStyleConfig((c) => ({ ...c, fontWeight: w }))}
                        className={`rounded border py-1 text-center text-xs transition ${
                          styleConfig.fontWeight === w ? 'border-primary bg-primary/10 text-primary font-semibold' : 'border-border'
                        }`}
                      >
                        {w === 'normal' ? '常規' : w === 'bold' ? '粗體' : '極粗'}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-muted block mb-1 font-medium">文字顏色</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={styleConfig.textColor}
                      onChange={(e) => setStyleConfig((c) => ({ ...c, textColor: e.target.value }))}
                      className="h-7 w-10 cursor-pointer rounded border border-border bg-transparent p-0.5"
                    />
                    <input
                      type="text"
                      value={styleConfig.textColor}
                      onChange={(e) => setStyleConfig((c) => ({ ...c, textColor: e.target.value }))}
                      className="input input-sm font-mono text-xs uppercase w-24"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-muted block mb-1 font-medium">背景顏色與透明度 ({styleConfig.bgOpacity}%)</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={styleConfig.bgColor}
                      onChange={(e) => setStyleConfig((c) => ({ ...c, bgColor: e.target.value }))}
                      className="h-7 w-10 cursor-pointer rounded border border-border bg-transparent p-0.5"
                    />
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={styleConfig.bgOpacity}
                      onChange={(e) => setStyleConfig((c) => ({ ...c, bgOpacity: parseInt(e.target.value, 10) }))}
                      className="flex-1"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-muted font-medium">文字描邊 ({styleConfig.strokeWidth}px)</label>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={styleConfig.strokeColor}
                      onChange={(e) => setStyleConfig((c) => ({ ...c, strokeColor: e.target.value }))}
                      className="h-7 w-10 cursor-pointer rounded border border-border bg-transparent p-0.5"
                    />
                    <input
                      type="range"
                      min={0}
                      max={8}
                      value={styleConfig.strokeWidth}
                      onChange={(e) => setStyleConfig((c) => ({ ...c, strokeWidth: parseInt(e.target.value, 10) }))}
                      className="flex-1"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-muted font-medium">背景圓角大小 ({styleConfig.borderRadius}px)</label>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={24}
                    value={styleConfig.borderRadius}
                    onChange={(e) => setStyleConfig((c) => ({ ...c, borderRadius: parseInt(e.target.value, 10) }))}
                    className="w-full"
                  />
                </div>
              </div>

              {/* Position Coordinate and Quick Snapping */}
              <div className="rounded-lg border border-border p-3 space-y-2.5">
                <div className="flex items-center justify-between">
                  <label className="text-muted font-medium flex items-center gap-1.5">
                    <Move size={13} />
                    字幕座標與畫面位置
                  </label>
                  <span className="font-mono text-xs text-primary font-medium">
                    水平: {styleConfig.x}% / 垂直: {styleConfig.y}%
                  </span>
                </div>
                <p className="text-[11px] text-muted">
                  💡 提示：您可直接在**視訊畫面上用滑鼠按住字幕自由拖曳**到任何角落；亦可點擊下方快速定位：
                </p>
                <div className="grid grid-cols-4 gap-2">
                  <button
                    onClick={() => setStyleConfig((c) => ({ ...c, x: 50, y: 86 }))}
                    className="rounded border border-border p-1.5 text-center hover:bg-muted/15"
                  >
                    底部標準 (86%)
                  </button>
                  <button
                    onClick={() => setStyleConfig((c) => ({ ...c, x: 50, y: 50 }))}
                    className="rounded border border-border p-1.5 text-center hover:bg-muted/15"
                  >
                    中央焦點 (50%)
                  </button>
                  <button
                    onClick={() => setStyleConfig((c) => ({ ...c, x: 50, y: 14 }))}
                    className="rounded border border-border p-1.5 text-center hover:bg-muted/15"
                  >
                    頂部橫幅 (14%)
                  </button>
                  <button
                    onClick={() => setStyleConfig((c) => ({ ...c, x: 25, y: 86 }))}
                    className="rounded border border-border p-1.5 text-center hover:bg-muted/15"
                  >
                    偏左底部 (25%)
                  </button>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between border-t border-border pt-3 shrink-0">
              <span className="text-[11px] text-muted">
                拖曳完畢後，點擊「燒錄字幕並匯出」即可輸出含此排版的永久影片！
              </span>
              <button onClick={() => setShowStyleModal(false)} className="btn-primary btn-sm">
                確定套用
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trim Video Modal */}
      {showTrimModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="card w-full max-w-md p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-sm font-semibold">剪輯影片片段</h3>
              <button onClick={() => setShowTrimModal(false)} className="btn-ghost btn-sm">
                <X size={14} />
              </button>
            </div>

            <div className="space-y-4 py-4 text-xs">
              <p className="text-muted leading-relaxed">
                指定裁剪的開始與結束時間（秒），系統將無損裁剪輸出全新視訊片段：
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-muted block mb-1">開始時間 (秒)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={trimStart}
                    onChange={(e) => setTrimStart(e.target.value)}
                    className="input input-sm w-full"
                  />
                </div>
                <div>
                  <label className="text-muted block mb-1">結束時間 (秒)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={trimEnd}
                    onChange={(e) => setTrimEnd(e.target.value)}
                    className="input input-sm w-full"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowTrimModal(false)} className="btn-secondary btn-sm">
                取消
              </button>
              <button onClick={handleTrimVideo} disabled={trimming} className="btn-primary btn-sm">
                {trimming ? '剪輯處理中…' : '確認剪輯'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Keyboard Shortcuts Modal */}
      {showShortcutsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="card w-full max-w-sm p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-sm font-semibold">快捷鍵一覽</h3>
              <button onClick={() => setShowShortcutsModal(false)} className="btn-ghost btn-sm">
                <X size={14} />
              </button>
            </div>

            <div className="space-y-2.5 py-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted">播放 / 暫停</span>
                <kbd className="rounded bg-muted/20 px-2 py-0.5 font-mono text-[11px]">Space</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">快退 1 秒 / 快進 1 秒</span>
                <kbd className="rounded bg-muted/20 px-2 py-0.5 font-mono text-[11px]">← / →</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">復原 / 重做</span>
                <kbd className="rounded bg-muted/20 px-2 py-0.5 font-mono text-[11px]">Ctrl+Z / Ctrl+Shift+Z</kbd>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted">在當前時間點分割</span>
                <span className="text-emerald-500 font-medium">切點分割按鈕</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button onClick={() => setShowShortcutsModal(false)} className="btn-secondary btn-sm">
                關閉
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import SRT Subtitles Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="card w-full max-w-lg p-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="text-sm font-semibold">匯入 / 貼上 SRT 字幕</h3>
              <button onClick={() => setShowImportModal(false)} className="btn-ghost btn-sm">
                <X size={14} />
              </button>
            </div>

            <div className="space-y-3 py-4 text-xs">
              <p className="text-muted leading-relaxed">
                貼上標準 SRT 格式字幕（包含時間標籤與內容），系統將自動解析替換現有字幕清單：
              </p>
              <textarea
                rows={9}
                placeholder={`1\n00:00:01,000 --> 00:00:03,500\n第一句字幕內容\n\n2\n00:00:03,600 --> 00:00:06,000\n第二句字幕內容`}
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                className="input w-full font-mono text-xs leading-relaxed"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowImportModal(false)} className="btn-secondary btn-sm">
                取消
              </button>
              <button onClick={handleImportSubtitles} className="btn-primary btn-sm">
                解析並匯入
              </button>
            </div>
          </div>
        </div>
      )}
    </div>,
    document.body
  )
}

function formatTimestamp(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00.000'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  const m = String(mins).padStart(2, '0')
  const s = secs.toFixed(3).padStart(6, '0')
  return `${m}:${s}`
}

function formatShortTimestamp(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00'
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function roundTo3(val: number): number {
  return Math.round(val * 1000) / 1000
}
