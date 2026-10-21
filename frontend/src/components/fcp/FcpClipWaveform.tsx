import React, { useState, useRef, useMemo, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { buildFcpWaveformPath, gainToDb } from '../../utils/audioWaveform'

interface FcpClipWaveformProps {
  peaks: number[]
  width: number
  height: number
  volume: number // 0 to 200 (%)
  onChangeVolume?: (newVolume: number) => void
  color?: 'voice' | 'bgm'
  isSelected?: boolean
  label?: string
  showVolumeLine?: boolean
}

/**
 * Authentic Final Cut Pro audio waveform component.
 * Renders a continuous solid-filled silhouette waveform, horizontal volume control line,
 * interactive dB dragging badge (-2.0 dB), and peak overload clipping warning icons (!).
 */
export default function FcpClipWaveform({
  peaks,
  width,
  height,
  volume,
  onChangeVolume,
  color = 'voice',
  isSelected = false,
  showVolumeLine = true,
}: FcpClipWaveformProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const dragStartYRef = useRef<number>(0)
  const dragStartVolRef = useRef<number>(volume)

  // Waveform SVG Path & Clipping Status
  const { pathD, strokeD, hasClipping } = useMemo(() => {
    return buildFcpWaveformPath(peaks, width, height)
  }, [peaks, width, height])

  // Volume gain ratio (1.0 = 100% / 0 dB)
  const gain = (volume ?? 100) / 100
  const currentDb = gainToDb(gain)

  // In FCP, 0 dB (100% volume) is positioned at ~65% from bottom (35% from top)
  // 200% volume (+6dB) reaches near the top (10% from top)
  // 0% volume (-inf dB) is at the bottom (100% from top)
  const volumeLineYPercent = useMemo(() => {
    if (volume <= 100) {
      return 100 - (volume / 100) * 65
    } else {
      return 35 - ((volume - 100) / 100) * 27
    }
  }, [volume])

  // Dragging volume line directly on the waveform
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      e.preventDefault()
      setIsDragging(true)
      dragStartYRef.current = e.clientY
      dragStartVolRef.current = volume

      const handleMouseMove = (moveEvent: MouseEvent) => {
        const deltaY = dragStartYRef.current - moveEvent.clientY // Up is positive
        const sensitivity = moveEvent.shiftKey ? 0.2 : 0.8 // Hold Shift for precision
        const newVol = Math.max(0, Math.min(200, Math.round(dragStartVolRef.current + deltaY * sensitivity)))
        onChangeVolume?.(newVol)
      }

      const handleMouseUp = () => {
        setIsDragging(false)
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }

      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)
    },
    [volume, onChangeVolume]
  )

  // Colors strictly aligned with Final Cut Pro UI
  const fillColor =
    color === 'voice'
      ? isSelected
        ? '#60a5fa' // Bright FCP Selection Blue
        : '#4a75a4' // Authentic FCP Steel Blue Dialogue
      : '#b58334' // Authentic FCP Golden Amber Music

  const contourStroke =
    color === 'voice'
      ? isSelected
        ? '#93c5fd'
        : '#7cb0d8'
      : '#fbbf24'

  const baselineStroke = color === 'voice' ? 'rgba(96, 165, 250, 0.4)' : 'rgba(217, 119, 6, 0.4)'

  return (
    <div
      ref={containerRef}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{ width: `${width}px`, height: `${height}px` }}
      className="relative overflow-visible select-none"
    >
      {/* 1. Continuous Solid Filled Waveform Silhouette with crisp top contour */}
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="absolute inset-0 pointer-events-none overflow-hidden"
      >
        <defs>
          <linearGradient id={`fcp-grad-${color}-${isSelected}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={fillColor} stopOpacity={0.95} />
            <stop offset="100%" stopColor={fillColor} stopOpacity={0.65} />
          </linearGradient>
        </defs>
        {pathD && (
          <path
            d={pathD}
            fill={`url(#fcp-grad-${color}-${isSelected})`}
            className="transition-all duration-75"
          />
        )}
        {strokeD && (
          <path
            d={strokeD}
            fill="none"
            stroke={contourStroke}
            strokeWidth={1.2}
            className="transition-all duration-75"
          />
        )}
      </svg>

      {/* 2. Audio Baseline */}
      <div
        style={{ borderTop: `1px solid ${baselineStroke}` }}
        className="absolute bottom-0 inset-x-0 pointer-events-none"
      />

      {/* 3. Authentic Final Cut Pro Horizontal Volume Control Line */}
      {showVolumeLine && (
        <div
          style={{ top: `${volumeLineYPercent}%` }}
          onMouseDown={handleMouseDown}
          className="group/vol absolute inset-x-0 h-5 -translate-y-1/2 flex items-center cursor-ns-resize z-30"
        >
          {/* Subtle horizontal volume line */}
          <div
            className={`w-full h-[1.5px] transition-colors ${
              isDragging || isHovered
                ? 'bg-white shadow-[0_0_5px_rgba(255,255,255,0.95)]'
                : 'bg-white/50 group-hover/vol:bg-white/80'
            }`}
          />

          {/* Left and Right FCP Volume Line Warning / Sync Badges (!) */}
          <div
            className={`absolute left-1 flex items-center justify-center w-3 h-3 rounded-full border text-[7px] font-bold pointer-events-none z-10 transition ${
              hasClipping || volume > 115
                ? 'bg-rose-950/90 border-rose-500 text-rose-300 animate-pulse'
                : 'bg-slate-900/80 border-slate-500/70 text-slate-300'
            }`}
            title={hasClipping ? '音訊過載削波警示' : 'FCP 音訊聲道基準標記'}
          >
            !
          </div>
          <div
            className={`absolute right-1 flex items-center justify-center w-3 h-3 rounded-full border text-[7px] font-bold pointer-events-none z-10 transition ${
              hasClipping || volume > 115
                ? 'bg-rose-950/90 border-rose-500 text-rose-300 animate-pulse'
                : 'bg-slate-900/80 border-slate-500/70 text-slate-300'
            }`}
            title={hasClipping ? '音訊過載削波警示' : 'FCP 音訊聲道基準標記'}
          >
            !
          </div>

          {/* Center Handle: FCP Up & Down Adjustment Arrows (▲ / ▼) */}
          <div className="absolute left-1/2 -translate-x-1/2 flex flex-col items-center justify-center pointer-events-none">
            <span
              className={`text-[8px] leading-none transition-transform ${
                isDragging ? 'text-white scale-125' : 'text-white/80 group-hover/vol:text-white'
              }`}
            >
              ▲
            </span>
            <span
              className={`text-[8px] leading-none transition-transform -mt-0.5 ${
                isDragging ? 'text-white scale-125' : 'text-white/80 group-hover/vol:text-white'
              }`}
            >
              ▼
            </span>
          </div>

          {/* 4. Iconic Final Cut Pro Floating dB Badge Tooltip with Beak Pointer */}
          {(isHovered || isDragging) && (
            <div className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 rounded bg-black/95 px-2.5 py-0.5 font-mono text-[11px] font-bold text-white shadow-2xl border border-white/20 whitespace-nowrap pointer-events-none z-50 flex flex-col items-center">
              <span>{currentDb}</span>
              <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-0 h-0 border-x-4 border-x-transparent border-t-4 border-t-black/95" />
            </div>
          )}
        </div>
      )}

      {/* 5. Peak Overload Clipping Alert Badge at top edge when severely overdriven */}
      {(hasClipping || volume > 120) && (
        <div
          className="absolute top-0.5 left-1/2 -translate-x-1/2 flex items-center gap-1 text-rose-400 bg-black/90 px-1.5 py-0.2 rounded border border-rose-500/60 text-[9px] font-bold pointer-events-none z-10 shadow"
          title="音訊過載削波警示 (Clipping Warning)"
        >
          <AlertCircle size={10} className="text-rose-400 fill-rose-500/30" />
          <span>PEAK OVERLOAD</span>
        </div>
      )}
    </div>
  )
}
