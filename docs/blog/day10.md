# Day 10｜供應商抽象層：可替換的 LLM / TTS / Image / Video 介面與 mock

> 30 天打造 AI 短影片生成平台 — 第 10 天

## 今日目標
- 定義四個 Protocol：`LLMProvider`、`ImageProvider`、`TTSProvider`、`VideoProvider`。
- 每個介面都有一個離線 mock 實作，整條管線不花一毛錢就能跑。
- 建立 `providers/registry.py`，依 `config.yaml` 組裝供應商。

## 為什麼要抽象層

三個實際的理由：

1. **開發時省錢省時間**：跑通 ffmpeg 合成不需要真的叫 Gemini 畫圖。
2. **測試可重現**：mock 輸出固定，CI 才能跑。
3. **模型會換**：今天是 `gemini-2.5-flash-image`，明年可能是別的名字；service 層不該知道。

## 介面定義

`providers/base.py`：

```python
from typing import Protocol
from pathlib import Path
from easyaivideo.providers.llm.schemas import ScriptDraft

class LLMProvider(Protocol):
    async def write_script(self, topic: str, **kw) -> ScriptDraft: ...
    async def segment_script(self, text: str, **kw) -> ScriptDraft: ...
    async def test(self) -> str: ...            # 設定頁「測試連線」

class ImageProvider(Protocol):
    async def generate(self, prompt: str, *, aspect: str, out: Path,
                       references: list[Path] | None = None, seed: int | None = None) -> Path: ...
    async def test(self) -> str: ...

class TTSResult(TypedDict):
    path: Path
    duration: float

class TTSProvider(Protocol):
    async def synthesize(self, text: str, *, voice: str, language: str, out: Path,
                         style: str | None = None) -> TTSResult: ...
    async def test(self) -> str: ...

class VideoProvider(Protocol):
    async def animate(self, *, image: Path | None, prompt: str, duration: float,
                      aspect: str, out: Path, last_image: Path | None = None) -> Path: ...
    async def test(self) -> str: ...
```

`Protocol` 不需要繼承，任何有這些方法的類別都算實作；配合 mypy 或 pyright 可以在編輯器裡即時檢查。

## mock 實作

`providers/llm/mock.py`：固定回傳 5 個場景，旁白帶主題名稱。

`providers/image/placeholder.py`：用 PIL 畫一張漸層底、印上場景編號與提示詞前 40 字：

```python
from PIL import Image, ImageDraw, ImageFont

class PlaceholderImage:
    async def generate(self, prompt, *, aspect, out, references=None, seed=None):
        w, h = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}[aspect]
        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)
        for y in range(h):  # 簡單直向漸層
            d.line([(0, y), (w, y)], fill=(30 + y * 60 // h, 40, 90 + y * 100 // h))
        d.text((40, 40), prompt[:40], fill="white")
        img.save(out)
        return out
```

`providers/tts/silent.py`：依字數估算時長（中文每秒 4 字），用 ffmpeg 產生等長靜音 wav：

```python
async def synthesize(self, text, *, voice, language, out, style=None):
    duration = max(1.0, len(text) / 4)
    await run_ffmpeg("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(duration), str(out))
    return {"path": out, "duration": duration}
```

`providers/video/kenburns.py` 本身就不需要 AI，Day 15 實作。

## registry

`providers/registry.py`：

```python
from easyaivideo.config import AppConfig

def build_llm(cfg: AppConfig):
    if cfg.llm.provider == "gemini":
        from .llm.gemini import GeminiLLM
        return GeminiLLM(cfg.gemini.resolved_key, cfg.llm)
    from .llm.mock import MockLLM
    return MockLLM()

def build_image(cfg): ...
def build_tts(cfg): ...
def build_video(cfg): ...

class Providers:
    """每次任務開始時重新組裝，設定頁改了立即生效。"""
    def __init__(self, cfg: AppConfig):
        self.llm, self.image, self.tts, self.video = build_llm(cfg), build_image(cfg), build_tts(cfg), build_video(cfg)
```

延遲 import 有兩個好處：沒裝某個套件不會整個炸掉；啟動速度快。

## 設定頁「測試連線」

每個 provider 的 `test()` 回傳一句人類可讀的訊息，例如 Gemini LLM：

```python
async def test(self) -> str:
    resp = await self.client.aio.models.generate_content(model=self.cfg.model, contents="回覆 OK")
    return f"{self.cfg.model} 回應：{resp.text.strip()[:20]}"
```

路由 `POST /api/settings/test/{section}` 用當前設定臨時組裝一個 provider 呼叫 `test()`。

## 第二個實例做測試

之後所有會花錢的測試，都用另一組設定跑在 8001 埠：

```bash
EASYAIVIDEO_CONFIG=scratch/config.yaml EASYAIVIDEO_DATA_DIR=scratch/data uv run easyaivideo --port 8001
```

`scratch/config.yaml` 全部用 mock / placeholder / silent。

## 給 Antigravity 的提示詞
```
建立 providers/base.py 四個 Protocol、mock/placeholder/silent 三個離線實作、providers/registry.py 的 build_* 與 Providers 類別，
以及 POST /api/settings/test/{section}。把 pipeline 改成透過 Providers 取得供應商。
用 scratch 設定在 8001 埠啟動，建立專案並跑 /script，確認 mock 場景回傳。
```

## 今日檢查清單
- [ ] `config.yaml` 全 mock 時，`/script` 仍能產生場景。
- [ ] 四個 `test()` 在設定頁都能回訊息。
- [ ] service 層沒有任何 `from google import genai`。

## 明日預告
Day 11 接上真正的圖片模型：Gemini 原生圖片生成（Nano Banana）與 Imagen，為每個場景畫圖。
