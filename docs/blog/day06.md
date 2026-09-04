# Day 06｜用 Antigravity 生成專案骨架：uv、config.yaml 與熱更新設定

> 30 天打造 AI 短影片生成平台 — 第 6 天

## 今日目標
- 跑起第一個 FastAPI 伺服器，有 `/api/health` 與 Swagger。
- 完成 `config.py`：讀 YAML、預設值、驗證、由 API 熱更新。
- 建立一鍵啟動腳本。

## 安裝相依

```bash
uv add fastapi "uvicorn[standard]" pydantic pyyaml aiosqlite pillow python-multipart
```

## 設定檔設計

`config.example.yaml`（第一次啟動會被複製成 `config.yaml`，後者不進 git）：

```yaml
gemini:
  api_key: ""              # 空字串則讀環境變數 GEMINI_API_KEY

llm:
  provider: gemini         # gemini | mock
  model: gemini-2.5-flash
  temperature: 0.8
  thinking_budget: 1024

image:
  provider: placeholder    # gemini | imagen | placeholder
  model: gemini-2.5-flash-image
  use_references: true

tts:
  provider: gemini         # gemini | silent
  model: gemini-2.5-flash-preview-tts
  voice: Kore

video:
  provider: kenburns       # kenburns | veo
  model: veo-3.1-generate-preview
  max_clip_seconds: 8

render:
  fps: 30
  font: "Microsoft JhengHei"
  subtitle: true

server:
  data_dir: data
```

預設是「完全離線可跑」的組合（placeholder 圖片，LLM 也可以切成 mock），這樣新使用者不填任何金鑰也能看到流程跑完。

## config.py

```python
from pathlib import Path
import os, shutil, yaml
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("EASYAIVIDEO_CONFIG", ROOT / "config.yaml"))

class GeminiCfg(BaseModel):
    api_key: str = ""
    @property
    def resolved_key(self) -> str:
        return self.api_key or os.environ.get("GEMINI_API_KEY", "")

class LLMCfg(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-2.5-flash"
    temperature: float = 0.8
    thinking_budget: int = 1024

class ImageCfg(BaseModel):
    provider: str = "placeholder"
    model: str = "gemini-2.5-flash-image"
    use_references: bool = True

class TTSCfg(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-2.5-flash-preview-tts"
    voice: str = "Kore"

class VideoCfg(BaseModel):
    provider: str = "kenburns"
    model: str = "veo-3.1-generate-preview"
    max_clip_seconds: int = 8

class RenderCfg(BaseModel):
    fps: int = 30
    font: str = "Microsoft JhengHei"
    subtitle: bool = True

class ServerCfg(BaseModel):
    data_dir: str = "data"

class AppConfig(BaseModel):
    gemini: GeminiCfg = GeminiCfg()
    llm: LLMCfg = LLMCfg()
    image: ImageCfg = ImageCfg()
    tts: TTSCfg = TTSCfg()
    video: VideoCfg = VideoCfg()
    render: RenderCfg = RenderCfg()
    server: ServerCfg = ServerCfg()

    @property
    def data_dir(self) -> Path:
        return Path(os.environ.get("EASYAIVIDEO_DATA_DIR", ROOT / self.server.data_dir))


class ConfigStore:
    """單例，支援熱更新。"""

    def __init__(self):
        if not CONFIG_PATH.exists():
            shutil.copy(ROOT / "config.example.yaml", CONFIG_PATH)
        self.reload()

    def reload(self) -> AppConfig:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        self.config = AppConfig.model_validate(raw)
        return self.config

    def update(self, patch: dict) -> AppConfig:
        data = self.config.model_dump()
        for section, values in patch.items():
            data.setdefault(section, {}).update(values)
        CONFIG_PATH.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return self.reload()


store = ConfigStore()
```

兩個環境變數 `EASYAIVIDEO_CONFIG`、`EASYAIVIDEO_DATA_DIR` 的用意：之後可以用另一份設定與資料夾在 8001 埠跑第二個實例做測試，不會動到你真正的金鑰與專案。

## main.py 與 health 路由

```python
import argparse
from fastapi import FastAPI
from easyaivideo.config import store

app = FastAPI(title="EasyAIVideo", version="0.1.0")

@app.get("/api/health")
async def health():
    cfg = store.config
    return {
        "ok": True,
        "llm": cfg.llm.provider,
        "image": cfg.image.provider,
        "has_key": bool(cfg.gemini.resolved_key),
    }

def main():
    import uvicorn
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    uvicorn.run("easyaivideo.main:app", host=a.host, port=a.port)
```

在 `pyproject.toml` 加入：

```toml
[project.scripts]
easyaivideo = "easyaivideo.main:main"
```

然後 `uv run easyaivideo`，打開 http://127.0.0.1:8000/docs 就能看到 Swagger。

## 設定 API

`routers/settings.py` 提供 `GET /api/settings`（回傳時把 api_key 遮罩成 `****abcd`）與 `PATCH /api/settings`（呼叫 `store.update`）。第四週的設定頁會用到，並在每個區塊提供「測試連線」按鈕，後端對應 `POST /api/settings/test/{section}`。

## 一鍵啟動

`start.bat`：

```bat
@echo off
uv sync || exit /b 1
if not exist frontend\dist (
  cd frontend && npm install && npm run build && cd ..
)
uv run easyaivideo --host 127.0.0.1 --port 8000
```

`start.sh` 同理。

## 給 Antigravity 的提示詞
```
實作 easyaivideo/config.py（Pydantic 模型、ConfigStore 單例、reload/update、
EASYAIVIDEO_CONFIG 與 EASYAIVIDEO_DATA_DIR 環境變數）、easyaivideo/main.py（FastAPI app、/api/health、main() 入口）、
routers/settings.py（GET 遮罩金鑰、PATCH 熱更新）、pyproject 的 project.scripts、start.bat 與 start.sh。
用內建瀏覽器打開 /docs 並截圖給我確認。
```

## 今日檢查清單
- [ ] `uv run easyaivideo` 啟動成功，`/api/health` 回 `ok: true`。
- [ ] 第一次啟動自動產生 `config.yaml`，且已在 `.gitignore`。
- [ ] `PATCH /api/settings` 後 YAML 有變，`GET /api/settings` 立即反映。

## 明日預告
Day 07 定義 Project / Scene / Task 資料模型，實作 SQLite 持久化與專案資料夾管理。
