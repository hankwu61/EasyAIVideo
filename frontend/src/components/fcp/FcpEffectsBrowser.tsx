import { useState, useEffect, useRef } from 'react'
import {
  Check,
  Clapperboard,
  Film,
  Music,
  Pause,
  Play,
  SlidersHorizontal,
  Sparkles,
  Upload,
  Volume2,
} from 'lucide-react'
import type { BgmOption, Project, Scene } from '../../types'
import { getBgm, uploadBgm } from '../../api'

export interface VideoFilter {
  id: string
  name: string
  cssFilter: string
  description: string
  previewBg: string
}

export const FCP_FILTERS: VideoFilter[] = [
  {
    id: 'none',
    name: '原色 (Normal)',
    cssFilter: 'none',
    description: '原始畫面無濾鏡',
    previewBg: 'bg-zinc-800',
  },
  {
    id: 'cinematic',
    name: '好萊塢電影 (Cinematic)',
    cssFilter: 'contrast(1.15) saturate(1.1) brightness(0.95) sepia(0.08)',
    description: '高動態範圍、細膩電影感',
    previewBg: 'bg-gradient-to-r from-blue-900 to-amber-900',
  },
  {
    id: 'teal_orange',
    name: '青橙色調 (Teal & Orange)',
    cssFilter: 'contrast(1.2) hue-rotate(-15deg) saturate(1.35)',
    description: '好萊塢動作商業大片色彩',
    previewBg: 'bg-gradient-to-r from-cyan-900 to-orange-900',
  },
  {
    id: 'cyberpunk',
    name: '賽博龐克 (Cyberpunk)',
    cssFilter: 'contrast(1.25) saturate(1.5) hue-rotate(45deg)',
    description: '霓虹夜景、強烈科技感',
    previewBg: 'bg-gradient-to-r from-purple-900 to-pink-900',
  },
  {
    id: 'noir_bw',
    name: '經典黑白 (Noir B&W)',
    cssFilter: 'grayscale(1) contrast(1.3) brightness(0.9)',
    description: '高反差黑白紀實底片風格',
    previewBg: 'bg-gradient-to-r from-zinc-900 to-zinc-600',
  },
  {
    id: 'golden_hour',
    name: '暖金夕陽 (Golden Hour)',
    cssFilter: 'sepia(0.3) saturate(1.25) contrast(1.05) brightness(1.02)',
    description: '溫暖夕陽、柔和金黃日光',
    previewBg: 'bg-gradient-to-r from-amber-800 to-yellow-700',
  },
  {
    id: 'vintage',
    name: '復古底片 (Vintage Film)',
    cssFilter: 'sepia(0.2) contrast(0.95) brightness(1.05) saturate(0.85)',
    description: '經典 80 年代懷舊顆粒氛圍',
    previewBg: 'bg-gradient-to-r from-stone-800 to-amber-950',
  },
]

interface FcpEffectsBrowserProps {
  project: Project
  scenes?: Scene[]
  activeFilter: string
  onSelectFilter: (filterId: string) => void
  onSeekToScene: (index: number) => void
  activeBgmName?: string | null
  onSelectBgm?: (bgmName: string | null) => void
  tab?: 'clips' | 'filters' | 'audio'
  onChangeTab?: (tab: 'clips' | 'filters' | 'audio') => void
}

