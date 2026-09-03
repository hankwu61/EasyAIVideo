import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Clapperboard, Plus } from 'lucide-react'
import { deleteProject, errorMessage, listProjects } from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import ProjectCard from '../components/ProjectCard'
import { useToast } from '../components/Toast'
import { ErrorAlert, PageHeader, Skeleton } from '../components/ui'
import { useLang } from '../i18n'
import type { ProjectSummary } from '../types'

export default function ProjectsPage() {
  const { t } = useLang()
  const toast = useToast()
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<ProjectSummary | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async (silent = false) => {
    if (!silent) setError(null)
    try {
      setProjects(await listProjects())
      setError(null)
    } catch (e) {
      if (!silent) setError(errorMessage(e))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // Light polling while any project has an active task so list cards stay fresh.
  const hasActive = !!projects?.some((p) => p.active_task)
  useEffect(() => {
    if (!hasActive) return
    const id = window.setInterval(() => void load(true), 3000)
    return () => window.clearInterval(id)
  }, [hasActive, load])

  const confirmDelete = async () => {
    if (!pendingDelete) return
    setDeleting(true)
    try {
      await deleteProject(pendingDelete.id)
      setProjects((list) => list?.filter((p) => p.id !== pendingDelete.id) ?? null)
      toast.success(t('project_deleted'))
      setPendingDelete(null)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <PageHeader
        title={t('projects_title')}
        subtitle={t('projects_subtitle')}
        actions={
          <Link to="/new" className="btn-primary">
            <Plus size={16} />
            {t('new_project')}
          </Link>
        }
      />

      {error && <ErrorAlert message={error} onRetry={() => void load()} className="mb-4" />}

      {projects === null && !error && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="card overflow-hidden">
              <Skeleton className="aspect-video w-full rounded-none" />
              <div className="space-y-2 p-4">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      )}

      {projects !== null && projects.length === 0 && (
        <div className="card flex flex-col items-center px-6 py-16 text-center">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-accent/15 text-accent">
            <Clapperboard size={26} />
          </span>
          <h2 className="mt-4 text-lg font-semibold">{t('no_projects')}</h2>
          <p className="mt-1 max-w-sm text-sm text-muted">{t('no_projects_hint')}</p>
          <Link to="/new" className="btn-primary mt-6">
            <Plus size={16} />
            {t('new_project')}
          </Link>
        </div>
      )}

      {projects !== null && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} onDelete={setPendingDelete} />
          ))}
        </div>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        danger
        busy={deleting}
        title={t('delete')}
        message={pendingDelete ? t('delete_project_confirm', { title: pendingDelete.title || t('untitled') }) : ''}
        confirmLabel={t('delete')}
        onConfirm={() => void confirmDelete()}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  )
}
