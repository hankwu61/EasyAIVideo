import type {
  AssetsRequest,
  EpisodePatch,
  SourceText,
  BgmOption,
  Config,
  ConfigTestKind,
  ConfigTestResult,
  Health,
  Presets,
  Project,
  ProjectCreate,
  ProjectPatch,
  ProjectSummary,
  PublishRequest,
  QuickVideoRequest,
  SceneCreate,
  ScenePatch,
  StyleOption,
  Task,
  TaskListParams,
  Template,
  TemplateCreate,
  TemplateExportResult,
  TransitionOption,
  SubtitlePositionOption,
  FontOption,
  H3Segment,
  UploadKind,
  VoiceOption,
  Workflows,
  SubtitleCue,
  BurnSubtitlesOptions,
} from './types'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** Human-readable message for any thrown value. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail
  if (err instanceof Error) return err.message
  return String(err)
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON-serialisable request body. */
  json?: unknown
  form?: FormData
  signal?: AbortSignal
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let body: BodyInit | undefined
  if (opts.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(opts.json)
  } else if (opts.form) {
    body = opts.form
  }

  let res: Response
  try {
    res = await fetch(path, { method: opts.method ?? 'GET', headers, body, signal: opts.signal })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, 'Network error: unable to reach the server')
  }

  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`
    try {
      const data = (await res.json()) as { detail?: unknown }
      if (typeof data?.detail === 'string') detail = data.detail
      else if (data?.detail != null) detail = JSON.stringify(data.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail)
  }

  if (res.status === 204) return undefined as T
  const text = await res.text()
  return (text ? JSON.parse(text) : undefined) as T
}

// ---------- Health ----------
export const getHealth = (signal?: AbortSignal) => request<Health>('/api/health', { signal })

// ---------- Config ----------
export const getConfig = () => request<Config>('/api/config')
export const putConfig = (body: Partial<Config>) => request<Config>('/api/config', { method: 'PUT', json: body })
export const testConfig = (kind: ConfigTestKind) =>
  request<ConfigTestResult>(`/api/config/test/${kind}`, { method: 'POST' })

// ---------- Resources ----------
export const getPresets = () => request<Presets>('/api/resources/presets')
export const getStyles = () => request<StyleOption[]>('/api/resources/styles')
export const getVoices = () => request<VoiceOption[]>('/api/resources/voices')
export const getBgm = () => request<BgmOption[]>('/api/resources/bgm')
export const uploadBgm = (file: File) => {
  const form = new FormData()
  form.append('file', file, file.name)
  return request<BgmOption>('/api/resources/bgm/upload', { method: 'POST', form })
}
export const getWorkflows = () => request<Workflows>('/api/resources/workflows')

// ---------- Projects ----------
export const listProjects = (includeEpisodes = false) =>
  request<ProjectSummary[]>(`/api/projects${includeEpisodes ? '?include_episodes=true' : ''}`)
export const createProject = (body: ProjectCreate) => request<Project>('/api/projects', { method: 'POST', json: body })
export const createSlideProject = (form: FormData) =>
  request<Project>('/api/projects/slide', { method: 'POST', form })
export const createQuickVideo = (body: QuickVideoRequest) =>
  request<Project>('/api/projects/quick-video', { method: 'POST', json: body })
export const cloneVideoProject = (form: FormData) =>
  request<Project>('/api/projects/clone-video', { method: 'POST', form })
export const getProjectH3Prompt = (id: string) =>
  request<{ project_id: string; title: string; h3_prompt: string; forensic_report: string; h3_mode: string; segments: H3Segment[] }>(
    `/api/projects/${encodeURIComponent(id)}/h3-prompt`
  )
export const updateH3Segment = (id: string, index: number, body: { prompt?: string; request_duration?: number }) =>
  request<Project>(`/api/projects/${encodeURIComponent(id)}/h3-segments/${index}`, { method: 'PATCH', json: body })
export const generateH3Video = (id: string, body: { segment_indexes?: number[]; force?: boolean } = {}) =>
  request<Task>(`/api/projects/${encodeURIComponent(id)}/h3-generate`, { method: 'POST', json: body })
export const getProject = (id: string, signal?: AbortSignal) =>
  request<Project>(`/api/projects/${encodeURIComponent(id)}`, { signal })
export const patchProject = (id: string, body: ProjectPatch) =>
  request<Project>(`/api/projects/${encodeURIComponent(id)}`, { method: 'PATCH', json: body })
export const deleteProject = (id: string) =>
  request<void>(`/api/projects/${encodeURIComponent(id)}`, { method: 'DELETE' })

// ---------- Scenes ----------
export const patchScene = (projectId: string, sceneId: string, body: ScenePatch) =>
  request<Project>(`/api/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}`, {
    method: 'PATCH',
    json: body,
  })
export const addScene = (projectId: string, body: SceneCreate) =>
  request<Project>(`/api/projects/${encodeURIComponent(projectId)}/scenes`, { method: 'POST', json: body })
export const deleteScene = (projectId: string, sceneId: string) =>
  request<Project>(`/api/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}`, {
    method: 'DELETE',
  })
export const reorderScenes = (projectId: string, sceneIds: string[]) =>
  request<Project>(`/api/projects/${encodeURIComponent(projectId)}/scenes/reorder`, {
    method: 'POST',
    json: { scene_ids: sceneIds },
  })
export const uploadSceneAsset = (projectId: string, sceneId: string, kind: UploadKind, file: File) => {
  const form = new FormData()
  form.append('file', file, file.name)
  return request<Project>(
    `/api/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(sceneId)}/upload/${kind}`,
    { method: 'POST', form },
  )
}

// ---------- Generation ----------
export const generateScript = (projectId: string) =>
  request<Task>(`/api/projects/${encodeURIComponent(projectId)}/generate/script`, { method: 'POST' })
export const generateAssets = (projectId: string, body: AssetsRequest) =>
  request<Task>(`/api/projects/${encodeURIComponent(projectId)}/generate/assets`, { method: 'POST', json: body })
export const renderProject = (projectId: string) =>
  request<Task>(`/api/projects/${encodeURIComponent(projectId)}/render`, { method: 'POST' })
export const generateAll = (projectId: string) =>
  request<Task>(`/api/projects/${encodeURIComponent(projectId)}/generate/all`, { method: 'POST' })

// ---------- Series: source documents ----------
const proj = (id: string) => `/api/projects/${encodeURIComponent(id)}`

// ---------- AI review ----------
export const reviewProject = (projectId: string) => request<Task>(`${proj(projectId)}/review`, { method: 'POST' })
export const clearReview = (projectId: string) => request<Project>(`${proj(projectId)}/review`, { method: 'DELETE' })

// ---------- Publishing ----------
export const publishProject = (projectId: string, body?: PublishRequest) =>
  request<Task>(`${proj(projectId)}/publish`, { method: 'POST', json: body })
export const cancelPublishSchedule = (projectId: string) =>
  request<Project>(`${proj(projectId)}/publish/schedule`, { method: 'DELETE' })

export const uploadSource = (projectId: string, file: File) => {
  const form = new FormData()
  form.append('file', file, file.name)
  return request<Project>(`${proj(projectId)}/source`, { method: 'POST', form })
}
export const getSource = (projectId: string, offset = 0, limit = 3000, signal?: AbortSignal) =>
  request<SourceText>(`${proj(projectId)}/source?offset=${offset}&limit=${limit}`, { signal })
export const clearSource = (projectId: string) => request<Project>(`${proj(projectId)}/source`, { method: 'DELETE' })

// ---------- Series: analysis / planning ----------
export const analyzeProject = (projectId: string) => request<Task>(`${proj(projectId)}/analyze`, { method: 'POST' })
export const planEpisodes = (projectId: string) =>
  request<Task>(`${proj(projectId)}/plan-episodes`, { method: 'POST' })
export const generateCharacterImage = (projectId: string, charId: string) =>
  request<Task>(`${proj(projectId)}/characters/${encodeURIComponent(charId)}/generate-image`, { method: 'POST' })

// ---------- Series: episodes ----------
export const updateEpisode = (projectId: string, index: number, body: EpisodePatch) =>
  request<Project>(`${proj(projectId)}/episodes/${index}`, { method: 'PATCH', json: body })
export const createEpisode = (projectId: string, index: number) =>
  request<Project>(`${proj(projectId)}/episodes/${index}/create`, { method: 'POST' })
export const generateEpisode = (projectId: string, index: number) =>
  request<Task>(`${proj(projectId)}/episodes/${index}/generate`, { method: 'POST' })
export const generateAllEpisodes = (projectId: string) =>
  request<Task[]>(`${proj(projectId)}/episodes/generate-all`, { method: 'POST' })

// ---------- Tasks ----------
export const listTasks = (params: TaskListParams = {}) => {
  const qs = new URLSearchParams()
  if (params.project_id) qs.set('project_id', params.project_id)
  if (params.active !== undefined) qs.set('active', String(params.active))
  if (params.limit !== undefined) qs.set('limit', String(params.limit))
  const q = qs.toString()
  return request<Task[]>(`/api/tasks${q ? `?${q}` : ''}`)
}
export const getTask = (taskId: string) => request<Task>(`/api/tasks/${encodeURIComponent(taskId)}`)
export const cancelTask = (taskId: string) =>
  request<Task>(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' })

// ---------- Templates ----------
export const listTemplates = () => request<Template[]>('/api/templates')
export const getTemplate = (id: string) => request<Template>(`/api/templates/${encodeURIComponent(id)}`)
export const createTemplate = (body: TemplateCreate) =>
  request<Template>('/api/templates', { method: 'POST', json: body })
export const createTemplateFromProject = (projectId: string, body: TemplateCreate) =>
  request<Template>(`/api/templates/from-project/${encodeURIComponent(projectId)}`, { method: 'POST', json: body })
export const updateTemplate = (id: string, body: Partial<TemplateCreate>) =>
  request<Template>(`/api/templates/${encodeURIComponent(id)}`, { method: 'PUT', json: body })
export const deleteTemplate = (id: string) =>
  request<{ ok: boolean }>(`/api/templates/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const exportTemplate = (id: string) =>
  request<TemplateExportResult>(`/api/templates/${encodeURIComponent(id)}/export`)
