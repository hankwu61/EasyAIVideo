import React, { useState, useEffect } from 'react'
import { X, Save, Sparkles } from 'lucide-react'
import type {
  Template,
  TemplateCreate,
  TemplateConfig,
  StyleOption,
  BgmOption,
  TransitionOption,
  SubtitlePositionOption,
  FontOption,
} from '../../types'
import { createTemplate, getStyles, getBgm, getPresets } from '../../api'
import { useLang } from '../../i18n'

interface TemplateEditModalProps {
  isOpen: boolean
  initialConfig?: Partial<TemplateConfig>
  initialName?: string
  initialDescription?: string
  onClose: () => void
  onSaveSuccess: (tpl: Template) => void
}

const COVER_GRADIENTS = [
  { id: 'from-amber-600 to-stone-900', label: '琥珀電影' },
  { id: 'from-pink-500 to-rose-700', label: '熱血動漫' },
  { id: 'from-blue-600 to-indigo-800', label: '短影音藍' },
  { id: 'from-teal-400 to-emerald-700', label: '治癒水彩' },
  { id: 'from-cyan-500 to-purple-800', label: '賽博龐克' },
  { id: 'from-gray-600 to-slate-900', label: '極簡黑白' },
  { id: 'from-purple-600 to-indigo-900', label: '夢幻紫境' },
]

