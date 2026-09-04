# Day 10｜供應商抽象層：可替換的 LLM / TTS / Image / Video 介面與 mock

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 10 天

## 今日目標
- 定義四個 Protocol 與 `ProviderError`。
- 每個介面一個離線 mock：`MockLLM`、`PlaceholderImage`、`SilentTTS`、Ken Burns 本身就離線。
- `registry.py` 依設定組裝；設定頁「測試連線」。

## 為什麼要抽象層

1. 開發不花錢：跑 ffmpeg 不需要真的叫 Agnes 畫圖。
2. 測試可重現：mock 輸出固定。
3. 換服務只改一個檔：Agnes → 其他 OpenAI 相容服務，只改 `base_url`；Edge-TTS → 其他 TTS，只換一個類別。

## base.py

```python
class ProviderError(RuntimeError): ...

@dataclass
class VideoRequest:
    prompt: str; width: int; height: int; duration: float; output_path: Path
    start_image: Path | None = None; end_image: Path | None = None
    reference_images: list[Path] | None = None; seed: int | None = None

class LLMProvider(Protocol):
    async def write_script(self, topic: str, **kw) -> ScriptDraft: ...
    async def segment_script(self, text: str, **kw) -> ScriptDraft: ...
    async def test(self) -> str: ...

class ImageProvider(Protocol):
    async def generate(self, prompt: str, *, width: int, height: int, output_path: Path,
                       reference_images: list[Path] | None = None, seed: int | None = None) -> Path: ...
    async def test(self) -> str: ...

class TTSProvider(Protocol):
    async def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> "TTSResult": ...
    async def list_voices(self) -> list[VoiceInfo]: ...
    async def test(self) -> str: ...

class VideoProvider(Protocol):
    async def generate(self, req: VideoRequest) -> Path: ...
    async def test(self) -> str: ...
```

`TTSResult` 含 `path`、`duration`、`words`（逐字時間戳，可為空），Day 14 用。

## mock 實作

- `MockLLM`：固定 5 場，旁白帶主題名；`segment_script` 用句號切。
- `PlaceholderImage`：PIL 漸層底 + 場景編號 + 提示詞前 40 字。
- `SilentTTS`：依字數估長度（每秒 4 字），ffmpeg `anullsrc` 產生等長 mp3，`words` 用等分估算。

## registry

```python
def build_llm(cfg):
    if cfg.llm.provider == "openai_compat":
        from .llm.openai_compat import OpenAICompatLLM; return OpenAICompatLLM(cfg.llm)
    from .llm.mock import MockLLM; return MockLLM()

def build_tts(cfg):
    if cfg.tts.provider == "edge":
        from .tts.edge import EdgeTTS; return EdgeTTS()
    from .tts.silent import SilentTTS; return SilentTTS()

def build_image(cfg): ...   # openai_compat | placeholder
def build_video(cfg): ...   # agnes | kenburns

class Providers:
    def __init__(self, cfg):
        self.llm, self.tts, self.image, self.video = build_llm(cfg), build_tts(cfg), build_image(cfg), build_video(cfg)
```

每個任務開始時重新組裝，設定頁改完立即生效。延遲 import 讓缺套件不會炸整個程式。

## 測試連線

`POST /api/settings/test/{section}`：用**請求帶來的暫時設定**（不是已儲存的）組裝供應商並呼叫 `test()`。使用者可以先測再存。Agnes 三個區塊的 `test()` 都打 `GET /models` 並確認所設模型在清單內。

## 第二個實例

```bash
EASYAIVIDEO_CONFIG=scratch/config.yaml EASYAIVIDEO_DATA_DIR=scratch/data uv run easyaivideo --port 8001
```

`scratch/config.yaml` 全 mock。把「所有會扣費的測試都在 8001 用 mock 跑」寫進 `CLAUDE.md`。

## 給 Claude Code 的提示詞
```
建立 providers/base.py（四個 Protocol、ProviderError、VideoRequest、TTSResult、VoiceInfo）、mock/placeholder/silent、registry.py、
POST /api/settings/test/{section}（用請求中的暫時設定）。pipeline 改為透過 Providers。
用 launch.json 的 easyaivideo-test 啟動 8001，建立專案並跑 /script，確認 mock 場景。
```

## 今日檢查清單
- [ ] 全 mock 設定下 `/script` 有場景。
- [ ] 四個「測試連線」都回訊息。
- [ ] service 層沒有任何 `httpx` 或 `edge_tts` 的 import。

## 明日預告
Day 11 接上 Agnes 圖片生成：`/images/generations`、精確尺寸、b64 與 URL 兩種回傳。
