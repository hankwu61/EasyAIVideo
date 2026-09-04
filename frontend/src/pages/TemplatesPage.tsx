import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Upload, Sparkles, LayoutTemplate, Layers } from 'lucide-react'
import type { Template } from '../types'
import { listTemplates, deleteTemplate } from '../api'
import { useLang } from '../i18n'
import { TemplateCard } from '../components/templates/TemplateCard'
import { ShareTemplateModal } from '../components/templates/ShareTemplateModal'
import { ImportTemplateModal } from '../components/templates/ImportTemplateModal'
import { TemplateEditModal } from '../components/templates/TemplateEditModal'

export const TemplatesPage: React.FC = () => {
  const { t } = useLang()
  const navigate = useNavigate()
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'builtin' | 'custom'>('all')

  // Modals
  const [sharingTemplate, setSharingTemplate] = useState<Template | null>(null)
  const [isImportOpen, setIsImportOpen] = useState(false)
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  const loadTemplates = async () => {
    setLoading(true)
    try {
      const data = await listTemplates()
      setTemplates(data)
    } catch (err) {
      console.error('Failed to load templates', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTemplates()
  }, [])

  const handleDelete = async (tpl: Template) => {
    if (!window.confirm(t('delete_template_confirm', { name: tpl.name }))) return
    try {
      await deleteTemplate(tpl.id)
      setTemplates((prev) => prev.filter((item) => item.id !== tpl.id))
    } catch (err) {
      console.error('Failed to delete template', err)
    }
  }

  const handleApplyToNewProject = (tpl: Template) => {
    navigate(`/new?template_id=${encodeURIComponent(tpl.id)}`)
  }

  const filtered = templates.filter((tpl) => {
    if (filter === 'builtin') return tpl.is_builtin
    if (filter === 'custom') return !tpl.is_builtin
    return true
  })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-in fade-in duration-300">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
              <LayoutTemplate className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-black tracking-tight text-white">{t('templates_title')}</h1>
          </div>
          <p className="text-sm text-zinc-400 mt-1.5 max-w-2xl">{t('templates_subtitle')}</p>
        </div>

        {/* Top actions */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsImportOpen(true)}
            className="py-2.5 px-4 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 hover:text-white text-xs font-semibold flex items-center gap-2 border border-zinc-700/60 transition-all"
          >
            <Upload className="w-4 h-4 text-teal-400" />
            {t('import_template')}
          </button>
          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="py-2.5 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold flex items-center gap-2 shadow-lg shadow-purple-600/25 transition-all"
          >
            <Plus className="w-4 h-4" />
            {t('new_template')}
          </button>
        </div>
      </div>

      {/* Filter Tabs & Dimension Summary Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-1.5 p-1 bg-zinc-900/90 border border-zinc-800 rounded-xl w-fit">
          <button
            type="button"
            onClick={() => setFilter('all')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === 'all' ? 'bg-purple-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            全部 ({templates.length})
          </button>
          <button
            type="button"
            onClick={() => setFilter('builtin')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === 'builtin' ? 'bg-purple-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {t('builtin_tag')} ({templates.filter((t) => t.is_builtin).length})
          </button>
          <button
            type="button"
            onClick={() => setFilter('custom')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === 'custom' ? 'bg-purple-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {t('custom_tag')} ({templates.filter((t) => !t.is_builtin).length})
          </button>
        </div>

        <div className="text-xs text-zinc-500 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-purple-400" />
          <span>點選任一模板卡片下方按鈕，即可直接以該模板建立全新專案。</span>
        </div>
      </div>

      {/* Templates Grid */}
      {loading ? (
        <div className="py-20 text-center text-zinc-400 text-sm">{t('loading')}</div>
      ) : filtered.length === 0 ? (
        <div className="py-20 text-center space-y-3 bg-zinc-900/30 rounded-2xl border border-zinc-800/50">
          <Layers className="w-10 h-10 text-zinc-600 mx-auto" />
          <p className="text-sm text-zinc-400">{t('no_templates')}</p>
          <button
            type="button"
            onClick={() => setIsCreateOpen(true)}
            className="py-2 px-4 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium"
          >
            {t('new_template')}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((tpl) => (
            <TemplateCard
              key={tpl.id}
              template={tpl}
              onSelect={handleApplyToNewProject}
              onShare={(t) => setSharingTemplate(t)}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <ShareTemplateModal template={sharingTemplate} onClose={() => setSharingTemplate(null)} />

      <ImportTemplateModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onImportSuccess={(newTpl) => {
          setTemplates((prev) => [newTpl, ...prev])
        }}
      />

      <TemplateEditModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSaveSuccess={(newTpl) => {
          setTemplates((prev) => [newTpl, ...prev])
        }}
      />
    </div>
  )
}