export const importTemplate = (body: { data?: string; template?: unknown }) =>
  request<Template>('/api/templates/import', { method: 'POST', json: body })

export const getTransitions = () => request<TransitionOption[]>('/api/resources/transitions')
export const getSubtitlePositions = () => request<SubtitlePositionOption[]>('/api/resources/subtitle-positions')
export const getFonts = () => request<FontOption[]>('/api/resources/fonts')

// ---------- Subtitles & Video Editing Studio ----------
export const getProjectSubtitles = (projectId: string) =>
  request<SubtitleCue[]>(`/api/projects/${encodeURIComponent(projectId)}/subtitles`)

export const updateProjectSubtitles = (projectId: string, cues: SubtitleCue[]) =>
  request<SubtitleCue[]>(`/api/projects/${encodeURIComponent(projectId)}/subtitles`, {
    method: 'PUT',
    json: { cues },
  })

export const burnProjectSubtitles = (projectId: string, options: BurnSubtitlesOptions = {}) =>
  request<{ ok: boolean; burned_video_url: string; final_video_url: string }>(
    `/api/projects/${encodeURIComponent(projectId)}/burn-subtitles`,
    {
      method: 'POST',
      json: options,
    },
  )

export const trimProjectVideo = (projectId: string, start: number, end: number) =>
  request<{ ok: boolean; trimmed_video_url: string; duration: number }>(
    `/api/projects/${encodeURIComponent(projectId)}/trim-video`,
    {
      method: 'POST',
      json: { start, end },
    },
  )

export const synthesizeCue = (projectId: string, text: string, voice?: string, speed?: number) =>
  request<{ ok: boolean; audio_url: string; duration: number }>(
    `/api/projects/${encodeURIComponent(projectId)}/synthesize-cue`,
    {
      method: 'POST',
      json: { text, voice, speed },
    },
  )


export const getAssetLibrary = (id: string) => request<import('./types').BoundAsset[]>(`/api/projects/${id}/asset-library`)
export const addLibraryAsset = (id: string, form: FormData) => request<import('./types').BoundAsset[]>(`/api/projects/${id}/asset-library`, {method: 'POST', form})
export const selectMediaVersion = (id: string, sceneId: string, versionId: string) => request<Project>(`/api/projects/${id}/scenes/${sceneId}/versions/${versionId}`, {method: 'POST'})
