import React from 'react'
import {
  Film,
  Sparkles,
  Smartphone,
  Palette,
  Zap,
  PenTool,
  LayoutTemplate,
  Share2,
  Trash2,
  Check,
  Music,
  Type,
  AlignVerticalJustifyCenter,
  Shuffle,
} from 'lucide-react'
import type { Template } from '../../types'
import { useLang } from '../../i18n'

interface TemplateCardProps {
  template: Template
  isSelected?: boolean
  onSelect?: (tpl: Template) => void
  onShare?: (tpl: Template) => void
  onDelete?: (tpl: Template) => void
  compact?: boolean
}

const ICON_MAP: Record<string, React.ReactNode> = {
  Film: <Film className="w-5 h-5" />,
  Sparkles: <Sparkles className="w-5 h-5" />,
  Smartphone: <Smartphone className="w-5 h-5" />,
  Palette: <Palette className="w-5 h-5" />,
  Zap: <Zap className="w-5 h-5" />,
  PenTool: <PenTool className="w-5 h-5" />,
  LayoutTemplate: <LayoutTemplate className="w-5 h-5" />,
}

const TRANSITION_LABELS: Record<string, string> = {
  none: '無轉場',
  fade: '淡入淡出',
  dissolve: '疊化',
  wipeleft: '向左擦除',
  wiperight: '向右擦除',
  slideup: '向上滑動',
  slidedown: '向下滑動',
  circlecrop: '圓形縮放',
}

const POSITION_LABELS: Record<string, string> = {
  bottom: '底部',
  middle: '中央',
  top: '頂部',
}

const FONT_LABELS: Record<string, string> = {
  msjh: '微軟正黑體',
  msyh: '微軟雅黑',
  simhei: '粗黑體',
  arial: 'Arial',
  noto: '思源黑體',
  system: '系統預設',
}

export const TemplateCard: React.FC<TemplateCardProps> = ({
  template,
  isSelected,
  onSelect,
  onShare,
  onDelete,
  compact = false,
}) => {
  const { t } = useLang()
  const cfg = template.config

  const iconEl = (template.icon && ICON_MAP[template.icon]) || <LayoutTemplate className="w-5 h-5" />

  const gradientClass = template.cover_color || 'from-indigo-600 to-purple-900'

  if (compact) {
    return (
      <div
        onClick={() => onSelect?.(template)}
        className={`group relative p-3 rounded-xl border transition-all cursor-pointer select-none text-left ${
          isSelected
            ? 'bg-purple-950/40 border-purple-500 shadow-md shadow-purple-500/10'
            : 'bg-zinc-900/60 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-800/50'
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-lg bg-gradient-to-br ${gradientClass} flex items-center justify-center text-white shrink-0 shadow-inner`}
          >
            {iconEl}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold text-zinc-200 truncate">{template.name}</span>
              {template.is_builtin && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 shrink-0">
                  {t('builtin_tag')}
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 line-clamp-1 mt-0.5">{template.description}</p>
          </div>
          {isSelected && (
            <div className="w-5 h-5 rounded-full bg-purple-500 text-white flex items-center justify-center shrink-0">
              <Check className="w-3 h-3" />
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div
      className={`group relative rounded-2xl border overflow-hidden transition-all duration-300 flex flex-col bg-zinc-900/80 backdrop-blur-sm ${
        isSelected
          ? 'border-purple-500 ring-2 ring-purple-500/20 shadow-xl shadow-purple-500/10'
          : 'border-zinc-800 hover:border-zinc-700 hover:shadow-lg hover:shadow-black/40'
      }`}
    >
      {/* Header Cover Banner */}
      <div className={`relative h-28 bg-gradient-to-br ${gradientClass} p-4 flex flex-col justify-between overflow-hidden`}>
        {/* Decorative elements */}
        <div className="absolute inset-0 bg-black/20" />
        <div className="absolute -right-6 -bottom-6 w-24 h-24 rounded-full bg-white/10 blur-xl pointer-events-none" />

        <div className="relative z-10 flex items-center justify-between">
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-medium backdrop-blur-md ${
              template.is_builtin
                ? 'bg-black/40 text-amber-300 border border-amber-400/30'
                : 'bg-black/40 text-teal-300 border border-teal-400/30'
            }`}
          >
            {template.is_builtin ? t('builtin_tag') : t('custom_tag')}
          </span>

          <div className="flex items-center gap-1">
            {onShare && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onShare(template)
                }}
                className="p-1.5 rounded-lg bg-black/30 hover:bg-black/60 text-white/90 hover:text-white transition-colors"
                title={t('share_template')}
              >
                <Share2 className="w-4 h-4" />
              </button>
            )}
            {!template.is_builtin && onDelete && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(template)
                }}
                className="p-1.5 rounded-lg bg-black/30 hover:bg-rose-600/80 text-white/90 hover:text-white transition-colors"
                title={t('delete')}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        <div className="relative z-10 flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-white/15 backdrop-blur-md text-white shadow-inner">{iconEl}</div>
          <h3 className="text-base font-bold text-white tracking-wide truncate drop-shadow-sm">{template.name}</h3>
        </div>
      </div>

      {/* Body content */}
      <div className="p-4 flex-1 flex flex-col justify-between space-y-4">
        <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed min-h-[32px]">{template.description}</p>

        {/* 5-dimension pills */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/60 border border-zinc-700/50 text-zinc-300">
            <Type className="w-3.5 h-3.5 text-purple-400 shrink-0" />
            <span className="truncate">
              {FONT_LABELS[cfg.font_family] || cfg.font_family} ({cfg.font_size}pt)
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/60 border border-zinc-700/50 text-zinc-300">
            <AlignVerticalJustifyCenter className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span className="truncate">{POSITION_LABELS[cfg.subtitle_position] || cfg.subtitle_position}字幕</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/60 border border-zinc-700/50 text-zinc-300">
            <Shuffle className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span className="truncate">{TRANSITION_LABELS[cfg.transition] || cfg.transition}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/60 border border-zinc-700/50 text-zinc-300">
            <Music className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="truncate">{cfg.bgm || '無 BGM'}</span>
          </div>
        </div>

        {/* Action Button */}
        {onSelect && (
          <button
            type="button"
            onClick={() => onSelect(template)}
            className={`w-full py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
              isSelected
                ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white'
            }`}
          >
            {isSelected ? (
              <>
                <Check className="w-3.5 h-3.5" />
                已套用
              </>
            ) : (
              t('apply_to_project')
            )}
          </button>
        )}
      </div>
    </div>
  )
}
