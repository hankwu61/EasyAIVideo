// Types mirroring docs/API.md exactly.

// ---------- Health ----------
export interface Health {
  status: string
  version: string
  ffmpeg: boolean
  config_valid: boolean
  warnings: string[]
}

// ---------- Config ----------
export type LlmProvider = 'openai_compat' | 'mock'
export type TtsProvider = 'edge' | 'openai_compat' | 'silent'
export type ImageProvider = 'placeholder' | 'openai_compat' | 'comfyui'
export type VideoProvider = 'kenburns' | 'comfyui' | 'agnes'
export type VideoResolution = '480p' | '720p' | '1080p'
/** AI video generation mode: image-to-video, text-to-video, or first+last frame. */
export type VideoMode = 'i2v' | 't2v' | 'keyframes'
export type ImageSizeMode = 'preset' | 'exact'

export interface LlmConfig {
  provider: LlmProvider
  api_key: string
  base_url: string
  model: string
  temperature: number
}

export interface TtsConfig {
  provider: TtsProvider
  voice: string
  speed: number
  api_key: string
  base_url: string
  model: string
}

export interface ImageConfig {
  provider: ImageProvider
  api_key: string
  base_url: string
  model: string
  size_portrait: string
  size_landscape: string
  size_square: string
  /** exact = WxH computed from the project aspect ratio and `short_edge` (needed for Agnes image models). */
  size_mode: ImageSizeMode
  short_edge: number
  /** Send character sheets as image-to-image references. */
  use_references: boolean
  comfyui_url: string
  comfyui_workflow: string
  prompt_prefix: string
  negative_prompt: string
}

export interface VideoConfig {
  provider: VideoProvider
  /** Secret; masked as "***" by the server. */
  api_key: string
  base_url: string
  model: string
  resolution: VideoResolution
  mode: VideoMode
  /** 1–18 */
  max_clip_seconds: number
  /** 1–4 */
  concurrency: number
  poll_timeout: number
  comfyui_url: string
  comfyui_workflow: string
  fps: number
}

export interface RenderConfig {
  font_path: string
  subtitle_size: number
  bgm_volume: number
  crf: number
}

export interface Config {
  llm: LlmConfig
  tts: TtsConfig
  image: ImageConfig
  video: VideoConfig
  render: RenderConfig
}

export type ConfigTestKind = 'llm' | 'tts' | 'image' | 'comfyui' | 'video'

export interface ConfigTestResult {
  ok: boolean
  message: string
  elapsed_ms: number
}

// ---------- Resources ----------
export interface AspectRatioPreset {
  id: AspectRatio
  label: string
  width: number
  height: number
}

export interface IdLabel {
  id: string
  label: string
}

export interface LlmPreset {
  id: string
  label: string
  base_url: string
  model: string
}

export interface Presets {
  aspect_ratios: AspectRatioPreset[]
  languages: IdLabel[]
  motions: IdLabel[]
  input_modes: IdLabel[]
  llm_presets: LlmPreset[]
  /** Optional: older backends do not return these; the UI falls back to built-in lists. */
  content_modes?: IdLabel[]
  kinds?: IdLabel[]
  video_modes?: IdLabel[]
}

export interface StyleOption {
  id: string
  label: string
  prompt: string
}

export interface VoiceOption {
  id: string
  name: string
  locale: string
  gender: string
}

export interface BgmOption {
  name: string
  url: string
}

export interface Workflows {
  image: string[]
  video: string[]
}

// ---------- Projects ----------
export type AspectRatio = '9:16' | '16:9' | '1:1'
export type InputMode = 'topic' | 'script' | 'novel'
export type ProjectStatus = 'draft' | 'scripted' | 'assets_ready' | 'rendered'
export type SceneStatus = 'pending' | 'partial' | 'ready' | 'failed'
export type ProjectKind = 'single' | 'series' | 'episode'
export type ContentMode = 'narration' | 'drama'
export type CharacterGender = 'female' | 'male' | 'other'
export type EpisodeStatus = 'planned' | 'draft' | 'scripted' | 'assets_ready' | 'rendered' | 'failed'

/** One spoken line inside a drama scene. `speaker` null = narrator. */
export interface SceneLine {
  speaker: string | null
  text: string
  duration: number | null
}

export interface Character {
  id: string
  name: string
  description: string
  /** English, used inside every image prompt. */
  appearance: string
  gender: CharacterGender
  voice: string
  image_url: string | null
}

/** Character as sent in PATCH (id optional for new ones, image_url ignored by the server). */
export interface CharacterInput {
  id?: string
  name: string
  description: string
  appearance: string
  gender: CharacterGender
  voice: string
}

export interface Location {
  name: string
  description: string
}

