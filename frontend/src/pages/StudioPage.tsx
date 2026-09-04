import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Download, FileText, Plus, X } from 'lucide-react'
import {
  ApiError,
  addScene,
  cancelTask,
  deleteScene,
  errorMessage,
  generateAll,
  generateAssets,
  generateScript,
  getProject,
  listTasks,
  patchProject,
  patchScene,
  renderProject,
  reorderScenes,
  reviewProject,
  uploadSceneAsset,
} from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import PreviewPanel from '../components/PreviewPanel'
import ReviewPanel from '../components/ReviewPanel'
import SceneCard, { type SceneActions } from '../components/SceneCard'
import StudioHeader, { BackLink } from '../components/StudioHeader'
import StudioSettings from '../components/StudioSettings'
import TaskBar from '../components/TaskBar'
import { useToast } from '../components/Toast'
import { ErrorAlert, Skeleton } from '../components/ui'
import { useResources } from '../hooks/useResources'
import { useLang } from '../i18n'
import type { AssetKind, Project, ScenePatch, Task, UploadKind } from '../types'

const POLL_MS = 1500

export default function StudioPage() {
  const { id = '' } = useParams()
  const { t } = useLang()
  const toast = useToast()
  const { resources, error: resourcesError, reload: reloadResources } = useResources()

  const [project, setProject] = useState<Project | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [lastTask, setLastTask] = useState<Task | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [confirmScript, setConfirmScript] = useState(false)
  const [pendingDeleteScene, setPendingDeleteScene] = useState<string | null>(null)
  const [deletingScene, setDeletingScene] = useState(false)

  const [titleDraft, setTitleDraft] = useState('')
  const titleFocused = useRef(false)

  // Episode projects: load the parent series once for the drama speaker list.
  const parentId = project?.kind === 'episode' ? project.parent_id : null
  const [parent, setParent] = useState<Project | null>(null)
  useEffect(() => {
    if (!parentId) {
      setParent(null)
      return
    }
    let cancelled = false
    getProject(parentId)
      .then((p) => {
        if (!cancelled) setParent(p)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [parentId])

  const load = useCallback(
    async (silent = false) => {
      try {
        const p = await getProject(id)
        setProject(p)
        setLoadError(null)
        setNotFound(false)
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setNotFound(true)
        else if (!silent) setLoadError(errorMessage(e))
      }
    },
    [id],
  )

  const checkLastTask = useCallback(async () => {
    try {
      const tasks = await listTasks({ project_id: id, limit: 1 })
      const latest = tasks[0]
      setLastTask(latest && (latest.status === 'failed' || latest.status === 'cancelled') ? latest : null)
    } catch {
      /* non-critical */
    }
  }, [id])

  useEffect(() => {
    setProject(null)
    setLastTask(null)
    void load().then(checkLastTask)
  }, [load, checkLastTask])

  // Keep the title draft in sync unless the user is editing it.
  useEffect(() => {
    if (project && !titleFocused.current) setTitleDraft(project.title)
  }, [project])

  // Poll while a task is active; when it ends, refetch once more and surface failures.
  const activeTaskId = project?.active_task?.id ?? null
  const prevActive = useRef<string | null>(null)
  useEffect(() => {
    if (!activeTaskId) {
      if (prevActive.current) {
        prevActive.current = null
        void load(true).then(checkLastTask)
      }
      return
    }
    prevActive.current = activeTaskId
    const timer = window.setInterval(() => void load(true), POLL_MS)
    return () => window.clearInterval(timer)
  }, [activeTaskId, load, checkLastTask])

  const busy = !!project?.active_task

  const startTask = async (fn: () => Promise<Task>) => {
    try {
      const task = await fn()
      setLastTask(null)
      setProject((p) => (p ? { ...p, active_task: task } : p))
      toast.success(t('task_started'))
      void load(true)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) toast.error(t('task_busy'))
      else toast.error(errorMessage(e))
    }
  }

  const onCancel = async () => {
    if (!project?.active_task) return
    setCancelling(true)
    try {
      await cancelTask(project.active_task.id)
      await load(true)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setCancelling(false)
    }
  }

  const commitTitle = async () => {
    titleFocused.current = false
    if (!project) return
    const next = titleDraft.trim()
    if (next === project.title || !next) {
      setTitleDraft(project.title)
      return
    }
    try {
      setProject(await patchProject(project.id, { title: next }))
      toast.success(t('title_saved'))
    } catch (e) {
      toast.error(errorMessage(e))
      setTitleDraft(project.title)
    }
  }

  const sceneActions: SceneActions = {
    patch: async (sceneId, body: ScenePatch) => {
      try {
        setProject(await patchScene(id, sceneId, body))
        return true
      } catch (e) {
        toast.error(errorMessage(e))
        return false
      }
    },
    regenerate: (sceneId, kinds: AssetKind[] | null) =>
      startTask(() => generateAssets(id, { scene_ids: [sceneId], kinds, force: true })),
    upload: async (sceneId, kind: UploadKind, file) => {
      try {
        setProject(await uploadSceneAsset(id, sceneId, kind, file))
        toast.success(t('uploaded'))
      } catch (e) {
        toast.error(errorMessage(e))
      }
    },
    addBelow: async (sceneId) => {
      try {
        setProject(await addScene(id, { after: sceneId, narration: '', image_prompt: '' }))
      } catch (e) {
        toast.error(errorMessage(e))
      }
    },
    remove: (sceneId) => setPendingDeleteScene(sceneId),
    move: async (sceneId, dir) => {
      if (!project) return
      const ids = project.scenes.map((s) => s.id)
      const i = ids.indexOf(sceneId)
      const j = i + dir
      if (i < 0 || j < 0 || j >= ids.length) return
      ;[ids[i], ids[j]] = [ids[j], ids[i]]
      try {
        setProject(await reorderScenes(id, ids))
      } catch (e) {
        toast.error(errorMessage(e))
      }
    },
  }

  const confirmDeleteScene = async () => {
    if (!pendingDeleteScene) return
    setDeletingScene(true)
    try {
      setProject(await deleteScene(id, pendingDeleteScene))
      setPendingDeleteScene(null)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setDeletingScene(false)
    }
  }

  const addSceneAtEnd = async () => {
    if (!project) return
    const last = project.scenes[project.scenes.length - 1]
    try {
      setProject(await addScene(id, { after: last?.id ?? null, narration: '', image_prompt: '' }))
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  if (notFound) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorAlert message={t('project_not_found')} />
      </div>
    )
  }
  if (loadError && !project) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorAlert message={loadError} onRetry={() => void load()} />
      </div>
    )
  }
  if (!project) {
    return (
      <div className="space-y-6">
        <BackLink />
        <Skeleton className="h-16" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-4">
            <Skeleton className="h-52" />
            <Skeleton className="h-52" />
          </div>
          <Skeleton className="h-96" />
        </div>
      </div>
    )
  }

  const hasScenes = project.scenes.length > 0
  const characterSource = parent?.characters.length ? parent.characters : project.characters
  const speakers = characterSource.length > 0 ? characterSource.map((c) => c.name).filter(Boolean) : null
  const reviewByScene = new Map(project.review?.scenes.map((r) => [r.scene_id, r]) ?? [])

  return (
    <div>
      <StudioHeader
        project={project}
        busy={busy}
        titleDraft={titleDraft}
        titleFocused={titleFocused}
        onTitleChange={setTitleDraft}
        onTitleCommit={() => void commitTitle()}
        onScript={() => (hasScenes ? setConfirmScript(true) : void startTask(() => generateScript(id)))}
        onAssets={() => void startTask(() => generateAssets(id, { scene_ids: null, kinds: null, force: false }))}
        onRender={() => void startTask(() => renderProject(id))}
        onReview={() => void startTask(() => reviewProject(id))}
        onAll={() => void startTask(() => generateAll(id))}
      />

      {project.active_task && <TaskBar task={project.active_task} onCancel={() => void onCancel()} cancelling={cancelling} />}

      {lastTask && !project.active_task && (
        <div className="relative mb-6">
          <ErrorAlert
            title={lastTask.status === 'failed' ? t('task_failed_title') : t('task_cancelled_title')}
            message={`${t(`task_type_${lastTask.type}` as const)}${lastTask.error ? ` — ${lastTask.error}` : ''}`}
            className="pr-10"
          />
          <button
            type="button"
            className="absolute top-2.5 right-2.5 rounded p-1 text-danger/70 hover:text-danger"
            onClick={() => setLastTask(null)}
            aria-label={t('close')}
          >
            <X size={14} />
          </button>
        </div>
      )}
      {loadError && <ErrorAlert message={loadError} className="mb-6" />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        {/* Storyboard */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold">
              {t('storyboard')}
              <span className="ml-2 text-sm font-normal text-muted">{t('scene_count', { n: project.scenes.length })}</span>
            </h2>
            <div className="flex items-center gap-1">
              {project.scenes.some((s) => s.image_url) && (
                <a className="btn-ghost btn-sm" href={`/api/projects/${project.id}/scenes/images.zip`} download>
                  <Download size={14} />
                  {t('download_all_images')}
                </a>
              )}
              <button type="button" className="btn-ghost btn-sm" disabled={busy} onClick={() => void addSceneAtEnd()}>
                <Plus size={14} />
                {t('add_scene')}
              </button>
            </div>
          </div>

          {hasScenes ? (
            <div className="space-y-3">
              {project.scenes.map((scene, i) => (
                <SceneCard
                  key={scene.id}
                  scene={scene}
                  index={i}
                  total={project.scenes.length}
                  aspect={project.aspect_ratio}
                  busy={busy}
                  actions={sceneActions}
                  contentMode={project.content_mode}
                  speakers={speakers}
                  motion={project.motion}
                  review={reviewByScene.get(scene.id) ?? null}
                />
              ))}
            </div>
          ) : (
            <div className="card flex flex-col items-center px-6 py-14 text-center">
              <span className="grid h-12 w-12 place-items-center rounded-2xl bg-accent/15 text-accent">
                <FileText size={22} />
              </span>
              <h3 className="mt-3 font-semibold">{t('scenes_empty')}</h3>
              <p className="mt-1 max-w-sm text-sm text-muted">{t('scenes_empty_hint')}</p>
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4 self-start lg:sticky lg:top-20">
          <PreviewPanel project={project} />
          {project.review && (
            <ReviewPanel
              project={project}
              busy={busy}
              actions={sceneActions}
              onReview={() => void startTask(() => reviewProject(id))}
              onProject={setProject}
            />
          )}
          {resources ? (
            <StudioSettings project={project} resources={resources} disabled={busy} onProject={setProject} />
          ) : resourcesError ? (
            <ErrorAlert message={resourcesError} onRetry={() => void reloadResources()} />
          ) : (
            <Skeleton className="h-80" />
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmScript}
        title={t('gen_script')}
        message={t('gen_script_confirm')}
        onCancel={() => setConfirmScript(false)}
        onConfirm={() => {
          setConfirmScript(false)
          void startTask(() => generateScript(id))
        }}
      />
      <ConfirmDialog
        open={pendingDeleteScene !== null}
        danger
        busy={deletingScene}
        title={t('delete_scene')}
        message={t('delete_scene_confirm')}
        confirmLabel={t('delete')}
        onCancel={() => !deletingScene && setPendingDeleteScene(null)}
        onConfirm={() => void confirmDeleteScene()}
      />
    </div>
  )
}
