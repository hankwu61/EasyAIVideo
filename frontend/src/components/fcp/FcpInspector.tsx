import {
  RotateCcw,
  Sliders,
  Sun,
  Volume2,
  Zap,
  Music,
  Mic,
  Sparkles,
  Shield,
  Activity,
} from 'lucide-react'
import type { SubtitleCue } from '../../types'

export interface VideoAdjustments {
  scale: number // 100% default
  rotation: number // 0 deg
  brightness: number // 100%
  contrast: number // 100%
  saturation: number // 100%
  temperature: number // 0 (-50 to +50)
  volume: number // 100%
  muted: boolean
}

interface FcpInspectorProps {
  selectedCue: SubtitleCue | null
  adjustments: VideoAdjustments
  onChangeAdjustments: (adjustments: VideoAdjustments) => void
  playbackRate: number
  onChangePlaybackRate: (rate: number) => void
  duration: number
  currentTime: number
  isPlaying?: boolean

  // Audio Channel controls
  voiceVolume?: number
  onChangeVoiceVolume?: (v: number) => void
  voiceMuted?: boolean
  onToggleVoiceMute?: () => void
  voiceSolo?: boolean
  onToggleVoiceSolo?: () => void
  denoiseLevel?: 'off' | 'low' | 'med' | 'high'
  onChangeDenoiseLevel?: (level: 'off' | 'low' | 'med' | 'high') => void
  antiClip?: boolean
  onToggleAntiClip?: () => void

  bgmVolume?: number
  onChangeBgmVolume?: (v: number) => void
  bgmMuted?: boolean
  onToggleBgmMute?: () => void
  bgmSolo?: boolean
  onToggleBgmSolo?: () => void
  audioDucking?: boolean
  onToggleAudioDucking?: () => void
  activeBgmName?: string | null
  onOpenBgmSelector?: () => void
  onSynthesizeCue?: (cueId: number) => void
}