export interface Overview {
  synopsis: string
  genre: string
  theme: string
  world_setting: string
}

export interface SourceFile {
  name: string
  chars: number
}

export interface SourceText {
  text: string
  total_chars: number
  offset: number
}

export interface Episode {
  index: number
  title: string
  summary: string
  source_start: number
  source_end: number
  chars: number
  project_id: string | null
  status: EpisodeStatus
  progress: number | null
  task_message: string | null
  task_status: 'queued' | 'running' | null
  final_video_url: string | null
  thumbnail_url: string | null
  scene_count: number
}

export interface EpisodePatch {
  title?: string
  summary?: string
}

export interface Scene {
  id: string
  index: number
  narration: string
  image_prompt: string
  lines: SceneLine[]
  location: string | null
  audio_url: string | null
  image_url: string | null
  video_url: string | null
  segment_url: string | null
  duration: number | null
  status: SceneStatus
  audio_stale: boolean
  image_stale: boolean
  /** English motion / camera description used by AI video providers. */
  video_prompt: string
  /** True after editing `video_prompt` or regenerating the image until the clip is regenerated. */
  video_stale: boolean
  error: string | null
}

export interface ProjectBase {
  id: string
  title: string
  topic: string
  input_mode: InputMode
  language: string
  aspect_ratio: AspectRatio
  width: number
  height: number
  style_id: string
  style_prompt: string
  n_scenes: number
  voice: string
  tts_speed: number
  bgm: string | null
  bgm_volume: number
  subtitle_enabled: boolean
  show_title: boolean
  motion: string
  /** null = use the system default (`Config.video.mode`). Only meaningful when motion == "ai_video". */
  video_mode: VideoMode | null
  kind: ProjectKind
  content_mode: ContentMode
  parent_id: string | null
  episode_index: number | null
  source_files: SourceFile[]
  source_chars: number
  overview: Overview | null
  characters: Character[]
  locations: Location[]
  episode_target_seconds: number
  status: ProjectStatus
  final_video_url: string | null
  final_video_duration: number | null
  final_video_size: number | null
  thumbnail_url: string | null
  active_task: Task | null
  created_at: string
  updated_at: string
}

export interface Project extends ProjectBase {
  scenes: Scene[]
  /** Series only; [] otherwise. */
  episodes: Episode[]
}

/** List view: no scenes / characters / locations / episodes. */
export interface ProjectSummary extends Omit<ProjectBase, 'characters' | 'locations'> {
  scene_count: number
  episode_count: number
}

export interface ProjectCreate {
  title?: string
  topic: string
  input_mode: InputMode
  language: string
  aspect_ratio: AspectRatio
  style_id: string
  style_prompt?: string | null
  n_scenes: number
  voice: string
  tts_speed: number
  bgm: string | null
  bgm_volume: number
  subtitle_enabled: boolean
  show_title: boolean
  motion: string
  video_mode?: VideoMode | null
  auto_start: boolean
  kind?: ProjectKind
  content_mode?: ContentMode
  episode_target_seconds?: number
  /** Pasted text for a series. */
  source_text?: string
}

export type ProjectPatch = Partial<
  Pick<
    ProjectBase,
    | 'title'
    | 'topic'
    | 'input_mode'
    | 'language'
    | 'aspect_ratio'
    | 'style_id'
    | 'style_prompt'
    | 'n_scenes'
    | 'voice'
    | 'tts_speed'
    | 'bgm'
    | 'bgm_volume'
    | 'subtitle_enabled'
    | 'show_title'
    | 'motion'
    | 'video_mode'
    | 'content_mode'
    | 'episode_target_seconds'
    | 'overview'
    | 'locations'
  >
> & {
  /** Full replacement list. */
  characters?: CharacterInput[]
}

export interface ScenePatch {
  narration?: string
  image_prompt?: string
  /** Marks the video clip stale. */
  video_prompt?: string
  /** Full list (drama mode); marks audio stale. */
  lines?: SceneLine[]
}

export interface SceneCreate {
  after: string | null
  narration: string
  image_prompt: string
}

export type AssetKind = 'audio' | 'image' | 'video'
export type UploadKind = 'image' | 'audio' | 'video'

export interface AssetsRequest {
  scene_ids: string[] | null
  kinds: AssetKind[] | null
  force: boolean
}

// ---------- Tasks ----------
export type TaskType = 'script' | 'assets' | 'render' | 'full' | 'analyze' | 'plan' | 'character_image'
export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface Task {
  id: string
  project_id: string
  type: TaskType
  status: TaskStatus
  progress: number
  message: string
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface TaskListParams {
  project_id?: string
  active?: boolean
  limit?: number
}
