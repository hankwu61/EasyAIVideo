# Day 19｜Agnes 影片生成：非同步提交、輪詢、i2v / t2v / 首尾幀

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 19 天

## 今日目標
- 實作 `AgnesVideo`：`POST /videos` 提交、`GET /videos/{id}` 輪詢、下載。
- 三種模式：`i2v`、`t2v`、`keyframes`，以及參考圖。
- 片長規則（24 fps、8n+1 幀、最長 18 秒）與旁白更長時的補長策略。

## API 形狀

```
POST /v1/videos
{ "model": "agnes-video-v2.0", "prompt": "...", "width": 720, "height": 1280,
  "num_frames": 97, "frame_rate": 24,
  "image": "<b64>"                                   # i2v：首幀
  "extra_body": {"image": ["<b64>", "<b64>"], "mode": "keyframes"}   # 首尾幀
  "extra_body": {"image": ["<b64>", ...]}            # t2v + 參考圖（最多 4）
}
→ { "task_id": "..." }
GET /v1/videos/{task_id} → { "status": "queued|running|completed|failed", "url": "...", "error": {...} }
```

## 片長 → 幀數

```python
FPS, STEP, MAX_FRAMES = 24, 8, 441
def duration_to_frames(seconds: float) -> int:
    target = max(1, round(seconds)) * FPS
    n = round((target - 1) / STEP)
    return max(1, min(STEP * n + 1, MAX_FRAMES))     # 8n+1
```

4 秒 → 97 幀，10 秒 → 241 幀，18 秒 → 433 幀。

## 尺寸

`resolution: 480p | 720p | 1080p` 是短邊，`aspect_size(..., round_to=8, max_long_edge=1920)` 算 WxH。

## AgnesVideo

```python
class AgnesVideo:
    name = "agnes"

    def build_payload(self, req: VideoRequest) -> dict:
        w, h = aspect_size(req.width, req.height, SHORT_EDGE[self.cfg.resolution], round_to=8, max_long_edge=1920)
        seconds = min(max(req.duration, 1), min(18, self.cfg.max_clip_seconds))
        p = {"model": self.model, "prompt": req.prompt, "width": w, "height": h,
             "num_frames": duration_to_frames(seconds), "frame_rate": FPS}
        if req.seed is not None: p["seed"] = req.seed
        if req.start_image and req.end_image:
            p["extra_body"] = {"image": [b64(req.start_image), b64(req.end_image)], "mode": "keyframes"}
        elif req.start_image:
            p["image"] = b64(req.start_image)
        elif req.reference_images:
            p["extra_body"] = {"image": [b64(x) for x in req.reference_images[:4]]}
        return p

    async def generate(self, req):
        payload = self.build_payload(req)
        async with httpx.AsyncClient(timeout=60) as c:
            task_id = await self._submit(c, payload)            # 408/429/5xx 退避重試 4 次
            final = await self._poll(c, task_id)                # 每 5 秒，poll_timeout 上限；暫時性錯誤容忍 8 次
            url = final.get("url") or final.get("video_url") or (final.get("metadata") or {}).get("url")
            if not url: raise ProviderError(f"完成但無影片 URL（欄位：{sorted(final)}）")
            await self._download(c, url, req.output_path)      # 串流寫檔，3 次重試
        return req.output_path
```

`b64()` 是**裸 base64**，不帶 `data:image/png;base64,` 前綴，這點與圖片端點不同。

## 三種模式

| 模式 | 輸入 | 適合 |
|---|---|---|
| `i2v`（預設） | 場景圖首幀 + `video_prompt` | 角色構圖最穩，圖已經是你審過的 |
| `t2v` | `video_prompt` +（可選）角色參考圖 | 讓模型自由發揮 |
| `keyframes` | 本場圖首幀 + 下一場圖尾幀 | 一鏡到底的銜接感 |

管線：

```python
nxt = project.scenes[i+1] if i+1 < len(project.scenes) else None
req = VideoRequest(prompt=s.video_prompt or s.image_prompt, width=w, height=h, duration=s.duration, output_path=out,
                   start_image=abs(s.image_path) if mode != "t2v" else None,
                   end_image=abs(nxt.image_path) if mode == "keyframes" and nxt and nxt.image_path else None,
                   reference_images=char_refs if mode == "t2v" else None)
```

## 旁白比片段長

`max_clip_seconds` 預設 10。旁白 15 秒時：
1. **循環**（預設）：`-stream_loop -1 -t 15`。
2. **boomerang**：正放 + `reverse` 串接再循環，小動作場景自然。
3. **續片**：截最後一幀當下一段首幀再生成，最好也最貴。

`ProjectOptions.long_scene_strategy` 切換。Agnes 片段沒有音軌，合成流程與 Ken Burns 完全相同。

## 混合策略與併發

- 場景層級 `motion_override`：只讓鉤子與結尾用 AI 影片，中間用 Ken Burns。
- `video.concurrency` 預設 1，Agnes 對併發敏感，多開會被限流。
- 提交前顯示「本次預估 N 段 × M 秒」，確認後才開始。

## 用 Claude Code 做假閘道測試

真的呼叫很貴。請 Claude Code 寫 `scratch/fake_agnes.py`：一個 FastAPI 假伺服器，`POST /v1/videos` 回 task_id，`GET /v1/videos/{id}` 前兩次回 running、第三次回 completed 並附一個由 ffmpeg 產生的測試片段 URL。把 `video.base_url` 指到它，整條流程就能零成本驗證。

## 給 Claude Code 的提示詞
```
實作 providers/video/agnes.py（build_payload、duration_to_frames、_submit 退避、_poll 容錯、_download 串流、test 打 /models）、
mode 三種分流、long_scene_strategy、concurrency Semaphore。再寫 scratch/fake_agnes.py 假閘道（FastAPI on 8099，回 ffmpeg 產生的片段）。
用假閘道對 8001 專案跑 i2v 與 keyframes，貼 payload 與結果。不要用真實金鑰。
```

## 今日檢查清單
- [ ] `num_frames` 永遠是 8n+1。
- [ ] i2v payload 的 `image` 是裸 base64；keyframes 在 `extra_body`。
- [ ] 15 秒旁白的場景片段正確補長。

## 明日預告
Day 20 背景任務佇列：進度、取消、重啟恢復。
