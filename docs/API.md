# EasyAIVideo REST API Contract

Base URL: `http://localhost:8000`. All JSON endpoints live under `/api`. The built frontend
(`frontend/dist`) is served at `/` by the same server. Media files are served at
`/api/files/{project_id}/{relative_path}`; the API returns them as `*_url` fields that are already
absolute paths such as `/api/files/proj_ab12/scenes/s01/image.png`.

All timestamps are ISO-8601 strings. IDs: projects `proj_xxxxxxxx`, scenes `s01`, `s02`..., tasks `task_xxxxxxxx`.

Errors: non-2xx responses have body `{"detail": "<human readable message>"}`.

---

## Health

`GET /api/health` → `{ "status": "ok", "version": "0.1.0", "ffmpeg": true, "config_valid": true, "warnings": ["..."] }`

## Config (settings page)

`GET /api/config` → the full `Config` object. Secret fields (`api_key`) are returned masked as `"***"` when set, `""` when empty.

`PUT /api/config` body: partial `Config` (deep-merged). Sending `"***"` for a secret keeps the stored value. Returns the merged (masked) `Config`.

`POST /api/config/test/{kind}` where kind is one of `llm`, `tts`, `image`, `comfyui`
→ `{ "ok": true, "message": "Connected: gpt-4o-mini", "elapsed_ms": 812 }` (HTTP 200 even on failure, `ok=false` with message).

```jsonc
// Config
{
  "llm":   { "provider": "openai_compat" | "mock", "api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "temperature": 0.8 },
  "tts":   { "provider": "edge" | "openai_compat" | "silent", "voice": "zh-TW-HsiaoChenNeural", "speed": 1.0,
             "api_key": "", "base_url": "", "model": "tts-1" },
  "image": { "provider": "placeholder" | "openai_compat" | "comfyui", "api_key": "", "base_url": "", "model": "dall-e-3",
             "size_portrait": "1024x1792", "size_landscape": "1792x1024", "size_square": "1024x1024",
             "comfyui_url": "http://127.0.0.1:8188", "comfyui_workflow": "image_default.json", "prompt_prefix": "", "negative_prompt": "" },
  "video": { "provider": "kenburns" | "comfyui", "comfyui_url": "http://127.0.0.1:8188", "comfyui_workflow": "video_default.json", "fps": 30 },
  "render": { "font_path": "", "subtitle_size": 56, "bgm_volume": 0.2, "crf": 23 }
}
```

## Resources (dropdown data)

`GET /api/resources/presets` →
```jsonc
{
  "aspect_ratios": [ {"id":"9:16","label":"直式 9:16 (1080×1920)","width":1080,"height":1920}, {"id":"16:9","label":"...","width":1920,"height":1080}, {"id":"1:1","label":"...","width":1080,"height":1080} ],
  "languages":     [ {"id":"zh-TW","label":"繁體中文"}, {"id":"zh-CN","label":"简体中文"}, {"id":"en","label":"English"}, {"id":"ja","label":"日本語"} ],
  "motions":       [ {"id":"kenburns","label":"Ken Burns 動態鏡頭"}, {"id":"static","label":"靜態圖片"}, {"id":"ai_video","label":"AI 影片生成"} ],
  "input_modes":   [ {"id":"topic","label":"輸入主題，AI 撰寫腳本"}, {"id":"script","label":"使用我的文稿（自動分段）"} ],
  "llm_presets":   [ {"id":"openai","label":"OpenAI","base_url":"https://api.openai.com/v1","model":"gpt-4o-mini"}, {"id":"deepseek","label":"DeepSeek","base_url":"https://api.deepseek.com","model":"deepseek-chat"}, {"id":"ollama","label":"Ollama (local)","base_url":"http://localhost:11434/v1","model":"llama3.2"} ]
}
```
`GET /api/resources/styles` → `[ {"id":"cinematic","label":"電影感寫實","prompt":"cinematic photo, ..."}, {"id":"anime","label":"...","prompt":"..."}, ... ]`

`GET /api/resources/voices` → `[ {"id":"zh-TW-HsiaoChenNeural","name":"曉臻 (女)","locale":"zh-TW","gender":"Female"}, ... ]` (depends on `tts.provider`)

`GET /api/resources/bgm` → `[ {"name":"calm.mp3","url":"/api/files/_bgm/calm.mp3"} ]`

`GET /api/resources/workflows` → `{ "image": ["image_default.json"], "video": ["video_default.json"] }` (ComfyUI workflow files in `data/workflows/comfyui/`)

## Projects

