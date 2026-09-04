# Day 06｜用 Claude Code 生成專案骨架：uv、config.yaml、設定頁與 launch.json

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 6 天

## 今日目標
- 跑起第一個 FastAPI 伺服器，有 `/api/health` 與 Swagger。
- 完成 `config.py`：讀 YAML、預設值、由 API 熱更新、金鑰遮罩。
- 設定 `.claude/launch.json`，讓 Claude Code 能自己啟動伺服器並用瀏覽器面板驗證。

## 安裝相依

```bash
uv add fastapi "uvicorn[standard]" pydantic pyyaml aiosqlite pillow python-multipart httpx edge-tts
```

## 設定檔

`config.example.yaml`：

```yaml
llm:
  provider: mock                 # openai_compat | mock
  api_key: ""
  base_url: "https://apihub.agnes-ai.com/v1"
  model: "agnes-2.0-flash"
  temperature: 0.8

tts:
  provider: edge                 # edge | silent
  voice: "zh-TW-HsiaoChenNeural"
  speed: 1.0

image:
  provider: placeholder          # openai_compat | placeholder
  api_key: ""
  base_url: "https://apihub.agnes-ai.com/v1"
  model: "agnes-image-2.0-flash"
  size_mode: exact               # exact = 依比例算 WxH（Agnes）；preset = 固定三種尺寸（DALL-E 類）
  short_edge: 1024
  use_references: true
  prompt_prefix: ""
  negative_prompt: "text, watermark, logo, blurry, low quality, deformed"

video:
  provider: kenburns             # kenburns | agnes
  api_key: ""
  base_url: "https://apihub.agnes-ai.com/v1"
  model: "agnes-video-v2.0"
  resolution: 720p               # 480p | 720p | 1080p
  mode: i2v                      # i2v | t2v | keyframes
  max_clip_seconds: 10           # 1–18
  concurrency: 1
  poll_timeout: 1800

render:
  font_path: ""
  subtitle_size: 56
  bgm_volume: 0.2
  crf: 23
  ffmpeg_path: ""
```

預設組合（mock + placeholder + edge + kenburns）不需要任何金鑰就能跑完整條管線，Edge-TTS 只要有網路。

## config.py 重點

```python
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("EASYAIVIDEO_CONFIG", ROOT / "config.yaml"))

class LLMConfig(BaseModel):
    provider: str = "mock"; api_key: str = ""; base_url: str = "https://apihub.agnes-ai.com/v1"
    model: str = "agnes-2.0-flash"; temperature: float = 0.8

class TTSConfig(BaseModel):
    provider: str = "edge"; voice: str = "zh-TW-HsiaoChenNeural"; speed: float = 1.0

class ImageConfig(BaseModel): ...
class VideoConfig(BaseModel): ...
class RenderConfig(BaseModel): ...

class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig(); tts: TTSConfig = TTSConfig(); image: ImageConfig = ImageConfig()
    video: VideoConfig = VideoConfig(); render: RenderConfig = RenderConfig()

    def masked(self) -> dict:
        d = self.model_dump()
        for sec in ("llm", "image", "video"):
            k = d[sec].get("api_key", "")
            d[sec]["api_key"] = f"****{k[-4:]}" if k else ""
        return d

class ConfigStore:
    def __init__(self):
        if not CONFIG_PATH.exists():
            shutil.copy(ROOT / "config.example.yaml", CONFIG_PATH)
        self.reload()
    def reload(self): ...
    def update(self, patch: dict):
        data = self.config.model_dump()
        for sec, vals in patch.items():
            # 前端送回遮罩值時不要覆蓋真實金鑰
            if str(vals.get("api_key", "")).startswith("****"):
                vals.pop("api_key")
            data.setdefault(sec, {}).update(vals)
        CONFIG_PATH.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return self.reload()
```

「遮罩值不覆蓋」是設定頁最容易踩的坑：使用者只改了模型名稱按儲存，結果金鑰被 `****abcd` 覆蓋。

「一把金鑰共用」：設定頁提供「同步 Agnes 金鑰到圖片／影片」按鈕，後端只是把 `llm.api_key` 複製到另外兩個區塊。

## main.py

```python
app = FastAPI(title="EasyAIVideo")

@app.get("/api/health")
async def health():
    c = store.config
    return {"ok": True, "llm": c.llm.provider, "image": c.image.provider, "tts": c.tts.provider, "video": c.video.provider}

def main():
    p = argparse.ArgumentParser(); p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(); uvicorn.run("easyaivideo.main:app", host=a.host, port=a.port)
```

`pyproject.toml`：

```toml
[project.scripts]
easyaivideo = "easyaivideo.main:main"
```

## .claude/launch.json

讓 Claude Code 的瀏覽器面板能自己啟動伺服器：

```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "easyaivideo", "runtimeExecutable": "uv",
      "runtimeArgs": ["run", "easyaivideo", "--host", "127.0.0.1", "--port", "8000"], "port": 8000 },
    { "name": "easyaivideo-test", "runtimeExecutable": "uv",
      "runtimeArgs": ["run", "easyaivideo", "--host", "127.0.0.1", "--port", "8001"], "port": 8001 }
  ]
}
```

第二組搭配 `EASYAIVIDEO_CONFIG=scratch/config.yaml EASYAIVIDEO_DATA_DIR=scratch/data`，之後所有會扣費的測試都在 8001 用 mock 跑，不會碰你的真實金鑰與專案。把這件事寫進 `CLAUDE.md` 的禁區。

## 一鍵啟動

`start.bat` / `start.sh`：`uv sync` → 沒有 `frontend/dist` 就 `npm install && npm run build` → `uv run easyaivideo`。

## 給 Claude Code 的提示詞
```
實作 config.py（五個區塊、ConfigStore、masked、遮罩值不覆蓋金鑰、EASYAIVIDEO_CONFIG/DATA_DIR）、main.py 與 /api/health、
routers/settings.py（GET 回 masked、PATCH 更新、POST /api/settings/sync-key 複製 llm 金鑰到 image 與 video）、
project.scripts、start.bat/start.sh、.claude/launch.json 兩組設定。啟動 easyaivideo 預覽，打開 /docs 截圖給我。
```

## 今日檢查清單
- [ ] `uv run easyaivideo` 啟動，`/api/health` 回 `ok`。
- [ ] `PATCH /api/settings` 送 `{"llm": {"model": "x", "api_key": "****abcd"}}` 後，真實金鑰沒有被改掉。
- [ ] Claude Code 能用 launch.json 啟動預覽並截圖。

## 明日預告
Day 07 定義 Project / Scene / Task 資料模型，實作 SQLite 持久化與專案 CRUD。
