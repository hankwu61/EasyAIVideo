# Day 29｜成本、配額與穩定性：快取、重試、安全設定與費用估算

> 30 天打造 AI 短影片生成平台 — 第 29 天

## 今日目標
- 為所有 Gemini 呼叫加上統一的重試、退避與逾時。
- 用快取避免重複付費：TTS 試聽、相同提示詞的圖片、上下文快取。
- 在 UI 顯示每個專案的預估與實際費用，並可設定每日預算。

## 統一重試

Gemini SDK 本身有基本重試，但我們要的是「可觀察、可調整」的行為。用 `tenacity`：

```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception
from google.genai import errors

def _retryable(e: BaseException) -> bool:
    if isinstance(e, errors.APIError):
        return e.code in (429, 500, 502, 503, 504)
    return isinstance(e, (TimeoutError, ConnectionError))

gemini_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=2, max=60, jitter=3),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
```

套在每個 provider 的公開方法上。429 之後等 2、4、8、16 秒，加抖動避免多個任務同時撞牆。逾時用 `http_options=types.HttpOptions(timeout=120_000)` 在 `genai.Client` 設定。

400（提示詞被拒）與 403（金鑰）不重試，直接轉成 `AppError(402/401)` 讓前端顯示中文提示。

## 並行上限

`providers/registry.py` 對每種供應商掛一個 `asyncio.Semaphore`，預設 LLM 4、圖片 2、TTS 4、Veo 1，可在設定頁調整。免費層先全部設 1。

## 安全設定

Gemini 預設安全過濾對小說改編偶爾太嚴（打鬥、恐怖題材）。允許使用者在設定頁調整：

```python
safety_settings=[
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
]
```

被擋時 `finish_reason == "SAFETY"`，任務錯誤要明確寫「第 3 場提示詞被安全政策擋下」，並在工作台把那一場標紅，讓使用者改提示詞重生，而不是整個任務失敗。

## 快取層

| 東西 | 鍵 | 位置 |
|---|---|---|
| TTS 試聽 | voice + style + text hash | `data/cache/tts/` |
| 圖片 | model + aspect + prompt hash + refs hash | `data/cache/images/` |
| 腳本 | model + system hash + user hash + temperature（僅溫度 0 時） | SQLite `llm_cache` |
| 原文上下文 | series id | Gemini context cache（Day 27） |

圖片快取的價值在「換比例重輸出」與「使用者手滑按了兩次重生」。快取目錄設上限（例如 2 GB），LRU 清理。

## 用量記錄

每次呼叫記一筆：

```python
class UsageRecord(BaseModel):
    ts: datetime; project_id: str | None; provider: str; model: str
    input_tokens: int = 0; output_tokens: int = 0; images: int = 0; audio_seconds: float = 0; video_seconds: float = 0
```

文字模型的 token 從 `resp.usage_metadata` 取；圖片每張 1；TTS 記輸出秒數；Veo 記生成秒數。存進 SQLite `usage` 表。

## 費用估算

單價放在 `pricing.yaml`（會變，所以獨立成檔並標註更新日期），估算函式把用量乘單價：

```python
def estimate_project(p: Project, cfg) -> dict:
    n = len(p.scenes) or 6
    return {
        "script": price("llm", cfg.llm.model, in_tok=2000, out_tok=1500),
        "images": n * price("image", cfg.image.model),
        "tts": price("tts", cfg.tts.model, chars=sum(len(s.narration) for s in p.scenes) or n * 40),
        "video": n * cfg.video.max_clip_seconds * price("video", cfg.video.model) if p.options.motion == "ai" else 0,
    }
```

新增專案表單底部與工作台按鈕旁顯示「預估 ≈ $0.12」；任務完成後顯示實際用量。設定頁有「每日預算」，超過時新任務要求確認。

## 可觀察性

- `logging` 統一 JSON 格式，每筆帶 `task_id`、`project_id`、`provider`、耗時。
- `GET /api/usage?days=7` 回每日彙總，前端設定頁畫一張簡單長條圖。
- 失敗任務的 traceback 已存在 task，加一個「複製診斷資訊」按鈕把設定（遮罩金鑰）、版本、錯誤一起複製。

## 給 Antigravity 的提示詞
```
加入 tenacity 重試裝飾器與 http timeout、每種供應商的 Semaphore 設定、safety_settings 設定與 SAFETY 錯誤的場景層級標記、
三層快取（tts/images/llm）與 LRU 清理、UsageRecord 與 usage 表、pricing.yaml 與 estimate_project、
表單與工作台的預估費用顯示、每日預算檢查、GET /api/usage 與設定頁用量圖。用 8001 埠模擬 429（mock 供應商丟例外）確認退避行為。
```

## 今日檢查清單
- [ ] 模擬 429 時任務不會失敗，日誌看到退避間隔。
- [ ] 同一句試聽第二次沒有 API 呼叫，用量表也沒有新紀錄。
- [ ] 預估費用與實際用量在同一頁可比較。

## 明日預告
Day 30 部署與回顧：Docker 映像、Cloud Run、區網部署、備份，以及下一個 30 天可以做什麼。