```jsonc
// Project
{
  "id": "proj_1a2b3c4d",
  "title": "台灣夜市文化",
  "topic": "介紹台灣夜市文化的三個特色",     // topic text OR full script text depending on input_mode
  "input_mode": "topic" | "script",
  "language": "zh-TW",
  "aspect_ratio": "9:16",
  "width": 1080, "height": 1920,             // derived, read-only
  "style_id": "cinematic",
  "style_prompt": "cinematic photo, ...",    // editable, seeded from style_id
  "n_scenes": 6,
  "voice": "zh-TW-HsiaoChenNeural",
  "tts_speed": 1.0,
  "bgm": "calm.mp3" | null,
  "bgm_volume": 0.2,
  "subtitle_enabled": true,
  "show_title": true,
  "motion": "kenburns",
  "status": "draft" | "scripted" | "assets_ready" | "rendered",
  "scenes": [ Scene, ... ],
  "final_video_url": "/api/files/proj_1a2b3c4d/output/final.mp4" | null,
  "final_video_duration": 42.3 | null,
  "final_video_size": 12345678 | null,
  "thumbnail_url": "/api/files/proj_1a2b3c4d/scenes/s01/image.png" | null,
  "active_task": Task | null,                // the queued/running task for this project if any
  "created_at": "...", "updated_at": "..."
}

// Scene
{
  "id": "s01", "index": 0,
  "narration": "台灣夜市是...",
  "image_prompt": "a bustling Taiwanese night market at dusk, ...",
  "audio_url": "/api/files/.../scenes/s01/audio.mp3" | null,
  "image_url": "..." | null,
  "video_url": "..." | null,        // AI-generated clip (only when motion == ai_video)
  "segment_url": "..." | null,      // rendered segment with overlay + audio
  "duration": 5.8 | null,           // seconds (from audio)
  "status": "pending" | "partial" | "ready" | "failed",
  "audio_stale": false, "image_stale": false,   // true after text edits until regenerated
  "error": null | "message"
}

// ProjectSummary (list view) = Project without `scenes` but with "scene_count": 6
```

`GET /api/projects` → `[ProjectSummary]` newest first

`POST /api/projects` body:
```jsonc
{ "title": "", "topic": "...", "input_mode": "topic", "language": "zh-TW",
  "aspect_ratio": "9:16", "style_id": "cinematic", "style_prompt": null, "n_scenes": 6,
  "voice": "zh-TW-HsiaoChenNeural", "tts_speed": 1.0, "bgm": null, "bgm_volume": 0.2,
  "subtitle_enabled": true, "show_title": true, "motion": "kenburns",
  "auto_start": true }
```
`title` optional (auto-derived from topic). `style_prompt` optional override. If `auto_start` is true the server
immediately enqueues a `full` task (script → assets → render). → `Project` (201)

`GET /api/projects/{id}` → `Project`
`PATCH /api/projects/{id}` body: any subset of the editable settings (`title, topic, input_mode, language, aspect_ratio, style_id, style_prompt, n_scenes, voice, tts_speed, bgm, bgm_volume, subtitle_enabled, show_title, motion`) → `Project`
`DELETE /api/projects/{id}` → 204 (deletes files too)

### Scenes

