"""Pydantic data models shared by storage, pipeline and API."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

InputMode = Literal["topic", "script", "novel", "slide", "prompt", "video"]
AspectRatio = Literal["9:16", "16:9", "1:1"]
Motion = Literal["kenburns", "static", "ai_video"]
ProjectStatus = Literal["draft", "scripted", "assets_ready", "rendered"]
SceneStatus = Literal["pending", "partial", "ready", "failed"]
TaskType = Literal["script", "assets", "render", "full", "analyze", "plan", "character_image", "review", "publish", "h3_generate"]
H3Mode = Literal["ref2va", "t2va", "i2va", "fl2va"]
H3SegmentStatus = Literal["pending", "generating", "done", "failed"]
TaskStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
AssetKind = Literal["audio", "image", "end_image", "video"]
Kind = Literal["single", "series", "episode"]
VideoMode = Literal["i2v", "t2v", "keyframes"]
ContentMode = Literal["narration", "drama"]
Gender = Literal["female", "male", "other"]
PublishPlatform = Literal["youtube", "tiktok", "webhook"]
PublishStatus = Literal["idle", "scheduled", "publishing", "published", "failed"]
PublishPrivacy = Literal["public", "unlisted", "private"]
SubtitlePosition = Literal["bottom", "middle", "top"]
TransitionEffect = Literal[
    "none",
    "fade",
    "dissolve",
    "wipeleft",
    "wiperight",
    "slideup",
    "slidedown",
    "circlecrop",
]

ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def _url(path: Optional[str]) -> Optional[str]:
    return f"/api/files/{path}" if path else None


class Line(BaseModel):
    """One spoken line inside a drama scene. speaker=None means the narrator."""

    speaker: Optional[str] = None
    text: str = ""
    duration: Optional[float] = None


class BoundAsset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("asset"))
    kind: Literal["character", "location", "prop"]
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    image_path: Optional[str] = None

    @computed_field
    @property
    def image_url(self) -> Optional[str]:
        return _url(self.image_path)


class MediaVersion(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ver"))
    kind: Literal["image", "end_image", "video"]
    path: str
    created_at: str = Field(default_factory=now_iso)

    @computed_field
    @property
    def url(self) -> Optional[str]:
        return _url(self.path)


class StagePosition(BaseModel):
    character_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    x: float = Field(50, ge=0, le=100, allow_inf_nan=False)
    y: float = Field(50, ge=0, le=100, allow_inf_nan=False)
    facing: float = Field(0, ge=0, lt=360, allow_inf_nan=False)


class Scene(BaseModel):
    id: str
    index: int = 0
    group: str = ""
    stage_positions: list[StagePosition] = Field(default_factory=list, max_length=30)
    asset_bindings: list[BoundAsset] = Field(default_factory=list)
    media_history: list[MediaVersion] = Field(default_factory=list)
    narration: str = ""
    image_prompt: str = ""
    end_image_prompt: str = ""  # prompt for the scene's ending frame
    video_prompt: str = ""  # motion / camera description for AI video providers (optional)
    lines: list[Line] = Field(default_factory=list)
    location: Optional[str] = None
    # Paths are relative to the projects directory and start with the project id,
    # e.g. "proj_ab12/scenes/s01/audio.mp3".
    audio_path: Optional[str] = None
    image_path: Optional[str] = None
    end_image_path: Optional[str] = None
    video_path: Optional[str] = None
    segment_path: Optional[str] = None
    duration: Optional[float] = None
    tts_speed: Optional[float] = None
    status: SceneStatus = "pending"
    audio_stale: bool = False
    image_stale: bool = False
    end_image_stale: bool = False
    video_stale: bool = False
    error: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def audio_url(self) -> Optional[str]:
        return _url(self.audio_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_url(self) -> Optional[str]:
        return _url(self.image_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def end_image_url(self) -> Optional[str]:
        return _url(self.end_image_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def video_url(self) -> Optional[str]:
        return _url(self.video_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def segment_url(self) -> Optional[str]:
        return _url(self.segment_path)

    def display_text(self) -> str:
        if self.lines:
            return "\n".join(f"{ln.speaker}：{ln.text}" if ln.speaker else ln.text for ln in self.lines if ln.text.strip())
        return self.narration


class Task(BaseModel):
    id: str
    project_id: str
    type: TaskType
    status: TaskStatus = "queued"
    progress: float = 0.0
    message: str = ""
    error: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    created_at: str = Field(default_factory=now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class H3Segment(BaseModel):
    """One <=15 s MiniMax H3 generation unit cut from the source video (video clone flow)."""

    index: int = 0
    start: float = 0.0  # source seconds
    end: float = 0.0
    duration: float = 0.0  # actual seconds kept after trimming the H3 output
    request_duration: int = 5  # integer seconds sent to H3 (4-15)
    reason: str = ""  # why the cut point was chosen (breath / breath+cut / ...)
    prompt: str = ""  # ready-to-paste English H3 prompt (segment-local clock)
    hand_off_state: str = ""
    shots: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Paths are relative to the projects directory
    ref_video_path: Optional[str] = None
    ref_audio_path: Optional[str] = None
    first_frame_path: Optional[str] = None
    last_frame_path: Optional[str] = None
    sheet_paths: list[str] = Field(default_factory=list)
    clip_path: Optional[str] = None
    status: H3SegmentStatus = "pending"
    error: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def prompt_chars(self) -> int:
        return len(self.prompt)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def clip_url(self) -> Optional[str]:
        return _url(self.clip_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ref_video_url(self) -> Optional[str]:
        return _url(self.ref_video_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def first_frame_url(self) -> Optional[str]:
        return _url(self.first_frame_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sheet_urls(self) -> list[str]:
        return [u for u in (_url(p) for p in self.sheet_paths) if u]


class Character(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    appearance: str = ""
    gender: Gender = "other"
    voice: str = ""
    image_path: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def image_url(self) -> Optional[str]:
        return _url(self.image_path)


class Location(BaseModel):
    name: str = ""
    description: str = ""


class Overview(BaseModel):
    synopsis: str = ""
    genre: str = ""
    theme: str = ""
    world_setting: str = ""


class SourceFile(BaseModel):
    name: str
    chars: int = 0


class Episode(BaseModel):
    index: int
    title: str = ""
    summary: str = ""
    source_start: int = 0
    source_end: int = 0
    project_id: Optional[str] = None
    # Runtime fields filled from the child project when the series is read.
    status: str = "planned"
    progress: Optional[float] = None
    task_message: Optional[str] = None
    task_status: Optional[str] = None
    final_video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    scene_count: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def chars(self) -> int:
        return max(self.source_end - self.source_start, 0)


class SceneReview(BaseModel):
    scene_id: str
    index: int = 0
    score: int = Field(3, ge=1, le=5)  # 5 = visuals fully match the narration
    match: bool = True
    issues: list[str] = Field(default_factory=list)
    suggested_image_prompt: str = ""
    note: str = ""
    frame_paths: list[str] = Field(default_factory=list)
    error: Optional[str] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def frame_urls(self) -> list[str]:
        return [f"/api/files/{p}" for p in self.frame_paths]


class ProjectReview(BaseModel):
    created_at: str = Field(default_factory=now_iso)
    model: str = ""
    video_path: Optional[str] = None  # the final video that was reviewed
    summary: str = ""
    scenes: list[SceneReview] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def issue_count(self) -> int:
        return sum(len(s.issues) for s in self.scenes)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_score(self) -> float:
        scored = [s.score for s in self.scenes if not s.error]
        return round(sum(scored) / len(scored), 2) if scored else 0.0


class PublishRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("pub"))
    platform: PublishPlatform
    status: Literal["succeeded", "failed"] = "succeeded"
    video_id: Optional[str] = None
    url: Optional[str] = None
    title: str = ""
    scheduled_at: Optional[str] = None
    published_at: str = Field(default_factory=now_iso)
    error: Optional[str] = None


class ProjectPublishSettings(BaseModel):
    enabled: bool = False
    auto_publish: bool = False
    platforms: list[PublishPlatform] = Field(default_factory=lambda: ["youtube", "tiktok"])
    schedule_mode: Literal["immediate", "scheduled"] = "immediate"
    schedule_time: Optional[str] = None
    privacy: PublishPrivacy = "public"
    title_template: str = "{title} #Shorts"
    description_template: str = "{topic}\n\nCreated with EasyAIVideo\n#Shorts #TikTok"
    tags: list[str] = Field(default_factory=lambda: ["Shorts", "AI", "EasyAIVideo"])


class TemplateConfig(BaseModel):
    """The 5 key dimensions of a video template."""

    # 1. Style
    style_id: str = "cinematic"
    style_prompt: str = ""
    # 2. Font
    font_family: str = "msjh"
    font_size: int = 24
    # 3. Subtitle Position
    subtitle_position: SubtitlePosition = "bottom"
    # 4. Transition
    transition: TransitionEffect = "none"
    transition_duration: float = 0.5
    # 5. BGM
    bgm: Optional[str] = None
    bgm_volume: float = 0.2


class Template(BaseModel):
    id: str
    name: str
    description: str = ""
    category: str = "general"
    cover_color: Optional[str] = None
    icon: Optional[str] = None
    is_builtin: bool = False
    config: TemplateConfig = Field(default_factory=TemplateConfig)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    category: str = "custom"
    cover_color: Optional[str] = None
    icon: Optional[str] = None
    config: TemplateConfig


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    cover_color: Optional[str] = None
    icon: Optional[str] = None
    config: Optional[TemplateConfig] = None


class TemplateSharePayload(BaseModel):
    name: str
    description: str = ""
    category: str = "custom"
    cover_color: Optional[str] = None
    icon: Optional[str] = None
    config: TemplateConfig


class ProjectSettings(BaseModel):
    """Fields a user can edit after creation."""

    title: str = ""
    topic: str = ""
    input_mode: InputMode = "topic"
    language: str = "zh-TW"
    aspect_ratio: AspectRatio = "9:16"
    style_id: str = "cinematic"
    style_prompt: str = ""
    n_scenes: int = Field(6, ge=1, le=30)
    voice: str = "zh-TW-HsiaoChenNeural"
    tts_speed: float = Field(1.0, ge=0.5, le=2.0)
    bgm: Optional[str] = None
    bgm_volume: float = Field(0.2, ge=0.0, le=1.0)
    subtitle_enabled: bool = True
    subtitle_position: SubtitlePosition = "bottom"
    font_family: str = "msjh"
    font_size: int = Field(24, ge=12, le=72)
    show_title: bool = True
    transition: TransitionEffect = "none"
    transition_duration: float = Field(0.5, ge=0.1, le=2.0)
    template_id: Optional[str] = None
    motion: Motion = "kenburns"
    video_mode: Optional[VideoMode] = None  # None = use the system default (config.video.mode)
    content_mode: ContentMode = "narration"
    episode_target_seconds: int = Field(120, ge=30, le=600)
    publish_settings: ProjectPublishSettings = Field(default_factory=ProjectPublishSettings)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "publish_settings" and isinstance(value, dict):
            value = ProjectPublishSettings(**value)
        super().__setattr__(name, value)

    @field_validator("publish_settings", mode="before")
    @classmethod
    def _validate_publish_settings(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return ProjectPublishSettings(**v)
        return v


class Project(ProjectSettings):
    id: str
    kind: Kind = "single"
    parent_id: Optional[str] = None
    episode_index: Optional[int] = None
    status: ProjectStatus = "draft"
    scenes: list[Scene] = Field(default_factory=list)
    scene_counter: int = 0
    assets: list[BoundAsset] = Field(default_factory=list)
    final_video_path: Optional[str] = None
    final_video_duration: Optional[float] = None
    final_video_size: Optional[int] = None
    raw_video_path: Optional[str] = None
    subtitles_path: Optional[str] = None
    active_task: Optional[Task] = None
    # series data
    source_files: list[SourceFile] = Field(default_factory=list)
    source_chars: int = 0
    overview: Optional[Overview] = None
    characters: list[Character] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    episodes: list[Episode] = Field(default_factory=list)
    review: Optional[ProjectReview] = None
    h3_prompt: Optional[str] = None
    forensic_report: Optional[str] = None
    source_url: Optional[str] = None  # web page the cloned video was downloaded from (None = uploaded file)
    source_meta: dict[str, Any] = Field(default_factory=dict)  # title / uploader / extractor / duration ...
    h3_mode: H3Mode = "ref2va"
    h3_segments: list[H3Segment] = Field(default_factory=list)
    h3_use_ref_video: bool = True  # send the source segment as <Video 1>
    h3_use_ref_audio: bool = True  # send the source segment audio as <Audio 1> (copied narration)
    h3_reference_images: list[str] = Field(default_factory=list)  # <Picture 1..N> identity locks
    h3_subjects: str = ""  # shared subject_definitions text reused by every segment
    publish_status: PublishStatus = "idle"
    publish_records: list[PublishRecord] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def width(self) -> int:
        return ASPECT_SIZES[self.aspect_ratio][0]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def height(self) -> int:
        return ASPECT_SIZES[self.aspect_ratio][1]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def final_video_url(self) -> Optional[str]:
        return _url(self.final_video_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def raw_video_url(self) -> Optional[str]:
        return _url(self.raw_video_path or self.final_video_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def subtitles_url(self) -> Optional[str]:
        return _url(self.subtitles_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def thumbnail_url(self) -> Optional[str]:
        for scene in self.scenes:
            if scene.image_path:
                return _url(scene.image_path)
        for ch in self.characters:
            if ch.image_path:
                return _url(ch.image_path)
        return None

    # helpers -----------------------------------------------------------
    def scene_by_id(self, scene_id: str) -> Optional[Scene]:
        return next((s for s in self.scenes if s.id == scene_id), None)

    def next_scene_id(self) -> str:
        self.scene_counter += 1
        return f"s{self.scene_counter:02d}"

    def reindex(self) -> None:
        for i, scene in enumerate(self.scenes):
            scene.index = i

    def character_by_name(self, name: Optional[str]) -> Optional[Character]:
        if not name:
            return None
        return next((c for c in self.characters if c.name == name), None)

    def summary(self) -> dict[str, Any]:
        data = self.model_dump(mode="json", exclude={"scenes", "scene_counter", "episodes", "characters", "locations"})
        data["scene_count"] = len(self.scenes)
        data["episode_count"] = len(self.episodes)
        return data


# ---- API request bodies -------------------------------------------------


class ProjectCreate(ProjectSettings):
    topic: str = ""
    kind: Kind = "single"
    style_prompt: Optional[str] = None  # type: ignore[assignment]
    source_text: Optional[str] = None
    auto_start: bool = True


class QuickVideoRequest(BaseModel):
    """Request to generate a single video from a single prompt."""

    prompt: str
    title: Optional[str] = None
    aspect_ratio: AspectRatio = "16:9"
    duration: float = Field(5.0, ge=1.0, le=30.0)
    motion: Motion = "ai_video"
    video_mode: Optional[VideoMode] = "i2v"
    style_id: str = "cinematic"
    style_prompt: Optional[str] = None
    voice: Optional[str] = None
    with_narration: bool = False
    image_base64: Optional[str] = None
    end_image_base64: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    input_mode: Optional[InputMode] = None
    language: Optional[str] = None
    aspect_ratio: Optional[AspectRatio] = None
    style_id: Optional[str] = None
    style_prompt: Optional[str] = None
    n_scenes: Optional[int] = Field(None, ge=1, le=30)
    voice: Optional[str] = None
    tts_speed: Optional[float] = Field(None, ge=0.5, le=2.0)
    bgm: Optional[str] = None
    bgm_volume: Optional[float] = Field(None, ge=0.0, le=1.0)
    subtitle_enabled: Optional[bool] = None
    subtitle_position: Optional[SubtitlePosition] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = Field(None, ge=12, le=72)
    show_title: Optional[bool] = None
    transition: Optional[TransitionEffect] = None
    transition_duration: Optional[float] = Field(None, ge=0.1, le=2.0)
    template_id: Optional[str] = None
    motion: Optional[Motion] = None
    video_mode: Optional[VideoMode] = None
    content_mode: Optional[ContentMode] = None
    episode_target_seconds: Optional[int] = Field(None, ge=30, le=600)
    overview: Optional[Overview] = None
    characters: Optional[list[Character]] = None
    locations: Optional[list[Location]] = None
    publish_settings: Optional[ProjectPublishSettings] = None

    @field_validator("publish_settings", mode="before")
    @classmethod
    def _validate_publish_settings(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return ProjectPublishSettings(**v)
        return v


class PublishRequest(BaseModel):
    platforms: Optional[list[PublishPlatform]] = None
    schedule_time: Optional[str] = None
    auto_publish: Optional[bool] = None
    privacy: Optional[PublishPrivacy] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class SceneUpdate(BaseModel):
    stage_positions: Optional[list[StagePosition]] = Field(None, max_length=30)
    group: Optional[str] = Field(None, max_length=100)
    asset_ids: Optional[list[str]] = None
    narration: Optional[str] = None
    image_prompt: Optional[str] = None
    end_image_prompt: Optional[str] = None
    video_prompt: Optional[str] = None
    lines: Optional[list[Line]] = None
    tts_speed: Optional[float] = None


class SceneCreate(BaseModel):
    group: str = Field("", max_length=100)
    after: Optional[str] = None
    narration: str = ""
    image_prompt: str = ""
    end_image_prompt: str = ""


class SceneReorder(BaseModel):
    scene_ids: list[str]


class H3SegmentUpdate(BaseModel):
    prompt: Optional[str] = Field(None, max_length=20000)
    request_duration: Optional[int] = Field(None, ge=4, le=15)


class H3GenerateRequest(BaseModel):
    segment_indexes: Optional[list[int]] = None
    force: bool = False


class AssetsRequest(BaseModel):
    scene_ids: Optional[list[str]] = None
    kinds: Optional[list[AssetKind]] = None
    force: bool = False


class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None


class TestResult(BaseModel):
    ok: bool
    message: str
    elapsed_ms: int


class SubtitleCueModel(BaseModel):
    id: int
    start: float
    end: float
    text: str


class SubtitlesUpdateRequest(BaseModel):
    cues: list[SubtitleCueModel]


class BurnSubtitlesRequest(BaseModel):
    font_name: Optional[str] = None
    font_size: int = 22
    primary_color: str = "&H00FFFFFF"  # ASS format: &HAABBGGRR
    back_color: str = "&H80000000"     # translucent black or color
    border_style: int = 1              # 1 = outline, 3 = box
    outline: int = 2
    outline_color: str = "&H00000000"
    alignment: int = 2                 # ASS Alignment (2 = bottom-center, 5 = top-center, 8 = middle-center, etc.)
    margin_v: int = 35
    margin_l: int = 20



class TrimVideoRequest(BaseModel):
    start: float
    end: float


class SynthesizeCueRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    speed: Optional[float] = None