export default function FcpInspector({
  selectedCue,
  adjustments,
  onChangeAdjustments,
  playbackRate,
  onChangePlaybackRate,
  duration,
  currentTime,
  isPlaying = false,
  voiceVolume = 100,
  onChangeVoiceVolume,
  voiceMuted = false,
  onToggleVoiceMute,
  voiceSolo = false,
  onToggleVoiceSolo,
  denoiseLevel = 'med',
  onChangeDenoiseLevel,
  antiClip = true,
  onToggleAntiClip,
  bgmVolume = 20,
  onChangeBgmVolume,
  bgmMuted = false,
  onToggleBgmMute,
  bgmSolo = false,
  onToggleBgmSolo,
  audioDucking = true,
  onToggleAudioDucking,
  activeBgmName,
  onOpenBgmSelector,
  onSynthesizeCue,
}: FcpInspectorProps) {
  const update = (partial: Partial<VideoAdjustments>) => {
    onChangeAdjustments({ ...adjustments, ...partial })
  }

  const resetAll = () => {
    onChangeAdjustments({
      scale: 100,
      rotation: 0,
      brightness: 100,
      contrast: 100,
      saturation: 100,
      temperature: 0,
      volume: 100,
      muted: false,
    })
  }

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-l border-zinc-800 bg-[#161618] text-xs select-none">
      {/* Inspector Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 bg-[#121214] px-3 py-2.5">
        <div className="flex items-center gap-1.5 font-semibold text-zinc-200">
          <Sliders size={13} className="text-primary" />
          <span>FCP 檢驗器 (Inspector)</span>
        </div>
        <button
          onClick={resetAll}
          title="重設所有調整值"
          className="flex items-center gap-1 text-[10px] text-zinc-400 hover:text-zinc-200 transition"
        >
          <RotateCcw size={11} />
          <span>重設</span>
        </button>
      </div>

      {/* Content scroll area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Selected Clip / Subtitle Context */}
        <div className="rounded border border-zinc-800 bg-zinc-900/60 p-2.5 space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-medium text-zinc-300">選取項目資訊</span>
            <span className="font-mono text-[10px] text-primary">
              {currentTime.toFixed(2)}s / {duration.toFixed(2)}s
            </span>
          </div>
          {selectedCue ? (
            <div className="space-y-1 text-[11px] text-zinc-400">
              <div className="flex items-center justify-between">
                <span>字幕區段: #{selectedCue.id}</span>
                <span className="font-mono text-zinc-300">
                  {selectedCue.start.toFixed(2)}s - {selectedCue.end.toFixed(2)}s
                </span>
              </div>
              <p className="line-clamp-2 rounded bg-black/40 p-1.5 text-zinc-200 font-sans leading-tight">
                {selectedCue.text}
              </p>
            </div>
          ) : (
            <p className="text-[10px] text-zinc-500">主故事線全片片段（未選取特定字幕條）</p>
          )}
        </div>

        {/* 1. Transform / Layout */}
        <div className="space-y-2.5">
          <label className="font-semibold text-zinc-300 flex items-center gap-1.5">
            <Zap size={12} className="text-amber-400" />
            畫面變形與比例 (Transform)
          </label>

          {/* Scale */}
          <div>
            <div className="flex items-center justify-between mb-1 text-[11px] text-zinc-400">
              <span>畫面縮放 (Scale)</span>
              <span className="font-mono text-primary">{adjustments.scale}%</span>
            </div>
            <input
              type="range"
              min={50}
              max={150}
              value={adjustments.scale}
              onChange={(e) => update({ scale: parseInt(e.target.value, 10) })}
              className="w-full accent-primary h-1 bg-zinc-700 rounded-lg cursor-pointer"
            />
          </div>

          {/* Rotation */}
          <div>
            <div className="flex items-center justify-between mb-1 text-[11px] text-zinc-400">
              <span>旋轉角度 (Rotation)</span>
              <span className="font-mono text-primary">{adjustments.rotation}°</span>
            </div>
            <input
              type="range"
              min={-45}
              max={45}
              value={adjustments.rotation}
              onChange={(e) => update({ rotation: parseInt(e.target.value, 10) })}
              className="w-full accent-primary h-1 bg-zinc-700 rounded-lg cursor-pointer"
            />
          </div>
        </div>

        {/* 2. Color Grading / Adjustments */}
        <div className="space-y-2.5 border-t border-zinc-800/80 pt-3">
          <label className="font-semibold text-zinc-300 flex items-center gap-1.5">
            <Sun size={12} className="text-cyan-400" />
            色彩與曝光調節 (Color Board)
          </label>

          {/* Brightness */}
          <div>
            <div className="flex items-center justify-between mb-1 text-[11px] text-zinc-400">
              <span>曝光亮度 (Exposure)</span>
              <span className="font-mono text-primary">{adjustments.brightness}%</span>
            </div>
            <input
              type="range"
              min={50}
              max={150}
              value={adjustments.brightness}
              onChange={(e) => update({ brightness: parseInt(e.target.value, 10) })}
              className="w-full accent-primary h-1 bg-zinc-700 rounded-lg cursor-pointer"
            />
          </div>

          {/* Contrast */}
          <div>
            <div className="flex items-center justify-between mb-1 text-[11px] text-zinc-400">
              <span>對比度 (Contrast)</span>
              <span className="font-mono text-primary">{adjustments.contrast}%</span>
            </div>
            <input
              type="range"
              min={50}
              max={150}
              value={adjustments.contrast}
              onChange={(e) => update({ contrast: parseInt(e.target.value, 10) })}
              className="w-full accent-primary h-1 bg-zinc-700 rounded-lg cursor-pointer"
            />
          </div>

          {/* Saturation */}
          <div>
            <div className="flex items-center justify-between mb-1 text-[11px] text-zinc-400">
              <span>色彩飽和度 (Saturation)</span>
              <span className="font-mono text-primary">{adjustments.saturation}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={200}
              value={adjustments.saturation}
              onChange={(e) => update({ saturation: parseInt(e.target.value, 10) })}
              className="w-full accent-primary h-1 bg-zinc-700 rounded-lg cursor-pointer"
            />
          </div>

          {/* Color Temperature */}
          <div>
            <div className="flex items-center justify-between mb-1 text-[11px] text-zinc-400">
              <span>色溫 (冷調 ↔ 暖調)</span>
              <span className="font-mono text-primary">
                {adjustments.temperature > 0 ? `+${adjustments.temperature}` : adjustments.temperature}
              </span>
            </div>
            <input
              type="range"
              min={-50}
              max={50}
              value={adjustments.temperature}
              onChange={(e) => update({ temperature: parseInt(e.target.value, 10) })}
              className="w-full accent-amber-500 h-1 bg-zinc-700 rounded-lg cursor-pointer"
            />
          </div>
        </div>

        {/* 3. Pro Dual-Channel Audio Mixer & Speed */}
        <div className="space-y-3 border-t border-zinc-800/80 pt-3">
          <div className="flex items-center justify-between">
            <label className="font-semibold text-zinc-200 flex items-center gap-1.5">
              <Volume2 size={13} className="text-emerald-400" />
              專業雙聲道混音台 (Audio Mixer)
            </label>
            {/* Master Stereo Peak VU Meter */}
            <div className="flex items-center gap-1 bg-black/60 px-1.5 py-0.5 rounded border border-zinc-800 font-mono text-[9px]">
              <span className="text-zinc-500">L</span>
              <div className="flex h-3 w-10 items-center gap-0.5 overflow-hidden rounded-sm bg-zinc-900 px-0.5">
                <div
                  style={{
                    width: isPlaying ? `${Math.min(100, Math.max(15, (voiceVolume / 2) + Math.random() * 30))}%` : '4%',
                  }}
                  className="h-2 rounded-sm bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500 transition-all duration-75"
                />
              </div>
              <span className="text-zinc-500">R</span>
              <div className="flex h-3 w-10 items-center gap-0.5 overflow-hidden rounded-sm bg-zinc-900 px-0.5">
                <div
                  style={{
                    width: isPlaying ? `${Math.min(100, Math.max(10, (bgmVolume) + Math.random() * 25))}%` : '4%',
                  }}
                  className="h-2 rounded-sm bg-gradient-to-r from-emerald-500 via-amber-400 to-red-500 transition-all duration-75"
                />
              </div>
            </div>
          </div>

          {/* CHANNEL 1: A1 Voice Dialogue */}
          <div className="rounded-lg border border-emerald-950/80 bg-gradient-to-b from-emerald-950/20 to-zinc-900/40 p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <div className="grid h-5 w-5 place-items-center rounded bg-emerald-500/20 text-emerald-400">
                  <Mic size={11} />
                </div>
                <span className="font-bold text-emerald-300">A1 人聲語音軌</span>
              </div>
              <div className="flex items-center gap-1">
                {/* Mute Button */}
                <button
                  onClick={onToggleVoiceMute}
                  className={`h-5 w-5 rounded text-[9px] font-black transition ${
                    voiceMuted
                      ? 'bg-red-600 text-white shadow ring-1 ring-red-400'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={voiceMuted ? '取消靜音' : '靜音 A1 語音軌'}
                >
                  M
                </button>
                {/* Solo Button */}
                <button
                  onClick={onToggleVoiceSolo}
                  className={`h-5 w-5 rounded text-[9px] font-black transition ${
                    voiceSolo
                      ? 'bg-amber-500 text-black font-bold shadow'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={voiceSolo ? '取消獨奏' : '獨奏 A1 語音軌'}
                >
                  S
                </button>
                <span className="w-10 text-right font-mono font-bold text-emerald-400">{voiceVolume}%</span>
              </div>
            </div>

            {/* Voice Volume Fader */}
            <div>
              <input
                type="range"
                min={0}
                max={200}
                disabled={voiceMuted}
                value={voiceVolume}
                onChange={(e) => onChangeVoiceVolume?.(parseInt(e.target.value, 10))}
                className="w-full accent-emerald-500 h-1.5 bg-zinc-800 rounded-lg cursor-pointer disabled:opacity-40"
              />
              <div className="flex justify-between text-[9px] text-zinc-500 font-mono mt-0.5">
                <span>0%</span>
                <span className="text-zinc-400">100% (標準)</span>
                <span>200%</span>
              </div>
            </div>

            {/* DSP Filters: Denoise & Anti-Clip Limiter */}
            <div className="rounded bg-black/40 p-2 border border-emerald-900/60 space-y-2">
              {/* Anti-Clip Limiter Switch */}
              <div className="flex items-center justify-between text-[10px]">
                <div className="flex items-center gap-1.5 text-zinc-300">
                  <Shield size={12} className={antiClip ? 'text-blue-400' : 'text-zinc-600'} />
                  <span className="font-semibold">防爆音限幅器 (Anti-Clip)</span>
                </div>
                <button
                  onClick={onToggleAntiClip}
                  className={`px-2 py-0.5 rounded text-[9px] font-bold transition ${
                    antiClip
                      ? 'bg-blue-600 text-white shadow'
                      : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  {antiClip ? '🛡️ 已啟用 (Limiter ON)' : '已關閉 (Off)'}
                </button>
              </div>

              {/* Denoise Level Selector */}
              <div className="space-y-1">
                <div className="flex items-center justify-between text-[10px] text-zinc-400">
                  <span className="flex items-center gap-1">
                    <Activity size={11} className={denoiseLevel !== 'off' ? 'text-emerald-400' : 'text-zinc-600'} />
                    <span>智慧人聲去噪 (Vocal Denoise)</span>
                  </span>
                  <span className="font-mono text-[9px] text-emerald-400">
                    {denoiseLevel === 'off' ? '關閉' : denoiseLevel === 'low' ? '輕度 (80Hz)' : denoiseLevel === 'med' ? '中度 (120Hz)' : '強力 (160Hz)'}
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1">
                  {(['off', 'low', 'med', 'high'] as const).map((lvl) => (
                    <button
                      key={lvl}
                      onClick={() => onChangeDenoiseLevel?.(lvl)}
                      className={`py-0.5 rounded text-[9px] font-medium text-center transition ${
                        denoiseLevel === lvl
                          ? 'bg-emerald-600 text-white shadow'
                          : 'bg-zinc-800/80 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                      }`}
                    >
                      {lvl === 'off' ? 'Off' : lvl === 'low' ? '輕度' : lvl === 'med' ? '中度' : '強力'}
                    </button>
                  ))}
                </div>
              </div>

              <div className="text-[8px] text-zinc-500 italic leading-tight">
                💡 調整音量推桿會即時縮放時間軸波形振幅；高通濾波與門限會自動平順消除環境底噪。
              </div>
            </div>

            {/* Selected Cue Voice Actions */}
            {selectedCue && (
              <div className="rounded bg-black/40 p-1.5 border border-emerald-800/40 text-[10px] space-y-1">
                <div className="text-zinc-400 flex items-center justify-between">
                  <span>選取句 #{selectedCue.id}</span>
                  <span className="font-mono text-emerald-400">{(selectedCue.end - selectedCue.start).toFixed(2)}s</span>
                </div>
                <p className="truncate text-zinc-300 italic">"{selectedCue.text}"</p>
                {onSynthesizeCue && (
                  <button
                    onClick={() => onSynthesizeCue(selectedCue.id)}
                    className="w-full mt-1 flex items-center justify-center gap-1 rounded bg-emerald-500/20 py-1 text-emerald-300 hover:bg-emerald-500 hover:text-black transition font-medium"
                  >
                    <Sparkles size={11} />
                    <span>重新語音合成 (TTS 試聽)</span>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* CHANNEL 2: A2 Background Music */}
          <div className="rounded-lg border border-amber-950/80 bg-gradient-to-b from-amber-950/20 to-zinc-900/40 p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <div className="grid h-5 w-5 place-items-center rounded bg-amber-500/20 text-amber-400">
                  <Music size={11} />
                </div>
                <span className="font-bold text-amber-300">A2 背景配樂軌</span>
              </div>
              <div className="flex items-center gap-1">
                {/* Ducking Button */}
                <button
                  onClick={onToggleAudioDucking}
                  className={`h-5 px-1.5 rounded text-[9px] font-bold transition ${
                    audioDucking
                      ? 'bg-cyan-600 text-white shadow'
                      : 'bg-zinc-800 text-zinc-500 hover:text-zinc-300'
                  }`}
                  title={audioDucking ? '自動閃避已開啟 (人聲說話時降至 30%)' : '自動閃避已關閉'}
                >
                  Ducking
                </button>
                {/* Mute Button */}
                <button
                  onClick={onToggleBgmMute}
                  className={`h-5 w-5 rounded text-[9px] font-black transition ${
                    bgmMuted
                      ? 'bg-red-600 text-white shadow ring-1 ring-red-400'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={bgmMuted ? '取消配樂靜音' : '靜音 A2 配樂軌'}
                >
                  M
                </button>
                {/* Solo Button */}
                <button
                  onClick={onToggleBgmSolo}
                  className={`h-5 w-5 rounded text-[9px] font-black transition ${
                    bgmSolo
                      ? 'bg-amber-500 text-black font-bold shadow'
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
                  }`}
                  title={bgmSolo ? '取消獨奏' : '獨奏 A2 配樂軌'}
                >
                  S
                </button>
                <span className="w-8 text-right font-mono font-bold text-amber-400">{bgmVolume}%</span>
              </div>
            </div>

            {/* Current BGM Info & Switch Button */}
            <div className="flex items-center justify-between text-[11px] bg-black/40 px-2 py-1.5 rounded border border-zinc-800/80">
              <span className="truncate text-zinc-300 font-mono">
                {activeBgmName ? `🎵 ${activeBgmName}` : '（尚未選擇配樂）'}
              </span>
              <button
                onClick={onOpenBgmSelector}
                className="text-[10px] text-amber-400 hover:text-amber-300 font-medium ml-2 shrink-0 underline"
              >
                更換配樂
              </button>
            </div>

            {/* BGM Volume Fader */}
            <div>
              <input
                type="range"
                min={0}
                max={100}
                disabled={bgmMuted}
                value={bgmVolume}
                onChange={(e) => onChangeBgmVolume?.(parseInt(e.target.value, 10))}
                className="w-full accent-amber-500 h-1.5 bg-zinc-800 rounded-lg cursor-pointer disabled:opacity-40"
              />
              <div className="flex justify-between text-[9px] text-zinc-500 font-mono mt-0.5">
                <span>0% (靜音)</span>
                <span className="text-zinc-400">20% (推薦)</span>
                <span>100%</span>
              </div>
              <div className="text-[8px] text-zinc-500 italic leading-tight mt-1">
                💡 調整音量推桿會即時縮放時間軸配樂波形高度。
              </div>
            </div>
          </div>

          {/* Speed Ramping */}
          <div className="pt-1">
            <div className="flex items-center justify-between mb-1.5 text-[11px] text-zinc-400">
              <span>片段播放速度 (Speed)</span>
              <span className="font-mono text-primary">{playbackRate}x</span>
            </div>
            <div className="grid grid-cols-4 gap-1">
              {[0.5, 1.0, 1.5, 2.0].map((rate) => (
                <button
                  key={rate}
                  onClick={() => onChangePlaybackRate(rate)}
                  className={`rounded border py-1 text-center font-mono text-[10px] transition ${
                    playbackRate === rate
                      ? 'border-primary bg-primary/20 text-primary font-bold'
                      : 'border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800 text-zinc-400'
                  }`}
                >
                  {rate}x
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-zinc-800/80 bg-[#121214] px-3 py-2 text-[10px] text-zinc-500 text-right font-mono">
        FCP Inspector Engine
      </div>
    </div>
  )
}
