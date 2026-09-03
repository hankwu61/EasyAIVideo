import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { X } from 'lucide-react'
import {
  ApiError,
  analyzeProject,
  cancelTask,
  createEpisode,
  errorMessage,
  generateAllEpisodes,
  generateCharacterImage,
  generateEpisode,
  getProject,
  listTasks,
  patchProject,
  planEpisodes,
} from '../api'
import ConfirmDialog from '../components/ConfirmDialog'
import CharactersSection from '../components/series/CharactersSection'
import EpisodesSection, { type EpisodeActions } from '../components/series/EpisodesSection'
import LocationsSection from '../components/series/LocationsSection'
import OverviewSection from '../components/series/OverviewSection'
import SeriesHeader from '../components/series/SeriesHeader'
import SourceSection from '../components/series/SourceSection'
import { BackLink } from '../components/StudioHeader'
import TaskBar from '../components/TaskBar'
import { useToast } from '../components/Toast'
import { ErrorAlert, Skeleton } from '../components/ui'
import { useResources } from '../hooks/useResources'
import { useLang } from '../i18n'
import type { Project, Task } from '../types'

const POLL_MS = 2000

export default function SeriesPage() {
  const { id = '' } = useParams()
  const { t } = useLang()
  const toast = useToast()
  const { resources } = useResources()

  const [project, setProject] = useState<Project | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [lastTask, setLastTask] = useState<Task | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const [generatingAll, setGeneratingAll] = useState(false)
  const [confirm, setConfirm] = useState<'analyze' | 'plan' | null>(null)

  const [titleDraft, setTitleDraft] = useState('')
  const titleFocused = useRef(false)

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

  useEffect(() => {
    if (project && !titleFocused.current) setTitleDraft(project.title)
  }, [project])

  // Poll while the series or any episode is working; refetch once more when it all stops.
  const polling = !!project && (!!project.active_task || project.episodes.some((e) => e.task_status !== null))
  const wasPolling = useRef(false)
  useEffect(() => {
    if (!polling) {
      if (wasPolling.current) {
        wasPolling.current = false
        void load(true).then(checkLastTask)
      }
      return
    }
    wasPolling.current = true
    const timer = window.setInterval(() => void load(true), POLL_MS)
    return () => window.clearInterval(timer)
  }, [polling, load, checkLastTask])

  const busy = !!project?.active_task

  const onApiError = (e: unknown) => {
    if (e instanceof ApiError && e.status === 409) toast.error(t('task_busy'))
    else toast.error(errorMessage(e))
  }

  const startTask = async (fn: () => Promise<Task>): Promise<boolean> => {
    try {
      const task = await fn()
      setLastTask(null)
      setProject((p) => (p ? { ...p, active_task: task } : p))
      toast.success(t('task_started'))
      void load(true)
      return true
    } catch (e) {
      onApiError(e)
      return false
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

  const onGenerateAll = async () => {
    setGeneratingAll(true)
    try {
      const tasks = await generateAllEpisodes(id)
      if (tasks.length === 0) toast.info(t('episodes_none_queued'))
      else toast.success(t('episodes_queued', { n: tasks.length }))
      setProject((p) =>
        p
          ? {
              ...p,
              episodes: p.episodes.map((e) =>
                tasks.some((tk) => tk.project_id === e.project_id) ? { ...e, task_status: 'queued' } : e,
              ),
            }
          : p,
      )
      await load(true)
    } catch (e) {
      onApiError(e)
    } finally {
      setGeneratingAll(false)
    }
  }

  const episodeActions: EpisodeActions = {
    generate: async (index) => {
      try {
        await generateEpisode(id, index)
        toast.success(t('task_started'))
        // Optimistic: keep polling until the next fetch reflects the queued task.
        setProject((p) =>
          p ? { ...p, episodes: p.episodes.map((e) => (e.index === index ? { ...e, task_status: 'queued' } : e)) } : p,
        )
        await load(true)
      } catch (e) {
        onApiError(e)
      }
    },
    create: async (index) => {
      try {
        setProject(await createEpisode(id, index))
        toast.success(t('episode_created'))
      } catch (e) {
        onApiError(e)
      }
    },
  }

  if (notFound) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorAlert message={t('series_not_found')} />
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
      <div className="mx-auto max-w-[1200px] space-y-6">
        <BackLink />
        <Skeleton className="h-24" />
        <Skeleton className="h-40" />
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1200px]">
      <SeriesHeader
        project={project}
        busy={busy}
        generatingAll={generatingAll}
        titleDraft={titleDraft}
        titleFocused={titleFocused}
        onTitleChange={setTitleDraft}
        onTitleCommit={() => void commitTitle()}
        onAnalyze={() =>
          project.characters.length > 0 ? setConfirm('analyze') : void startTask(() => analyzeProject(id))
        }
        onPlan={() => (project.episodes.length > 0 ? setConfirm('plan') : void startTask(() => planEpisodes(id)))}
        onGenerateAll={() => void onGenerateAll()}
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

      <div className="space-y-6">
        <SourceSection project={project} busy={busy} onProject={setProject} />
        <OverviewSection project={project} disabled={busy} onProject={setProject} />
        <CharactersSection
          project={project}
          voices={resources?.voices ?? []}
          busy={busy}
          onProject={setProject}
          onGenerateImage={(charId) => startTask(() => generateCharacterImage(id, charId))}
        />
        <LocationsSection project={project} disabled={busy} onProject={setProject} />
        <EpisodesSection project={project} onProject={setProject} actions={episodeActions} />
      </div>

      <ConfirmDialog
        open={confirm === 'analyze'}
        title={t('analyze')}
        message={t('analyze_confirm')}
        onCancel={() => setConfirm(null)}
        onConfirm={() => {
          setConfirm(null)
          void startTask(() => analyzeProject(id))
        }}
      />
      <ConfirmDialog
        open={confirm === 'plan'}
        title={t('plan_episodes')}
        message={t('plan_confirm')}
        onCancel={() => setConfirm(null)}
        onConfirm={() => {
          setConfirm(null)
          void startTask(() => planEpisodes(id))
        }}
      />
    </div>
  )
}
