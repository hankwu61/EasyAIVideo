import { useRef, useState, useEffect, useCallback } from 'react'
import {
  Magnet,
  MousePointer,
  Scissors,
  Split,
  Trash2,
  Volume2,
  VolumeX,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Film,
  Type,
  Music,
  Plus,
} from 'lucide-react'
import type { SubtitleCue, Scene } from '../../types'
import { formatDuration } from '../../utils'
import {
  DecodedAudioData,
  extractCuePeaks,
  extractTimelinePeaks,
} from '../../utils/audioWaveform'
import FcpClipWaveform from './FcpClipWaveform'

export type FcpTool = 'select' | 'blade' | 'trim'

interface FcpTimelineProps {
  duration: number
  currentTime: number
  onSeek: (time: number) => void
  cues: SubtitleCue[]
  selectedCueId: number | null
  onSelectCue: (id: number | null) => void
  onSplitCue: (cueId: number, splitTime: number) => void
  onDeleteCue: (cueId: number) => void
  onUpdateCueTimes?: (cueId: number, newStart: number, newEnd: number) => void
  scenes?: Scene[]
  audioPeaks?: number[]
  isPlaying: boolean
  onTogglePlay: () => void

  // Audio Channel Controls & Real Audio Data
  voiceAudioData?: DecodedAudioData | null
  bgmAudioData?: DecodedAudioData | null
  denoiseLevel?: 'off' | 'low' | 'med' | 'high'
  onToggleDenoise?: () => void
  antiClip?: boolean
  onToggleAntiClip?: () => void

  voiceMuted?: boolean
  onToggleVoiceMute?: () => void
  voiceSolo?: boolean
  onToggleVoiceSolo?: () => void
  voiceVolume?: number
  onChangeVoiceVolume?: (newVolume: number) => void

  bgmMuted?: boolean
  onToggleBgmMute?: () => void
  bgmSolo?: boolean
  onToggleBgmSolo?: () => void
  bgmVolume?: number
  onChangeBgmVolume?: (newVolume: number) => void
  audioDucking?: boolean
  onToggleAudioDucking?: () => void
  activeBgmName?: string | null
  onOpenBgmSelector?: () => void
  onSynthesizeCue?: (cueId: number) => void
}