export default function FcpEffectsBrowser({
  project,
  scenes = [],
  activeFilter,
  onSelectFilter,
  onSeekToScene,
  activeBgmName,
  onSelectBgm,
  tab: controlledTab,
  onChangeTab: setControlledTab,
}: FcpEffectsBrowserProps) {
  const [internalTab, setInternalTab] = useState<'clips' | 'filters' | 'audio'>('clips')
  const tab = controlledTab !== undefined ? controlledTab : internalTab
  const setTab = setControlledTab || setInternalTab
  const [bgmList, setBgmList] = useState<BgmOption[]>([])
  const [loadingBgm, setLoadingBgm] = useState(false)
  const [previewingBgm, setPreviewingBgm] = useState<string | null>(null)
  const [uploadingBgm, setUploadingBgm] = useState(false)
  const previewAudioRef = useRef<HTMLAudioElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  // Fetch BGMs on tab switch or mount
  useEffect(() => {
    if (tab === 'audio' && bgmList.length === 0) {
      setLoadingBgm(true)
      getBgm()
        .then((items) => setBgmList(items))
        .catch(() => {})
        .finally(() => setLoadingBgm(false))
    }
  }, [tab, bgmList.length])

  // Stop preview audio when unmounting or switching tabs
  useEffect(() => {
    return () => {
      if (previewAudioRef.current) {
        previewAudioRef.current.pause()
      }
    }
  }, [tab])

  const togglePreviewBgm = (url: string, name: string) => {
    if (previewingBgm === name) {
      if (previewAudioRef.current) {
        previewAudioRef.current.pause()
      }
      setPreviewingBgm(null)
    } else {
      if (!previewAudioRef.current) {
        previewAudioRef.current = new Audio()
      }
      previewAudioRef.current.src = url
      previewAudioRef.current.play().catch(() => {})
      setPreviewingBgm(name)
      previewAudioRef.current.onended = () => setPreviewingBgm(null)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingBgm(true)
    try {
      const res = await uploadBgm(file)
      setBgmList((prev) => [...prev.filter((b) => b.name !== res.name), res])
      onSelectBgm?.(res.name)
    } catch {
      // ignore
    } finally {
      setUploadingBgm(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="flex h-full w-72 shrink-0 flex-col border-r border-zinc-800 bg-[#161618] text-xs select-none">
      {/* Tab Navigation */}
      <div className="flex border-b border-zinc-800 bg-[#121214] px-1 pt-1">
        <button
          onClick={() => setTab('clips')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 font-medium transition ${
            tab === 'clips'
              ? 'border-b-2 border-primary text-primary'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <Clapperboard size={13} />
          <span>分幕素材</span>
        </button>
        <button
          onClick={() => setTab('filters')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 font-medium transition ${
            tab === 'filters'
              ? 'border-b-2 border-primary text-primary'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <Sparkles size={13} />
          <span>濾鏡調色</span>
        </button>
        <button
          onClick={() => setTab('audio')}
          className={`flex flex-1 items-center justify-center gap-1.5 py-2 font-medium transition ${
            tab === 'audio'
              ? 'border-b-2 border-primary text-primary'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <Music size={13} />
          <span>音樂音效</span>
        </button>
      </div>

      {/* Tab Contents */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
        {/* TAB 1: CLIPS / SCENES */}
        {tab === 'clips' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 px-1 pb-1">
              <span>分幕清單 ({scenes.length || project.scenes?.length || 0} 幕)</span>
              <span className="text-[10px] text-zinc-500">點擊跳轉至該幕</span>
            </div>
            {scenes.length > 0 ? (
              scenes.map((scene, idx) => (
                <div
                  key={scene.id || idx}
                  onClick={() => onSeekToScene(idx)}
                  className="group flex items-center gap-2 rounded border border-zinc-800/80 bg-zinc-900/60 p-1.5 transition hover:border-primary/60 hover:bg-zinc-800/80 cursor-pointer"
                >
                  <div className="relative h-12 w-20 shrink-0 overflow-hidden rounded bg-black/60">
                    {scene.image_url || scene.segment_url ? (
                      <img
                        src={scene.image_url || ''}
                        alt={`Scene ${idx + 1}`}
                        className="h-full w-full object-cover group-hover:scale-105 transition"
                      />
                    ) : (
                      <div className="grid h-full w-full place-items-center text-zinc-600">
                        <Film size={16} />
                      </div>
                    )}
                    <span className="absolute bottom-0.5 right-0.5 rounded bg-black/80 px-1 py-0.2 text-[9px] font-mono text-zinc-300">
                      {scene.duration ? `${scene.duration.toFixed(1)}s` : `#${idx + 1}`}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="rounded bg-primary/20 px-1 text-[10px] font-bold text-primary">
                        S{idx + 1}
                      </span>
                      <span className="text-[11px] font-medium text-zinc-200 truncate">
                        第 {idx + 1} 幕
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-[10px] text-zinc-400 leading-tight">
                      {scene.narration || '（無旁白）'}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-4 text-center text-zinc-500">
                <Film size={24} className="mx-auto mb-1 opacity-40" />
                <p>無單獨分幕資料，目前使用完整影片軌道</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: FILTERS & LUTS */}
        {tab === 'filters' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 px-1 pb-1">
              <span>FCP 電影風格濾鏡 (LUTs)</span>
              <span className="text-[10px] text-primary">即時渲染</span>
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {FCP_FILTERS.map((f) => {
                const isSelected = activeFilter === f.id
                return (
                  <button
                    key={f.id}
                    onClick={() => onSelectFilter(f.id)}
                    className={`flex items-center gap-2.5 rounded border p-2 text-left transition ${
                      isSelected
                        ? 'border-primary bg-primary/15 text-primary font-semibold ring-1 ring-primary'
                        : 'border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 hover:bg-zinc-800/60 text-zinc-300'
                    }`}
                  >
                    <div className={`h-8 w-12 shrink-0 rounded ${f.previewBg} border border-white/10 flex items-center justify-center text-[10px] font-bold text-white shadow`}>
                      LUT
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-xs truncate">{f.name}</div>
                      <div className="text-[10px] text-zinc-400 truncate">{f.description}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* TAB 3: AUDIO & BGM */}
        {tab === 'audio' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-[11px] text-zinc-400 px-1">
              <span>背景音樂與音效庫 (BGM Library)</span>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingBgm}
                className="flex items-center gap-1 rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-300 hover:bg-zinc-700 hover:text-white transition"
                title="上傳本機 MP3 / WAV 音訊檔案"
              >
                <Upload size={10} />
                <span>{uploadingBgm ? '上傳中…' : '上傳音樂'}</span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>

            {/* Current Selected BGM Status Card */}
            <div className="rounded-lg border border-amber-800/60 bg-gradient-to-r from-amber-950/40 to-zinc-900/60 p-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-zinc-300">目前使用配樂</span>
                <span className="font-mono text-[10px] font-bold text-amber-400 truncate max-w-[140px]">
                  {activeBgmName ? `🎵 ${activeBgmName}` : '無配樂 (純語音)'}
                </span>
              </div>
            </div>

            {/* BGM List */}
            <div className="space-y-1.5">
              {/* Option: No BGM (Mute) */}
              <div
                onClick={() => onSelectBgm?.(null)}
                className={`flex items-center justify-between p-2 rounded-lg border cursor-pointer transition ${
                  !activeBgmName
                    ? 'border-amber-400 bg-amber-500/10 text-white ring-1 ring-amber-400'
                    : 'border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center gap-2">
                  <div className="grid h-7 w-7 place-items-center rounded bg-zinc-800 text-zinc-400">
                    <Volume2 size={13} />
                  </div>
                  <div>
                    <div className="font-medium text-xs">無配樂 (靜音)</div>
                    <div className="text-[10px] text-zinc-500">僅保留 A1 人聲語音軌道</div>
                  </div>
                </div>
                {!activeBgmName && <Check size={14} className="text-amber-400" />}
              </div>

              {/* Real Available BGMs */}
              {loadingBgm ? (
                <div className="p-4 text-center text-zinc-500 text-[11px]">正在載入音樂庫…</div>
              ) : (
                bgmList.map((bgm) => {
                  const isSelected = activeBgmName === bgm.name
                  const isPreviewing = previewingBgm === bgm.name

                  return (
                    <div
                      key={bgm.name}
                      className={`flex items-center justify-between p-2 rounded-lg border transition ${
                        isSelected
                          ? 'border-amber-400 bg-amber-500/10 text-white ring-1 ring-amber-400'
                          : 'border-zinc-800 bg-zinc-900/40 text-zinc-300 hover:border-zinc-700 hover:bg-zinc-800/60'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        {/* Play / Pause Preview Button */}
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            togglePreviewBgm(bgm.url, bgm.name)
                          }}
                          className={`grid h-7 w-7 shrink-0 place-items-center rounded-full transition ${
                            isPreviewing
                              ? 'bg-amber-500 text-black shadow animate-pulse'
                              : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-white'
                          }`}
                          title={isPreviewing ? '暫停試聽' : '試聽音樂'}
                        >
                          {isPreviewing ? <Pause size={12} /> : <Play size={12} className="ml-0.5" />}
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-xs truncate font-mono">{bgm.name}</div>
                          <div className="text-[10px] text-zinc-500">背景音樂 (循環)</div>
                        </div>
                      </div>

                      {/* Apply to Project Button */}
                      <button
                        onClick={() => onSelectBgm?.(bgm.name)}
                        className={`ml-2 px-2 py-1 rounded text-[10px] font-medium transition ${
                          isSelected
                            ? 'bg-amber-500 text-black font-bold'
                            : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-white'
                        }`}
                      >
                        {isSelected ? '使用中' : '套用'}
                      </button>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div className="border-t border-zinc-800/80 bg-[#121214] px-3 py-2 flex items-center justify-between text-[10px] text-zinc-500">
        <span className="flex items-center gap-1">
          <SlidersHorizontal size={11} />
          FCP 素材特效庫
        </span>
        <span className="font-mono text-zinc-400">Pro NLE</span>
      </div>
    </div>
  )
}
