# Day 29｜成本、配額與穩定性：Agnes 併發限制、Edge-TTS 失敗處理、快取與重試

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 29 天

## 今日目標
- 統一重試、退避與逾時；每種供應商的併發上限。
- Edge-TTS 的特殊處理：免費服務的失敗模式與退回方案。
- 三層快取、用量記錄、費用估算與每日預算。

## 統一重試

```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception

def retryable(e: BaseException) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in (408, 429, 500, 502, 503, 504)
    return isinstance(e, (httpx.TransportError, asyncio.TimeoutError))

agnes_retry = retry(stop=stop_after_attempt(5), wait=wait_exponential_jitter(initial=2, max=60, jitter=3),
                    retry=retry_if_exception(retryable), reraise=True)
```

套在 LLM、圖片、影片提交的公開方法上。401、404 model not found、400 內容被拒不重試，轉成 `AppError` 給前端中文提示。

## 併發

| 供應商 | 預設併發 | 說明 |
|---|---|---|
| Agnes LLM | 3 | 分段並行時注意 |
| Agnes 圖片 | 2 | 多開容易 429 |
| Agnes 影片 | 1 | 對併發最敏感，`video.concurrency` |
| Edge-TTS | 2 | 免費服務，太快會被暫時拒絕 |

全部用 `asyncio.Semaphore`，設定頁可調。

## Edge-TTS 的失敗模式

- **暫時性 403 / 連線重置**：微軟偶爾調整端點，`edge-tts` 套件會跟著更新。重試 3 次仍失敗 → 提示「請 `uv sync --upgrade-package edge-tts`」。
- **沒有 WordBoundary**：某些聲音或極短文本不回時間戳，字幕自動退回比例估算（Day 14）。
- **完全不可用**：設定頁提供退回選項 `tts.fallback: silent | openai_compat`；`openai_compat` 走 Agnes 或其他服務的 `/audio/speech`（付費）。管線在 Edge 連續失敗 3 次後自動切退回並在任務訊息註明。

把 `edge-tts` 的版本釘在 `pyproject.toml`，並在 CI 每週跑一次「合成一句」的煙霧測試。

## 快取

| 東西 | 鍵 | 位置 |
|---|---|---|
| TTS（試聽與逐行台詞） | voice + speed + text hash | `data/cache/tts/` |
| 圖片 | model + size + prompt hash + refs hash | `data/cache/images/` |
| LLM（temperature 0 時） | model + system hash + user hash | SQLite `llm_cache` |

圖片快取讓「換比例」與「手滑重生兩次」不重扣費。快取上限 2 GB，LRU 清理。

## 用量記錄與費用

```python
class UsageRecord(BaseModel):
    ts: datetime; project_id: str | None; provider: str; model: str
    input_tokens: int = 0; output_tokens: int = 0; images: int = 0; audio_seconds: float = 0; video_seconds: float = 0
```

Agnes chat 回應的 `usage` 欄位有 token 數；圖片每張 1；影片記 `num_frames / 24` 秒；Edge-TTS 記秒數但單價 0。

`pricing.yaml` 放單價與更新日期。`estimate_project()` 在表單與工作台顯示「預估 ≈ $0.08」，AI 影片時另列「影片 6 × 10 秒」。每日預算超過時新任務要求確認。

`GET /api/usage?days=7` 回每日彙總，設定頁畫長條圖。

## 可觀察性

JSON 格式日誌帶 `task_id` / `project_id` / `provider` / 耗時；失敗任務的「複製診斷資訊」包含遮罩後設定、`edge-tts` 與 `ffmpeg` 版本。

## 用 Claude Code 做故障演練

「用 monkeypatch 讓 OpenAICompatImage 前兩次丟 429、第三次成功，寫成測試並確認退避間隔；再讓 EdgeTTS 連續失敗 3 次，確認自動切到 silent 並在任務訊息註明。」讓它把故障情境變成測試，之後就不會回歸。

## 給 Claude Code 的提示詞
```
加入 tenacity 重試、httpx timeout、四種供應商 Semaphore 設定、Edge-TTS fallback 機制、三層快取與 LRU、UsageRecord 與 usage 表、
pricing.yaml 與 estimate_project、表單與工作台預估、每日預算、GET /api/usage 與設定頁圖表。
寫 429 退避與 Edge fallback 的測試並跑綠。
```

## 今日檢查清單
- [ ] 模擬 429 任務不失敗，日誌看到退避。
- [ ] Edge 連續失敗自動退回且訊息清楚。
- [ ] 預估費用與實際用量同頁可比。

## 明日預告
Day 30 部署與回顧：Docker、區網、備份、下一個 30 天。