`PATCH /api/projects/{id}/scenes/{scene_id}` body `{ "narration"?: "...", "image_prompt"?: "..." }` → `Project`. Changing `narration` sets `audio_stale=true`, changing `image_prompt` sets `image_stale=true`.
`POST /api/projects/{id}/scenes` body `{ "after": "s02" | null, "narration": "", "image_prompt": "" }` → `Project` (inserts and re-indexes; ids are re-assigned sequentially, so always re-read the returned project)
`DELETE /api/projects/{id}/scenes/{scene_id}` → `Project`
`POST /api/projects/{id}/scenes/reorder` body `{ "scene_ids": ["s03","s01","s02"] }` → `Project`
`POST /api/projects/{id}/scenes/{scene_id}/upload/{kind}` (kind is `image`, `audio` or `video`), multipart field `file` → `Project` (replaces the asset with the user's own file; clears the stale flag)

### Generation (all return `Task`, 202). Only one active task per project. A second request returns 409.

`POST /api/projects/{id}/generate/script` → writes or rewrites `scenes` from `topic` (LLM).
`POST /api/projects/{id}/generate/assets` body `{ "scene_ids": ["s01"] | null, "kinds": ["audio","image","video"] | null, "force": false }` → generates missing or stale assets (`null` = all).
`POST /api/projects/{id}/render` → renders every scene segment then the final video (requires all scenes to have audio + image).
`POST /api/projects/{id}/generate/all` → script (only if no scenes yet) → assets → render.

## Tasks

```jsonc
// Task
{ "id": "task_9f8e7d6c", "project_id": "proj_...", "type": "script" | "assets" | "render" | "full",
  "status": "queued" | "running" | "succeeded" | "failed" | "cancelled",
  "progress": 0.42, "message": "產生場景 3/6 的圖片…", "error": null,
  "created_at": "...", "started_at": null, "finished_at": null }
```
`GET /api/tasks?project_id=proj_...&active=true&limit=50` → `[Task]` newest first
`GET /api/tasks/{task_id}` → `Task`
`POST /api/tasks/{task_id}/cancel` → `Task`

Frontend polling guidance: while a project has `active_task`, poll `GET /api/projects/{id}` every 1500 ms (the response includes refreshed scenes and task progress). Otherwise no polling is needed.

## Files
`GET /api/files/{project_id}/{path}` → raw file (supports HTTP Range for video). `project_id` may be `_bgm` for background music files.

---

# Part 2: Long-form documents / novels → episodic videos (series)

A **series** project holds an imported document (novel, article, screenplay), its content analysis
(overview, characters, locations) and an episode plan. Each planned episode is materialised as a child
**episode** project that reuses the normal studio (scenes, assets, render). Ordinary projects have
`kind: "single"`.

## Project additions

```jsonc
// Project (all kinds) — new fields
{
  "kind": "single" | "series" | "episode",
  "content_mode": "narration" | "drama",     // narration = narrator reads/condenses the story; drama = characters speak their lines
  "parent_id": "proj_..." | null,            // episode → its series
  "episode_index": 1 | null,                 // episode → 1-based index in the series
  "source_files": [ {"name": "novel.txt", "chars": 123456} ],
  "source_chars": 123456,
  "overview": { "synopsis": "...", "genre": "...", "theme": "...", "world_setting": "..." } | null,
  "characters": [ Character, ... ],
  "locations": [ {"name": "金鑾大殿", "description": "..."} ],
  "episode_target_seconds": 120,
  "episodes": [ EpisodeSummary, ... ]        // series only; [] otherwise
}

// Character
{ "id": "c01", "name": "沈青鸞", "description": "女主角，聰慧冷靜的宮廷女官", 
  "appearance": "young East Asian woman, 20s, long black hair in a high bun, pale blue Hanfu robe, calm sharp eyes",  // English, used inside every image prompt
  "gender": "female" | "male" | "other", "voice": "zh-TW-HsiaoChenNeural", "image_url": "/api/files/..." | null }

// EpisodeSummary (inside a series project)
{ "index": 1, "title": "第 1 集：初入宮門", "summary": "...", "source_start": 0, "source_end": 5120, "chars": 5120,
  "project_id": "proj_..." | null,           // null until the episode project is created
  "status": "planned" | "draft" | "scripted" | "assets_ready" | "rendered" | "failed",
  "progress": 0.42 | null, "task_message": "..." | null, "task_status": "queued" | "running" | null,
  "final_video_url": "..." | null, "thumbnail_url": "..." | null, "scene_count": 8 }

// Scene — new fields (drama mode)
{ "lines": [ {"speaker": "沈青鸞" | null, "text": "陛下，臣有一事啟奏。", "duration": 2.4 | null} ],  // null speaker = narrator
  "location": "金鑾大殿" | null }
// In drama mode `narration` holds the read-only joined display text of the lines; edit `lines` instead.
```

`POST /api/projects` body additions: `kind` (default `single`), `content_mode` (default `narration`),
`episode_target_seconds` (default 120), `source_text` (optional pasted text for a series). For a series,
`topic` may be empty when a file is uploaded afterwards. `auto_start` on a series runs the `analyze` task
(the plan step is separate so the user can review characters first).

`PATCH /api/projects/{id}` additionally accepts `content_mode`, `episode_target_seconds`, `overview`,
`characters` (full replacement list; `id` optional for new characters, `image_url` ignored), `locations`.

`PATCH /api/projects/{id}/scenes/{scene_id}` additionally accepts `lines` (full list; marks audio stale).

`GET /api/projects?include_episodes=false` — episodes are hidden from the main list unless `include_episodes=true`.
`ProjectSummary` includes `kind`, `content_mode`, `episode_count`, `parent_id`, `episode_index`.

## Source documents (series)

`POST /api/projects/{id}/source` multipart `file` — accepts `.txt .md .docx .epub .pdf` (max 50 MB). Text is
extracted, normalised to UTF-8 and appended to the series source. → `Project`.
`GET /api/projects/{id}/source?offset=0&limit=20000` → `{ "text": "...", "total_chars": 123456, "offset": 0 }`
`DELETE /api/projects/{id}/source` → `Project` (clears all source text and files; also clears the episode plan)

## Analysis and planning (return `Task`, 202; 409 if the series already has an active task)

`POST /api/projects/{id}/analyze` → task type `analyze`: LLM writes `overview`, `characters` (with English `appearance` and an auto-picked `voice` by gender/language) and `locations`. Existing characters are replaced.
`POST /api/projects/{id}/plan-episodes` → task type `plan`: splits the source into episodes of roughly `episode_target_seconds` each (paragraph-aligned) and asks the LLM for titles + summaries. Replaces the plan; episode projects that were already created are kept if their index still exists, otherwise detached.
`POST /api/projects/{id}/characters/{char_id}/generate-image` → task type `character_image`: generates a portrait with the image provider from `appearance` + style.

`PATCH /api/projects/{id}/episodes/{index}` body `{ "title"?: "...", "summary"?: "..." }` → `Project`.

## Episode generation

`POST /api/projects/{id}/episodes/{index}/create` → `Project` (the series, refreshed). Creates the child episode project (inherits voice, style, aspect ratio, bgm, motion, subtitle settings; `topic` = the episode's source excerpt; `input_mode: "novel"`). No-op if it already exists.
`POST /api/projects/{id}/episodes/{index}/generate` → `Task` (202). Creates the child if needed and submits a `full` task on it (script → assets → render). 409 if that episode already has an active task.
`POST /api/projects/{id}/episodes/generate-all` → `[Task]` (202). Same for every episode that is not yet `rendered` and has no active task; they run one after another in the queue.

Episode projects use the normal studio routes (`/projects/{episode_project_id}`); their `parent_id` links back to the series. `POST /api/projects/{episode_id}/generate/script` regenerates the episode script from its excerpt using the series' characters and overview.

Task `type` gains: `analyze`, `plan`, `character_image`.

Frontend polling guidance for a series page: poll `GET /api/projects/{id}` every 2000 ms while the series has an `active_task` OR any episode has `task_status` non-null.

---

# Part 3: AI video generation (Agnes video, text-to-video / image-to-video / first+last frame)

`Config.video` gained provider `agnes` and these fields:
```jsonc
"video": { "provider": "kenburns" | "comfyui" | "agnes",
           "api_key": "", "base_url": "https://apihub.agnes-ai.com/v1", "model": "agnes-video-v2.0",
           "resolution": "480p" | "720p" | "1080p", "mode": "i2v" | "t2v" | "keyframes",
           "max_clip_seconds": 10, "concurrency": 1, "poll_timeout": 1800,
           "comfyui_url": "...", "comfyui_workflow": "...", "fps": 30 }
```
`Config.image` gained: `"size_mode": "preset" | "exact"` (exact = WxH computed from the project aspect ratio and
`"short_edge": 1024`, needed for Agnes image models), and `"use_references": false` (send character sheets as
image-to-image references in the `image` field; Agnes image models support this).

`POST /api/config/test/video` tests the configured video provider (kenburns returns ok with a note).

`GET /api/resources/presets` gained `"video_modes": [{"id":"i2v","label":"圖生影片（場景圖為首幀）"},{"id":"t2v","label":"文生影片（只用提示詞）"},{"id":"keyframes","label":"首尾幀（下一場景圖為尾幀）"}]`.

`Project` gained `"video_mode": "i2v" | "t2v" | "keyframes" | null` (null = use `Config.video.mode`); accepted by `POST /api/projects` and `PATCH /api/projects/{id}`. Only meaningful when `motion == "ai_video"`.

`Scene` gained `"video_prompt": "..."` (English motion / camera description used by AI video providers; the LLM fills it, the user may edit) and `"video_stale": false` (true after editing `video_prompt` or regenerating the image until the clip is regenerated). `PATCH /api/projects/{id}/scenes/{scene_id}` accepts `video_prompt`.

Asset generation with `motion == "ai_video"` now runs in two phases: audio + images for all scenes, then AI video clips (serialised by `Config.video.concurrency`). In `keyframes` mode the next scene's image is used as the last frame. Clips longer than `max_clip_seconds` are looped by the renderer to match the narration length.

---

# Part 4: Scene image update / upload / download

- **Regenerate one scene's image**: `POST /api/projects/{id}/generate/assets` with `{ "scene_ids": ["s03"], "kinds": ["image"], "force": true }` (existing). Add `"video"` to `kinds` to also redo the AI clip.
- **Upload your own image**: `POST /api/projects/{id}/scenes/{scene_id}/upload/image` multipart `file` (png/jpg/webp; existing). Clears `image_stale`; the AI clip (if any) becomes stale.
- **Download one file**: any `/api/files/...` URL accepts `?download=1` (original filename) or `?download=<name>` (custom filename, extension appended if missing) and responds with `Content-Disposition: attachment`.
- **Download all scene images**: `GET /api/projects/{id}/scenes/images.zip` → zip containing `scene01_image.png`, `scene02_image.png`, … plus `sceneNN_clip.mp4` for AI clips. 404 when the project has no images yet.
