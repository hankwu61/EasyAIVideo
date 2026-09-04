import React, { useState, useEffect } from 'react'
import { Copy, Check, Download, X, Share2, Code2 } from 'lucide-react'
import type { Template, TemplateExportResult } from '../../types'
import { exportTemplate } from '../../api'
import { useLang } from '../../i18n'

interface ShareTemplateModalProps {
  template: Template | null
  onClose: () => void
}

export const ShareTemplateModal: React.FC<ShareTemplateModalProps> = ({ template, onClose }) => {
  const { t } = useLang()
  const [loading, setLoading] = useState(false)
  const [exportData, setExportData] = useState<TemplateExportResult | null>(null)
  const [copied, setCopied] = useState(false)
  const [showJson, setShowJson] = useState(false)

  useEffect(() => {
    if (!template) return
    setLoading(true)
    setCopied(false)
    exportTemplate(template.id)
      .then((res) => {
        setExportData(res)
      })
      .catch((err) => {
        console.error('Failed to export template', err)
      })
      .finally(() => setLoading(false))
  }, [template])

  if (!template) return null

  const handleCopy = () => {
    if (!exportData?.share_code) return
    navigator.clipboard.writeText(exportData.share_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  const handleDownload = () => {
    if (!exportData) return
    const blob = new Blob([JSON.stringify(exportData.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportData.filename || `template_${template.id}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <Share2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-zinc-100">{t('share_template')}</h2>
              <p className="text-xs text-zinc-400">{template.name}</p>
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

        {loading ? (
          <div className="py-12 text-center text-zinc-400 text-sm">{t('loading')}</div>
        ) : (
          <div className="space-y-4">
            {/* Share code box */}
            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1.5">{t('copy_share_code')}</label>
              <div className="relative">
                <textarea
                  readOnly
                  value={exportData?.share_code || ''}
                  rows={4}
                  className="w-full text-xs font-mono bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-zinc-300 focus:outline-none focus:border-purple-500 select-all resize-none"
                />
              </div>
              <p className="text-[11px] text-zinc-500 mt-1">
                此代碼內含風格、字型、字幕位置、轉場與 BGM 設定，任何人貼上代碼即可一鍵匯入。
              </p>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleCopy}
                className="flex-1 py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-all shadow-lg shadow-purple-600/20"
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4 text-white" />
                    {t('share_code_copied')}
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    {t('copy_share_code')}
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleDownload}
                className="py-2.5 px-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white text-xs font-semibold flex items-center justify-center gap-2 transition-colors border border-zinc-700/60"
              >
                <Download className="w-4 h-4" />
                {t('export_json')}
              </button>
            </div>

            {/* JSON collapsible view */}
            <div className="border-t border-zinc-800 pt-3">
              <button
                type="button"
                onClick={() => setShowJson(!showJson)}
                className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1.5 transition-colors"
              >
                <Code2 className="w-3.5 h-3.5" />
                {showJson ? '隱藏 JSON 原始資料' : '檢視 JSON 原始資料'}
              </button>
              {showJson && (
                <pre className="mt-2 text-[10px] font-mono p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-400 overflow-x-auto max-h-40">
                  {JSON.stringify(exportData?.data, null, 2)}
                </pre>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
