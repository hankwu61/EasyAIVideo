import React, { useState, useRef } from 'react'
import { Upload, X, FileText, CheckCircle2, AlertCircle } from 'lucide-react'
import type { Template } from '../../types'
import { importTemplate } from '../../api'
import { useLang } from '../../i18n'

interface ImportTemplateModalProps {
  isOpen: boolean
  onClose: () => void
  onImportSuccess: (tpl: Template) => void
}

export const ImportTemplateModal: React.FC<ImportTemplateModalProps> = ({
  isOpen,
  onClose,
  onImportSuccess,
}) => {
  const { t } = useLang()
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!isOpen) return null

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    const reader = new FileReader()
    reader.onload = (event) => {
      const content = event.target?.result as string
      setInputText(content)
    }
    reader.onerror = () => {
      setError('讀取檔案失敗')
    }
    reader.readAsText(file)
  }

  const handleImport = async () => {
    if (!inputText.trim()) {
      setError('請輸入分享代碼或貼上 JSON 內容')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const tpl = await importTemplate({ data: inputText.trim() })
      onImportSuccess(tpl)
      onClose()
    } catch (err: any) {
      setError(err?.detail || err?.message || '匯入失敗，請確認代碼或格式是否正確')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl bg-zinc-900 border border-zinc-800 shadow-2xl p-6 space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-zinc-100">{t('import_template')}</h2>
              <p className="text-xs text-zinc-400">支援貼上分享代碼或上傳 .json 模板檔案</p>
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
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-zinc-300">分享代碼 / JSON 內容</label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-xs text-teal-400 hover:text-teal-300 flex items-center gap-1 transition-colors"
              >
                <FileText className="w-3.5 h-3.5" />
                上傳 .json 檔
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>
            <textarea
              value={inputText}
              onChange={(e) => {
                setInputText(e.target.value)
                if (error) setError(null)
              }}
              placeholder={t('import_placeholder')}
              rows={5}
              className="w-full text-xs font-mono bg-zinc-950 border border-zinc-800 rounded-xl p-3 text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-teal-500 transition-colors resize-none"
            />
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Action buttons */}
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
              onClick={handleImport}
              disabled={loading || !inputText.trim()}
              className="py-2 px-5 rounded-xl bg-teal-600 hover:bg-teal-500 disabled:opacity-50 disabled:pointer-events-none text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-lg shadow-teal-600/20"
            >
              {loading ? (
                '匯入中…'
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  {t('confirm')}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
