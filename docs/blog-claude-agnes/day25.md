# Day 25｜即時進度：輪詢 vs SSE，任務狀態視覺化

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 25 天

## 今日目標
- `useTask(taskId)`：進行中每秒輪詢，結束自動刷新專案。
- SSE 端點作為升級選項，並支援腳本逐字串流。
- 進度條、場景層級轉圈、錯誤翻譯、取消、任務歷史。

## 輪詢

```tsx
export function useTask(taskId: string | null, onDone?: (t: Task) => void) {
  return useQuery({
    queryKey: ["task", taskId], queryFn: () => api.tasks.get(taskId!), enabled: !!taskId,
    refetchInterval: q => { const s = q.state.data?.status; return s === "queued" || s === "running" ? 1000 : false; },
    select: t => { if (t.status !== "running" && t.status !== "queued") onDone?.(t); return t; },
  });
}
```

每秒一個小 GET，經得起斷線、切換分頁、重新整理。單機工具首選。

## SSE

```python
@router.get("/api/tasks/{tid}/events")
async def events(tid: str, db=Depends(get_db)):
    async def gen():
        last = None
        while True:
            t = await db.get_task(tid); snap = (t.status, round(t.progress, 3), t.message, t.scene_id)
            if snap != last: yield {"event": "task", "data": t.model_dump_json()}; last = snap
            if t.status not in ("queued", "running"): break
            await asyncio.sleep(0.3)
    return EventSourceResponse(gen())
```

前端 `EventSource`，`onerror` 退回輪詢。設定頁一個開關，預設輪詢。

## 腳本逐字串流

Agnes chat 支援 `stream: true`（Day 04）。`POST /api/projects/{id}/script/stream` 用 SSE 把 delta 推給前端，工作台顯示「正在撰寫…」並逐字浮現 JSON 裡的旁白（用簡單的正則抓 `"narration": "` 之後的字）。純體驗加分，不影響正確性，最後仍以完整解析結果為準。

## 進度視覺化

五段權重對應進度條；`task.message` 顯示在旁；`task.scene_id` 讓對應卡片轉圈。

## 錯誤翻譯

```ts
const HINTS: [RegExp, string][] = [
  [/401|api key/i, "Agnes API Key 無效，請到設定頁重新填入。"],
  [/429|rate limit/i, "Agnes 請求過於頻繁或額度不足，請稍後再試或降低併發。"],
  [/model.*not found/i, "模型名稱不存在，請到設定頁從清單選擇。"],
  [/edge tts/i, "Edge-TTS 連線失敗，請確認網路後重試。"],
  [/ffmpeg/i, "影片合成失敗，請確認 ffmpeg 已安裝或在設定頁指定路徑。"],
  [/no video url|timed out/i, "Agnes 影片任務逾時或未回傳影片，請重試該場景。"],
];
```

紅色面板第一行中文提示，展開看 traceback，「複製診斷資訊」按鈕。

## 取消與歷史

取消按鈕呼叫 cancel 並本地標 cancelling。右上角任務歷史列最近 10 筆：種類、狀態、耗時。

## 給 Claude Code 的提示詞
```
實作 useTask、進度條與階段訊息、scene_id 轉圈、HINTS 錯誤面板與複製診斷、取消、任務歷史；後端 sse_starlette 的 /events 與 /script/stream。
用預覽啟動完整流程每 5 秒截圖到完成；再把 LLM 金鑰改成錯的跑一次，截圖錯誤面板。
```

## 今日檢查清單
- [ ] 進度平滑、訊息對應、對應場景轉圈。
- [ ] 錯誤金鑰顯示中文提示。
- [ ] 重新整理後接回進行中任務。

## 明日預告
Day 26 預覽、下載、字幕、zip 與版本紀錄。
