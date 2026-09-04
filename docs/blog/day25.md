# Day 25｜即時進度：輪詢 vs SSE，任務狀態視覺化

> 30 天打造 AI 短影片生成平台 — 第 25 天

## 今日目標
- 實作 `useTask(taskId)`：任務進行中每秒輪詢，結束後自動刷新專案。
- 加一條 SSE 端點作為升級選項，並比較兩者取捨。
- 進度條、階段訊息、錯誤面板與取消按鈕。

## 輪詢：先做這個

```tsx
export function useTask(taskId: string | null, onDone?: (t: Task) => void) {
  return useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.tasks.get(taskId!),
    enabled: !!taskId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "queued" || s === "running" ? 1000 : false;
    },
    // 結束時觸發
    select: (t) => { if (t.status !== "running" && t.status !== "queued") onDone?.(t); return t; },
  });
}
```

工作台：

```tsx
const [taskId, setTaskId] = useState(project.active_task_id ?? null);
const { data: task } = useTask(taskId, () => qc.invalidateQueries({ queryKey: ["project", project.id] }));
```

每秒一個小 GET，對單機工具毫無壓力，而且經得起網路斷線、分頁切換、重新整理。

## SSE：需要更即時時再上

後端：

```python
from sse_starlette.sse import EventSourceResponse

@router.get("/api/tasks/{tid}/events")
async def task_events(tid: str, db=Depends(get_db)):
    async def gen():
        last = None
        while True:
            t = await db.get_task(tid)
            snap = (t.status, round(t.progress, 3), t.message)
            if snap != last:
                yield {"event": "task", "data": t.model_dump_json()}
                last = snap
            if t.status not in ("queued", "running"):
                break
            await asyncio.sleep(0.3)
    return EventSourceResponse(gen())
```

前端：

```ts
const es = new EventSource(`/api/tasks/${id}/events`);
es.addEventListener("task", e => setTask(JSON.parse(e.data)));
es.onerror = () => { es.close(); /* 退回輪詢 */ };
```

| | 輪詢 | SSE |
|---|---|---|
| 延遲 | ≤1 秒 | ~0.3 秒 |
| 實作複雜度 | 極低 | 中（連線管理、代理設定、錯誤退回） |
| 適合 | 單機、少量任務 | 多使用者、串流腳本文字 |

腳本生成若要逐字顯示（Day 04 的 `generate_content_stream`），SSE 才做得到。今天先把端點做好，前端預設仍用輪詢，設定頁加一個開關。

## 進度視覺化

頂部進度條分五段（腳本 10%、圖片 35%、語音 15%、動態 20%、合成 20%），對應 Day 20 的權重：

```tsx
<div className="h-2 rounded bg-neutral-800 overflow-hidden">
  <div className="h-full bg-emerald-500 transition-all duration-500" style={{ width: `${(task.progress * 100).toFixed(1)}%` }} />
</div>
<div className="text-sm text-neutral-400">{task.message} · {Math.round(task.progress * 100)}%</div>
```

場景卡片也吃進度：`task.message` 含「場景圖 3/6」時，第 3 張縮圖顯示轉圈。更好的做法是讓 `progress()` 多帶一個 `scene_id`，前端精準對應。

## 錯誤呈現

`task.status === "failed"` 時顯示紅色面板：第一行是人類可讀的 `error` 摘要，展開才看 traceback。常見錯誤翻譯成中文提示：

```ts
const HINTS: Record<string, string> = {
  "429": "Gemini 配額用完，請稍後再試或到設定頁更換金鑰／升級付費層。",
  "API key not valid": "API Key 無效，請到設定頁重新填入。",
  "ffmpeg": "影片合成失敗，請確認 ffmpeg 已安裝且在 PATH 中。",
  "safety": "內容被安全政策擋下，請修改提示詞。",
};
```

## 取消

按鈕呼叫 `api.tasks.cancel(id)`，立即把本地狀態設為 `cancelling` 避免重複點，下一次輪詢會拿到 `cancelled`。

## 任務歷史

工作台右上角一個小面板列出 `GET /api/projects/{id}/tasks` 最近 10 筆：種類、狀態、耗時。除錯與觀察成本都靠它。

## 給 Antigravity 的提示詞
```
實作 useTask 輪詢 hook、進度條與階段訊息、場景層級轉圈（progress 回呼加 scene_id）、失敗面板與 HINTS、取消按鈕、任務歷史面板；
後端加 sse_starlette 的 /api/tasks/{id}/events 與 progress 的 scene_id。用瀏覽器啟動一次完整流程，
每 5 秒截圖直到完成，並故意把 API Key 改錯再跑一次，截圖錯誤面板。
```

## 今日檢查清單
- [ ] 進度條平滑前進，訊息與階段對應。
- [ ] 錯誤金鑰時顯示中文提示而不是 traceback。
- [ ] 重新整理頁面後仍能接回進行中的任務。

## 明日預告
Day 26 工作台右半邊：影片預覽、下載、字幕下載、素材打包 zip，與版本紀錄。