export default function FcpTimeline({
  duration,
  currentTime,
  onSeek,
  cues,
  selectedCueId,
  onSelectCue,
  onSplitCue,
  onDeleteCue,
  onUpdateCueTimes: _onUpdateCueTimes,
  scenes = [],
  audioPeaks: _audioPeaks = [],
  voiceAudioData = null,
  bgmAudioData = null,
  denoiseLevel = 'med',
  onToggleDenoise,
  antiClip = true,
  onToggleAntiClip,
  voiceMuted = false,
  onToggleVoiceMute,
  voiceSolo = false,
  onToggleVoiceSolo,
  voiceVolume = 100,
  onChangeVoiceVolume,
  bgmMuted = false,
  onToggleBgmMute,
  bgmSolo = false,
  onToggleBgmSolo,
  bgmVolume = 20,
  onChangeBgmVolume,
  audioDucking = true,
  onToggleAudioDucking,
  activeBgmName,
  onOpenBgmSelector,
  onSynthesizeCue,
}: FcpTimelineProps) {
  const [activeTool, setActiveTool] = useState<FcpTool>('select')
  const [snapping, setSnapping] = useState<boolean>(true)
  const [zoom, setZoom] = useState<number>(1.0) // 1.0 = standard, up to 3.0
  const [isScrubbing, setIsScrubbing] = useState<boolean>(false)
  const [hoverTime, setHoverTime] = useState<number | null>(null)

  const timelineContainerRef = useRef<HTMLDivElement | null>(null)
  const scrollAreaRef = useRef<HTMLDivElement | null>(null)

  // Total width of the timeline canvas based on duration and zoom
  // Base: 100 pixels per 5 seconds * zoom -> 20px per second * zoom
  const pxPerSec = Math.max(15, 28 * zoom)
  const totalTimelineWidth = Math.max(1000, duration * pxPerSec + 200)

  // Format timecode for FCP ruler: HH:MM:SS:FF
  const formatTimecode = (seconds: number) => {
    const s = Math.max(0, seconds)
    const m = Math.floor(s / 60)
    const remS = Math.floor(s % 60)
    const frames = Math.floor((s - Math.floor(s)) * 30)
    return `${m.toString().padStart(2, '0')}:${remS.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`
  }

  // Handle timeline clicking / scrubbing
  const TRACK_HEADER_WIDTH = 160

  const handleTimelineMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!scrollAreaRef.current) return
    const rect = scrollAreaRef.current.getBoundingClientRect()
    const scrollLeft = scrollAreaRef.current.scrollLeft
    const clickX = e.clientX - rect.left + scrollLeft - TRACK_HEADER_WIDTH
    const targetTime = Math.max(0, Math.min(duration, clickX / pxPerSec))
    onSeek(targetTime)
    setIsScrubbing(true)
  }

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!scrollAreaRef.current) return
      const rect = scrollAreaRef.current.getBoundingClientRect()
      const scrollLeft = scrollAreaRef.current.scrollLeft
      const posX = e.clientX - rect.left + scrollLeft - TRACK_HEADER_WIDTH
      const targetTime = Math.max(0, Math.min(duration, posX / pxPerSec))

      setHoverTime(targetTime)

      if (isScrubbing) {
        onSeek(targetTime)
      }
    },
    [duration, isScrubbing, onSeek, pxPerSec]
  )

  const handleMouseUp = useCallback(() => {
    setIsScrubbing(false)
  }, [])

  useEffect(() => {
    if (isScrubbing) {
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isScrubbing, handleMouseMove, handleMouseUp])

  // Split current cue at playhead position
  const handleSplitAtPlayhead = () => {
    const activeCue = cues.find(
      (c) => currentTime >= c.start && currentTime < c.end
    )
    if (activeCue && currentTime > activeCue.start + 0.1 && currentTime < activeCue.end - 0.1) {
      onSplitCue(activeCue.id, currentTime)
    }
  }

  // Blade click directly on a cue
  const handleCueClick = (cue: SubtitleCue, e: React.MouseEvent) => {
    e.stopPropagation()
    if (activeTool === 'blade') {
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
      const clickRatio = (e.clientX - rect.left) / rect.width
      const cutTime = cue.start + (cue.end - cue.start) * clickRatio
      if (cutTime > cue.start + 0.1 && cutTime < cue.end - 0.1) {
        onSplitCue(cue.id, cutTime)
      }
    } else {
      onSelectCue(cue.id)
      onSeek(cue.start)
    }
  }

  // Generate ruler tick marks every 1s / 5s / 10s
  const rulerInterval = zoom > 1.8 ? 1 : zoom > 0.8 ? 2 : 5
  const ticksCount = Math.ceil(duration / rulerInterval)
  const ticks = Array.from({ length: ticksCount + 1 }, (_, i) => i * rulerInterval)

  return (
    <div
      ref={timelineContainerRef}
      className="flex h-[360px] w-full flex-col border-t border-zinc-800 bg-[#121214] text-xs select-none relative"
    >
      {/* 1. TIMELINE TOOLBAR */}
      <div className="flex items-center justify-between border-b border-zinc-800/90 bg-[#18181b] px-3 py-1.5 shrink-0">
        {/* Left Tools */}
        <div className="flex items-center gap-1.5">
          {/* Tool mode selector */}
          <div className="flex items-center rounded border border-zinc-700/80 bg-zinc-900/80 p-0.5">
            <button
              onClick={() => setActiveTool('select')}
              title="選取工具 (A - Select Tool)"
              className={`flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium transition ${
                activeTool === 'select'
                  ? 'bg-primary text-white shadow'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <MousePointer size={12} />
              <span>選取 (A)</span>
            </button>
            <button
              onClick={() => setActiveTool('blade')}
              title="刀片切割工具 (B - Blade Tool)"
              className={`flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium transition ${
                activeTool === 'blade'
                  ? 'bg-amber-600 text-white shadow'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Scissors size={12} />
              <span>刀片 (B)</span>
            </button>
          </div>

          {/* Quick Split at Playhead */}
          <button
            onClick={handleSplitAtPlayhead}
            title="在目前播放指針位置精準分割 (C - Split at Playhead)"
            className="flex items-center gap-1 rounded border border-zinc-700 bg-zinc-800/80 px-2.5 py-1 text-[11px] text-zinc-300 hover:bg-zinc-700 hover:text-white transition"
          >
            <Split size={12} className="text-amber-400" />
            <span>分割當前 (C)</span>
          </button>

          {/* Delete selected */}
          <button
            onClick={() => selectedCueId && onDeleteCue(selectedCueId)}
            disabled={!selectedCueId}
            title="刪除選取片段 (Delete / Ripple Delete)"
            className="flex items-center gap-1 rounded border border-zinc-700/60 bg-zinc-800/40 px-2.5 py-1 text-[11px] text-zinc-400 hover:border-red-500/50 hover:bg-red-500/10 hover:text-red-400 transition disabled:opacity-30"
          >
            <Trash2 size={12} />
            <span>刪除</span>
          </button>

          {/* Snapping */}
          <button
            onClick={() => setSnapping((v) => !v)}
            title="磁性吸附 (N - Magnetic Snapping)"
            className={`flex items-center gap-1 rounded px-2 py-1 text-[11px] transition ${
              snapping
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Magnet size={12} />
            <span>吸附 (N)</span>
          </button>
        </div>

        {/* Center: Playhead Timecode Display */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="rounded bg-black/80 px-2 py-0.5 text-cyan-400 font-bold border border-cyan-500/30">
            {formatTimecode(currentTime)}
          </span>
          <span className="text-zinc-500">/</span>
          <span className="text-zinc-400">{formatTimecode(duration)}</span>
        </div>

        {/* Right: Zoom Slider */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom((z) => Math.max(0.4, z - 0.2))}
            title="縮小時間軸 (-)"
            className="text-zinc-400 hover:text-zinc-200"
          >
            <ZoomOut size={13} />
          </button>
          <input
            type="range"
            min={0.4}
            max={3.0}
            step={0.1}
            value={zoom}
            onChange={(e) => setZoom(parseFloat(e.target.value))}
            className="w-20 accent-primary h-1 bg-zinc-700 rounded-lg cursor-pointer"
          />
          <button
            onClick={() => setZoom((z) => Math.min(3.0, z + 0.2))}
            title="放大時間軸 (+)"
            className="text-zinc-400 hover:text-zinc-200"
          >
            <ZoomIn size={13} />
          </button>
          <button
            onClick={() => setZoom(1.0)}
            title="重設為 100%"
            className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400 hover:text-zinc-200"
          >
            <Maximize2 size={11} />
          </button>
        </div>
      </div>

      {/* 2. MULTI-TRACK TIMELINE SCROLL AREA */}
      <div
        ref={scrollAreaRef}
        onMouseDown={handleTimelineMouseDown}
        className={`flex-1 overflow-x-auto overflow-y-hidden relative select-none ${
          activeTool === 'blade' ? 'cursor-crosshair' : 'cursor-default'
        }`}
      >
        <div
          style={{ width: `${totalTimelineWidth}px` }}
          className="relative min-h-full flex flex-col"
        >
          {/* TRACK HEADERS (Sticky Left) */}
          <div
            style={{ width: `${TRACK_HEADER_WIDTH}px` }}
            className="sticky left-0 z-30 shrink-0 flex flex-col border-r border-zinc-800 bg-[#161619] shadow-lg select-none"
          >
            {/* Ruler Header */}
            <div className="h-6 border-b border-zinc-800 flex items-center px-2 font-mono text-[9px] text-zinc-500">
              TIME
            </div>
            {/* V2 Header */}
            <div className="h-10 border-b border-zinc-800/80 flex items-center justify-between px-2 text-[10px] font-bold text-indigo-400 bg-indigo-950/20">
              <div className="flex items-center gap-1">
                <Type size={11} />
                <span>V2 字幕</span>
              </div>
              <span className="text-[9px] font-normal text-indigo-300/70">{cues.length} 句</span>
            </div>
            {/* V1 Header */}
            <div className="h-14 border-b border-zinc-800/80 flex items-center justify-between px-2 text-[10px] font-bold text-sky-400 bg-sky-950/20">
              <div className="flex items-center gap-1">
                <Film size={11} />
                <span>V1 視訊</span>
              </div>
              <span className="text-[9px] font-normal text-sky-300/70">{scenes.length} 幕</span>
            </div>
            {/* A1 Header: Voice Track Controls */}
            <div className="h-20 border-b border-zinc-800/80 flex flex-col justify-between p-2 text-[10px] font-bold bg-emerald-950/25">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 text-emerald-400">
                  {voiceMuted ? <VolumeX size={12} className="text-red-400" /> : <Volume2 size={12} />}
                  <span>A1 語音</span>
                </div>
                <span className="font-mono text-[9px] text-emerald-300/90">{Math.round(voiceVolume ?? 100)}%</span>
              </div>
              <div className="flex items-center gap-1">
                {/* Denoise toggle */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleDenoise?.()
                  }}
                  className={`h-4 px-1 rounded text-[8px] font-bold transition ${
                    denoiseLevel && denoiseLevel !== 'off'
                      ? 'bg-emerald-600 text-white shadow'
                      : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300'
                  }`}
                  title={`人聲去噪濾波：${denoiseLevel ?? '中度'} (點擊切換)`}
                >
                  NR
                </button>
                {/* Anti-Clip Limiter toggle */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleAntiClip?.()
                  }}
                  className={`h-4 px-1 rounded text-[8px] font-bold transition ${
                    antiClip
                      ? 'bg-blue-600 text-white shadow'
                      : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300'
                  }`}
                  title={antiClip ? '防爆音限幅器已開啟 (Soft-knee Limiter)' : '防爆音限幅器已關閉'}
                >
                  LIM
                </button>
                {/* Mute toggle button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleVoiceMute?.()
                  }}
                  className={`h-4 w-4 rounded text-[9px] font-black transition ${
                    voiceMuted
                      ? 'bg-red-600 text-white shadow ring-1 ring-red-400'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={voiceMuted ? '取消靜音 (Mute)' : '將語音軌靜音 (Mute)'}
                >
                  M
                </button>
                {/* Solo toggle button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleVoiceSolo?.()
                  }}
                  className={`h-4 w-4 rounded text-[9px] font-black transition ${
                    voiceSolo
                      ? 'bg-amber-500 text-black font-bold shadow'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={voiceSolo ? '取消獨奏 (Solo)' : '獨奏此語音軌 (Solo)'}
                >
                  S
                </button>
              </div>
            </div>
            {/* A2 Header: BGM Track Controls */}
            <div className="h-16 flex items-center justify-between px-2 text-[10px] font-bold bg-amber-950/25">
              <div className="flex items-center gap-1 text-amber-400">
                {bgmMuted ? <VolumeX size={12} className="text-red-400" /> : <Music size={12} />}
                <span>A2 配樂</span>
              </div>
              <div className="flex items-center gap-1">
                {/* Ducking toggle */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleAudioDucking?.()
                  }}
                  className={`h-4 px-1 rounded text-[8px] font-bold transition ${
                    audioDucking
                      ? 'bg-cyan-600 text-white shadow'
                      : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300'
                  }`}
                  title={audioDucking ? '自動人聲閃避已開啟 (說話時降至 30%)' : '自動人聲閃避已關閉'}
                >
                  D
                </button>
                {/* Mute toggle */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleBgmMute?.()
                  }}
                  className={`h-4 w-4 rounded text-[9px] font-black transition ${
                    bgmMuted
                      ? 'bg-red-600 text-white shadow ring-1 ring-red-400'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={bgmMuted ? '取消配樂靜音' : '將配樂靜音'}
                >
                  M
                </button>
                {/* Solo toggle */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleBgmSolo?.()
                  }}
                  className={`h-4 w-4 rounded text-[9px] font-black transition ${
                    bgmSolo
                      ? 'bg-amber-500 text-black font-bold shadow'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={bgmSolo ? '取消獨奏' : '獨奏此配樂軌'}
                >
                  S
                </button>
                <span className="font-mono text-[8px] text-amber-300/80">{Math.round(bgmVolume ?? 20)}%</span>
              </div>
            </div>
          </div>

          {/* TRACKS CONTENT CANVAS (Offset by TRACK_HEADER_WIDTH) */}
          <div
            style={{ left: `${TRACK_HEADER_WIDTH}px` }}
            className="absolute inset-0 flex flex-col pointer-events-auto"
          >
            {/* 2.1 TIME RULER */}
            <div className="relative h-6 border-b border-zinc-800 bg-[#141416] overflow-hidden">
              {ticks.map((tSec) => {
                const posX = tSec * pxPerSec
                return (
                  <div
                    key={tSec}
                    style={{ left: `${posX}px` }}
                    className="absolute top-0 bottom-0 flex flex-col items-start border-l border-zinc-700/50 pl-1"
                  >
                    <span className="font-mono text-[9px] text-zinc-400">
                      {formatDuration(tSec)}
                    </span>
                  </div>
                )
              })}
            </div>

            {/* 2.2 V2 TRACK: SUBTITLES & TITLES */}
            <div className="relative h-10 border-b border-zinc-800/80 bg-[#141418] flex items-center">
              {cues.map((cue) => {
                const left = cue.start * pxPerSec
                const width = Math.max(16, (cue.end - cue.start) * pxPerSec)
                const isSelected = selectedCueId === cue.id

                return (
                  <div
                    key={cue.id}
                    onClick={(e) => handleCueClick(cue, e)}
                    style={{ left: `${left}px`, width: `${width}px` }}
                    className={`absolute h-7 rounded border px-1.5 flex items-center text-[10px] font-medium truncate cursor-pointer transition shadow-sm ${
                      isSelected
                        ? 'border-indigo-400 bg-indigo-600/60 text-white ring-2 ring-indigo-400/80 z-10'
                        : 'border-indigo-800/80 bg-indigo-900/40 text-indigo-200 hover:bg-indigo-800/50'
                    }`}
                    title={`#${cue.id}: ${cue.text} (${cue.start.toFixed(2)}s ~ ${cue.end.toFixed(2)}s)`}
                  >
                    <span className="truncate">{cue.text}</span>
                  </div>
                )
              })}
            </div>

            {/* 2.3 V1 TRACK: PRIMARY STORYLINE (VIDEO CLIPS) */}
            <div className="relative h-14 border-b border-zinc-800/80 bg-[#121418] flex items-center">
              {scenes.length > 0 ? (
                scenes.map((scene, idx) => {
                  const startSec = scenes
                    .slice(0, idx)
                    .reduce((acc, s) => acc + (s.duration || 5), 0)
                  const sceneDur = scene.duration || 5
                  const left = startSec * pxPerSec
                  const width = Math.max(24, sceneDur * pxPerSec)

                  return (
                    <div
                      key={scene.id || idx}
                      onClick={() => onSeek(startSec)}
                      style={{ left: `${left}px`, width: `${width}px` }}
                      className="absolute h-12 rounded border border-sky-800/70 bg-gradient-to-r from-sky-950/80 to-blue-950/70 flex items-center gap-1.5 px-2 overflow-hidden shadow cursor-pointer hover:border-sky-400 transition"
                    >
                      {scene.image_url && (
                        <img
                          src={scene.image_url}
                          alt={`Scene ${idx + 1}`}
                          className="h-8 w-12 shrink-0 rounded object-cover border border-sky-500/30"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1 text-[10px] font-bold text-sky-300">
                          <span>S{idx + 1}</span>
                          <span className="font-normal text-zinc-400 truncate">
                            {sceneDur.toFixed(1)}s
                          </span>
                        </div>
                        <p className="truncate text-[9px] text-zinc-400 leading-none">
                          {scene.narration || `第 ${idx + 1} 幕畫面`}
                        </p>
                      </div>
                    </div>
                  )
                })
              ) : (
                <div
                  style={{ left: 0, width: `${duration * pxPerSec}px` }}
                  className="absolute h-12 rounded border border-sky-800/70 bg-sky-950/40 flex items-center px-3 text-[11px] text-sky-300"
                >
                  <Film size={14} className="mr-2 text-sky-400 shrink-0" />
                  <span>主要視訊軌道 (Primary Storyline: {duration.toFixed(1)}s)</span>
                </div>
              )}
            </div>

            {/* 2.4 A1 TRACK: INDIVIDUAL VOICE DIALOGUE CLIPS (AUTHENTIC FCP SOLID WAVEFORM) */}
            <div className={`relative h-20 border-b border-zinc-800/80 bg-[#10151f] flex items-center transition ${
              voiceMuted ? 'opacity-40 grayscale' : ''
            }`}>
              {cues.map((cue, idx) => {
                const left = cue.start * pxPerSec
                const width = Math.max(36, (cue.end - cue.start) * pxPerSec)
                const isSelected = selectedCueId === cue.id
                const cuePoints = Math.max(40, Math.min(240, Math.floor(((cue.end - cue.start) * pxPerSec) / 1.5)))
                const peaks = extractCuePeaks(voiceAudioData, duration, cue.start, cue.end, cuePoints, {
                  gain: (voiceVolume ?? 100) / 100,
                  denoiseLevel,
                  antiClip,
                })

                return (
                  <div
                    key={cue.id}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectCue(cue.id)
                      onSeek(cue.start)
                    }}
                    style={{ left: `${left}px`, width: `${width}px` }}
                    className={`group absolute h-[72px] rounded border flex flex-col justify-between overflow-hidden cursor-pointer transition shadow ${
                      isSelected
                        ? 'border-blue-400 bg-[#1e2e42] text-white ring-2 ring-blue-400 z-20'
                        : 'border-[#2d4663] bg-[#1a2636] text-blue-200 hover:border-blue-400 hover:bg-[#202f42]'
                    }`}
                    title={`#${cue.id}: ${cue.text} (${cue.start.toFixed(2)}s ~ ${cue.end.toFixed(2)}s)`}
                  >
                    {/* Voice Clip Top Label & Text Info */}
                    <div className="flex items-center justify-between text-[9px] font-mono leading-tight px-1.5 pt-1 z-10 pointer-events-none">
                      <span className="font-bold text-sky-300">A1-{idx + 1}</span>
                      <span className="truncate max-w-[65%] text-[9px] font-normal text-zinc-200 px-1">{cue.text}</span>
                      <span className="text-[8px] text-zinc-400 shrink-0">{(cue.end - cue.start).toFixed(1)}s</span>
                    </div>

                    {/* Authentic Final Cut Pro Continuous Solid Filled Silhouette Waveform */}
                    <div className="w-full h-[50px] overflow-visible relative">
                      <FcpClipWaveform
                        peaks={peaks}
                        width={width}
                        height={50}
                        volume={voiceVolume ?? 100}
                        onChangeVolume={onChangeVoiceVolume}
                        color="voice"
                        isSelected={isSelected}
                      />
                    </div>

                    {/* Quick TTS Regenerate / Preview button on hover */}
                    {onSynthesizeCue && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onSynthesizeCue(cue.id)
                        }}
                        className="absolute top-1 right-1 h-5 w-5 grid place-items-center rounded bg-blue-500 text-white shadow opacity-0 group-hover:opacity-100 transition hover:scale-110 z-20"
                        title="試聽或重新生成此句配音"
                      >
                        <Volume2 size={10} />
                      </button>
                    )}
                  </div>
                )
              })}
            </div>

            {/* 2.5 A2 TRACK: BACKGROUND MUSIC (AUTHENTIC FCP CONTINUOUS SOLID WAVEFORM) */}
            <div className={`relative h-16 bg-[#14120e] flex items-center transition ${
              bgmMuted ? 'opacity-40 grayscale' : ''
            }`}>
              {activeBgmName ? (
                <div
                  onClick={() => onOpenBgmSelector?.()}
                  style={{ left: 0, width: `${duration * pxPerSec}px` }}
                  className="group absolute h-[58px] rounded border border-amber-800/80 bg-[#241c12] flex flex-col justify-between overflow-hidden cursor-pointer hover:border-amber-400 transition"
                  title={`背景音樂: ${activeBgmName} (點擊切換配樂)`}
                >
                  <div className="flex items-center justify-between text-[9px] px-2 pt-1 z-10 pointer-events-none">
                    <span className="flex items-center gap-1 font-bold text-amber-300">
                      <Music size={11} />
                      {activeBgmName}
                    </span>
                    <span className="rounded bg-amber-500/20 px-1 py-0.2 font-mono text-[8px] text-amber-400">
                      循環播放
                    </span>
                  </div>

                  {/* Authentic Final Cut Pro Continuous Solid Filled Silhouette Waveform for BGM */}
                  <div className="w-full h-[38px] overflow-visible relative">
                    {(() => {
                      const bgmSamplePoints = Math.max(100, Math.floor((duration * pxPerSec) / 2))
                      const peaks = extractTimelinePeaks(bgmAudioData, duration, bgmSamplePoints, {
                        gain: (bgmVolume ?? 20) / 100,
                        antiClip,
                      })
                      return (
                        <FcpClipWaveform
                          peaks={peaks}
                          width={duration * pxPerSec}
                          height={38}
                          volume={bgmVolume ?? 20}
                          onChangeVolume={onChangeBgmVolume}
                          color="bgm"
                        />
                      )
                    })()}
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => onOpenBgmSelector?.()}
                  style={{ left: 0, width: `${Math.max(300, duration * pxPerSec)}px` }}
                  className="absolute h-10 rounded border border-dashed border-zinc-700 bg-zinc-900/40 flex items-center justify-center gap-2 text-zinc-500 hover:border-amber-500/70 hover:text-amber-400 hover:bg-amber-950/20 cursor-pointer transition text-[11px]"
                >
                  <Plus size={13} />
                  <span>+ 點選此處為影片添加背景音樂 (A2 配樂軌)</span>
                </div>
              )}
            </div>
          </div>

          {/* 3. RED / YELLOW FCP PLAYHEAD LINE (Full Height) */}
          <div
            style={{
              left: `${TRACK_HEADER_WIDTH + currentTime * pxPerSec}px`,
            }}
            className="pointer-events-none absolute top-0 bottom-0 z-40 w-0.5 bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.9)]"
          >
            {/* Playhead Handle at Top Ruler */}
            <div className="absolute -top-1 left-1/2 -translate-x-1/2 h-3.5 w-3.5 rotate-45 rounded-sm bg-red-500 border border-white shadow" />
          </div>

          {/* 4. HOVER BLADE RAZOR INDICATOR */}
          {activeTool === 'blade' && hoverTime !== null && (
            <div
              style={{
                left: `${TRACK_HEADER_WIDTH + hoverTime * pxPerSec}px`,
              }}
              className="pointer-events-none absolute top-6 bottom-0 z-30 w-px border-l border-dashed border-amber-400/90"
            >
              <div className="absolute top-1 left-1/2 -translate-x-1/2 rounded bg-amber-500 px-1 py-0.5 text-[9px] font-mono font-bold text-black shadow">
                ✂ CUT
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
