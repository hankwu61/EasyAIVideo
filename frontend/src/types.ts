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

/** AI review (審片). Empty api_key / base_url / model fall back to `Config.llm`. */
export interface ReviewConfig {
  /** Secret; masked as "***" by the server. */
  api_key: string
  base_url: string
  model: string
  /** 1–3 */
  frames_per_scene: number
  frame_width: number
  /** 1–4 */
  concurrency: number
}

export type PublishPlatform = 'youtube' | 'tiktok' | 'webhook'
export type PublishStatus = 'idle' | 'scheduled' | 'publishing' | 'published' | 'failed'
export type PublishPrivacy = 'public' | 'unlisted' | 'private'

export interface YouTubeConfig {
  enabled: boolean
  mock: boolean
  client_id: string
  client_secret: string
  refresh_token: string
  default_privacy: PublishPrivacy
  default_tags: string
}

export interface TikTokConfig {
  enabled: boolean
  mock: boolean
  client_key: string
  client_secret: string
  access_token: string
  default_privacy: PublishPrivacy
  default_tags: string
}

export interface WebhookConfig {
  enabled: boolean
  url: string
  secret: string
}

export interface PublishConfig {
  youtube: YouTubeConfig
  tiktok: TikTokConfig
  webhook: WebhookConfig
}

export interface Config {
  llm: LlmConfig
  tts: TtsConfig
  image: ImageConfig
  video: VideoConfig
  render: RenderConfig
  review: ReviewConfig
  publish: PublishConfig
}

export type ConfigTestKind = 'llm' | 'tts' | 'image' | 'comfyui' | 'video' | 'review' | 'youtube' | 'tiktok' | 'webhook'

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
  transitions?: TransitionOption[]
  subtitle_positions?: SubtitlePositionOption[]
  fonts?: FontOption[]
}

export type SubtitlePosition = 'bottom' | 'middle' | 'top'
export type TransitionEffect = 'none' | 'fade' | 'dissolve' | 'wipeleft' | 'wiperight' | 'slideup' | 'slidedown' | 'circlecrop'

export interface TransitionOption {
  id: TransitionEffect
  label: string
  description?: string
}

export interface SubtitlePositionOption {
  id: SubtitlePosition
  label: string
  description?: string
}

export interface FontOption {
  id: string
  label: string
  family?: string
  description?: string
}

export interface TemplateConfig {
  style_id: string
  style_prompt: string
  font_family: string
  font_size: number
  subtitle_position: SubtitlePosition
  transition: TransitionEffect
  transition_duration: number
  bgm: string | null
  bgm_volume: number
}

export interface Template {
  id: string
  name: string
  description: string
  category: string
  cover_color: string | null
  icon: string | null
  is_builtin: boolean
  config: TemplateConfig
  created_at: string
  updated_at: string
}

export interface TemplateCreate {
  name: string
  description?: string
  category?: string
  cover_color?: string | null
  icon?: string | null
  config: TemplateConfig
}

export interface TemplateExportResult {
  filename: string
  data: {
    version: string
    type: string
    template: {
      name: string
      description: string
      category: string
      cover_color?: string | null
      icon?: string | null
      config: TemplateConfig
    }
  }
  share_code: string
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
  subtitle_position?: SubtitlePosition
  font_family?: string
  font_size?: number
  show_title: boolean
  transition?: TransitionEffect
  transition_duration?: number
  template_id?: string | null
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
  publish_settings: ProjectPublishSettings
  publish_status: PublishStatus
  publish_records: PublishRecord[]
  created_at: string
  updated_at: string
}

export interface PublishRecord {
  id: string
  platform: PublishPlatform
  status: 'succeeded' | 'failed'
  video_id: string | null
  url: string | null
  title: string
  scheduled_at: string | null
  published_at: string
  error: string | null
}

export interface ProjectPublishSettings {
  enabled: boolean
  auto_publish: boolean
  platforms: PublishPlatform[]
  schedule_mode: 'immediate' | 'scheduled'
  schedule_time: string | null
  privacy: PublishPrivacy
  title_template: string
  description_template: string
  tags: string[]
}

export interface PublishRequest {
  platforms?: PublishPlatform[]
  schedule_time?: string | null
  auto_publish?: boolean
  privacy?: PublishPrivacy
  title?: string
  description?: string
  tags?: string[]
}

// ---------- AI review ----------
export interface SceneReview {
  scene_id: string
  index: number
  /** 1–5 */
  score: number
  match: boolean
  issues: string[]
  /** Empty when the scene scored well. */
  suggested_image_prompt: string
  note: string
  frame_urls: string[]
  error: string | null
}

export interface ProjectReview {
  created_at: string
  model: string
  /** Relative path of the video that was reviewed; compare with `final_video_url` to detect staleness. */
  video_path: string
  summary: string
  issue_count: number
  average_score: number
  scenes: SceneReview[]
}

export interface Project extends ProjectBase {
  scenes: Scene[]
  /** Series only; [] otherwise. */
  episodes: Episode[]
  review: ProjectReview | null
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
  subtitle_position?: SubtitlePosition
  font_family?: string
  font_size?: number
  show_title: boolean
  transition?: TransitionEffect
  transition_duration?: number
  template_id?: string | null
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
    | 'subtitle_position'
    | 'font_family'
    | 'font_size'
    | 'show_title'
    | 'transition'
    | 'transition_duration'
    | 'template_id'
    | 'motion'
    | 'video_mode'
    | 'content_mode'
    | 'episode_target_seconds'
    | 'overview'
    | 'locations'
    | 'publish_settings'
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
export type TaskType = 'script' | 'assets' | 'render' | 'full' | 'analyze' | 'plan' | 'character_image' | 'review' | 'publish'
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