export const TemplateEditModal: React.FC<TemplateEditModalProps> = ({
  isOpen,
  initialConfig,
  initialName = '',
  initialDescription = '',
  onClose,
  onSaveSuccess,
}) => {
  const { t } = useLang()
  const [name, setName] = useState(initialName)
  const [description, setDescription] = useState(initialDescription)
  const [coverColor, setCoverColor] = useState('from-indigo-600 to-purple-800')

  // 5 Dimensions
  const [styleId, setStyleId] = useState(initialConfig?.style_id || 'cinematic')
  const [stylePrompt, setStylePrompt] = useState(initialConfig?.style_prompt || '')
  const [fontFamily, setFontFamily] = useState(initialConfig?.font_family || 'msjh')
  const [fontSize, setFontSize] = useState(initialConfig?.font_size || 24)
  const [subtitlePosition, setSubtitlePosition] = useState<any>(initialConfig?.subtitle_position || 'bottom')
  const [transition, setTransition] = useState<any>(initialConfig?.transition || 'none')
  const [transitionDuration, setTransitionDuration] = useState(initialConfig?.transition_duration || 0.5)
  const [bgm, setBgm] = useState<string | null>(initialConfig?.bgm || null)
  const [bgmVolume, setBgmVolume] = useState(initialConfig?.bgm_volume ?? 0.2)

  const [styles, setStyles] = useState<StyleOption[]>([])
  const [bgmList, setBgmList] = useState<BgmOption[]>([])
  const [transitions, setTransitions] = useState<TransitionOption[]>([])
  const [subtitlePositions, setSubtitlePositions] = useState<SubtitlePositionOption[]>([])
  const [fonts, setFonts] = useState<FontOption[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setName(initialName)
    setDescription(initialDescription)
    if (initialConfig?.style_id) setStyleId(initialConfig.style_id)
    if (initialConfig?.style_prompt) setStylePrompt(initialConfig.style_prompt)
    if (initialConfig?.font_family) setFontFamily(initialConfig.font_family)
    if (initialConfig?.font_size) setFontSize(initialConfig.font_size)
    if (initialConfig?.subtitle_position) setSubtitlePosition(initialConfig.subtitle_position)
    if (initialConfig?.transition) setTransition(initialConfig.transition)
    if (initialConfig?.transition_duration) setTransitionDuration(initialConfig.transition_duration)
    if (initialConfig?.bgm !== undefined) setBgm(initialConfig.bgm)
    if (initialConfig?.bgm_volume !== undefined) setBgmVolume(initialConfig.bgm_volume)

    // Load options
    Promise.all([getStyles(), getBgm(), getPresets()]).then(([s, b, p]) => {
      setStyles(s)
      setBgmList(b)
      if (p.transitions) setTransitions(p.transitions)
      if (p.subtitle_positions) setSubtitlePositions(p.subtitle_positions)
      if (p.fonts) setFonts(p.fonts)
    })
  }, [isOpen, initialConfig, initialName, initialDescription])

  if (!isOpen) return null

  const handleSave = async () => {
    if (!name.trim()) {
      setError('請輸入模板名稱')
      return
    }
    setLoading(true)
    setError(null)

    const payload: TemplateCreate = {
      name: name.trim(),
      description: description.trim(),
      category: 'custom',
      cover_color: coverColor,
      icon: 'LayoutTemplate',
      config: {
        style_id: styleId,
        style_prompt: stylePrompt,
        font_family: fontFamily,
        font_size: fontSize,
        subtitle_position: subtitlePosition,
        transition: transition,
        transition_duration: transitionDuration,
        bgm: bgm,
        bgm_volume: bgmVolume,
      },
    }

    try {
      const created = await createTemplate(payload)
      onSaveSuccess(created)
      onClose()
    } catch (err: any) {
      setError(err?.detail || err?.message || '儲存失敗')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl p-6 space-y-5 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-zinc-100">{t('new_template')}</h2>
              <p className="text-xs text-zinc-400">{t('template_dimensions')}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <div className="space-y-4">
          {/* Name and Description */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">模板名稱 *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：科技冷酷藍"
                className="w-full text-xs bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-200 focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1">封面主題色</label>
              <select
                value={coverColor}
                onChange={(e) => setCoverColor(e.target.value)}
                className="w-full text-xs bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-200 focus:outline-none focus:border-purple-500"
              >
                {COVER_GRADIENTS.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-300 mb-1">簡短描述</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="說明此模板的使用情境或視覺特色…"
              className="w-full text-xs bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-zinc-200 focus:outline-none focus:border-purple-500"
            />
          </div>

          {/* Dimension 1: Style */}
          <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-3">
            <h4 className="text-xs font-bold text-purple-400 flex items-center gap-1.5">
              <span>1. 視覺風格 (Style)</span>
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">風格類型</label>
                <select
                  value={styleId}
                  onChange={(e) => {
                    const sid = e.target.value
                    setStyleId(sid)
                    const found = styles.find((s) => s.id === sid)
                    if (found) setStylePrompt(found.prompt)
                  }}
                  className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200"
                >
                  {styles.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">自訂提示詞</label>
                <input
                  type="text"
                  value={stylePrompt}
                  onChange={(e) => setStylePrompt(e.target.value)}
                  placeholder="追加視覺風格英文提示詞…"
                  className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200"
                />
              </div>
            </div>
          </div>

          {/* Dimension 2: Font */}
          <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-3">
            <h4 className="text-xs font-bold text-blue-400 flex items-center gap-1.5">
              <span>2. 字型與字級 (Font & Size)</span>
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">{t('font_family')}</label>
                <select
                  value={fontFamily}
                  onChange={(e) => setFontFamily(e.target.value)}
                  className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200"
                >
                  {fonts.length > 0 ? (
                    fonts.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.label}
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="msjh">微軟正黑體</option>
                      <option value="msyh">微軟雅黑</option>
                      <option value="simhei">黑體 / 粗黑</option>
                      <option value="arial">Arial</option>
                      <option value="noto">思源黑體</option>
                      <option value="system">系統預設</option>
                    </>
                  )}
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">{t('font_size')} (12-72 pt)</label>
                <input
                  type="number"
                  min={12}
                  max={72}
                  value={fontSize}
                  onChange={(e) => setFontSize(Number(e.target.value))}
                  className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200"
                />
              </div>
            </div>
          </div>

          {/* Dimension 3 & 4: Subtitle Position & Transition */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-2">
              <h4 className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                <span>3. {t('subtitle_position')}</span>
              </h4>
              <select
                value={subtitlePosition}
                onChange={(e) => setSubtitlePosition(e.target.value as any)}
                className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200"
              >
                {subtitlePositions.length > 0 ? (
                  subtitlePositions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="bottom">{t('position_bottom')}（標準預設）</option>
                    <option value="middle">{t('position_middle')}（焦點短影音）</option>
                    <option value="top">{t('position_top')}（避開底部圖案）</option>
                  </>
                )}
              </select>
            </div>

            <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-2">
              <h4 className="text-xs font-bold text-indigo-400 flex items-center gap-1.5">
                <span>4. {t('transition')}</span>
              </h4>
              <div className="flex gap-2">
                <select
                  value={transition}
                  onChange={(e) => setTransition(e.target.value as any)}
                  className="flex-1 text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200"
                >
                  {transitions.length > 0 ? (
                    transitions.map((tr) => (
                      <option key={tr.id} value={tr.id}>
                        {tr.label}
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="none">無轉場（直接接續）</option>
                      <option value="fade">淡入淡出 (Fade)</option>
                      <option value="dissolve">疊化 (Dissolve)</option>
                      <option value="wipeleft">向左擦除 (Wipe Left)</option>
                      <option value="wiperight">向右擦除 (Wipe Right)</option>
                      <option value="slideup">向上滑動 (Slide Up)</option>
                      <option value="slidedown">向下滑動 (Slide Down)</option>
                      <option value="circlecrop">圓形縮放 (Circle Crop)</option>
                    </>
                  )}
                </select>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="2.0"
                  value={transitionDuration}
                  onChange={(e) => setTransitionDuration(parseFloat(e.target.value))}
                  title="轉場時間 (秒)"
                  className="w-16 text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-zinc-200 text-center"
                />
              </div>
            </div>
          </div>

          {/* Dimension 5: BGM */}
          <div className="p-3.5 rounded-xl bg-zinc-950 border border-zinc-800/80 space-y-3">
            <h4 className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
              <span>5. 背景音樂 (BGM)</span>
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">{t('bgm')}</label>
                <select
                  value={bgm || ''}
                  onChange={(e) => setBgm(e.target.value || null)}
                  className="w-full text-xs bg-zinc-900 border border-zinc-800 rounded-lg px-2.5 py-1.5 text-zinc-200"
                >
                  <option value="">{t('bgm_none')}</option>
                  {bgmList.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">音量 ({Math.round(bgmVolume * 100)}%)</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={bgmVolume}
                  onChange={(e) => setBgmVolume(parseFloat(e.target.value))}
                  className="w-full accent-purple-500"
                />
              </div>
            </div>
          </div>

          {error && <div className="text-xs text-rose-400 bg-rose-950/40 p-2.5 rounded-xl">{error}</div>}

          {/* Footer buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="py-2 px-4 rounded-xl text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
            >
              {t('cancel')}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={loading || !name.trim()}
              className="py-2 px-5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-lg shadow-purple-600/20"
            >
              <Save className="w-4 h-4" />
              {t('save')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
