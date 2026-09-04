# Day 03｜Agnes AI 入門：取得 API Key、OpenAI 相容端點與模型總覽

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 3 天

## 今日目標
- 在 Agnes AI 控制台建立 API Key，安全存放。
- 認識三個端點：`/chat/completions`、`/images/generations`、`/videos`。
- 用 curl 各打一次，確認金鑰與模型可用。

## 為什麼是 Agnes AI

- **一把金鑰、三種能力**：文字、圖片、影片同一個 base URL 與同一把金鑰，設定頁只要填一次。
- **OpenAI 相容**：任何會用 OpenAI API 的程式碼幾乎不用改；日後想換 DeepSeek、Qwen、本地 Ollama，只要改 `base_url` 與 `model`。
- **影片模型可用圖生影片與首尾幀**：這讓「場景圖 → 動態片段」不必自建 GPU。

## 取得 API Key

1. 到 Agnes AI 官網註冊，進入 API 控制台（apihub）。
2. 建立 API Key，複製保存（通常只顯示一次）。
3. 儲值或確認方案額度。文字模型很便宜，圖片按張、影片按秒計價。

存放：

```powershell
[Environment]::SetEnvironmentVariable("AGNES_API_KEY", "你的金鑰", "User")
```

程式裡從環境變數或 `config.yaml` 讀，永遠不要寫進原始碼或貼進 Claude Code 的對話。

## 三個端點

| 能力 | 端點 | 模型範例 | 形式 |
|---|---|---|---|
| 文字 | `POST /v1/chat/completions` | `agnes-2.0-flash` | 同步，OpenAI messages 格式 |
| 圖片 | `POST /v1/images/generations` | `agnes-image-2.0-flash`、`agnes-image-2.1-flash` | 同步，回 `url` 或 `b64_json`；支援 `size: "WxH"` 精確尺寸與 `image: [參考圖 data URI]` |
| 影片 | `POST /v1/videos` → `GET /v1/videos/{task_id}` | `agnes-video-v2.0` | 非同步，提交後輪詢，完成回影片 URL |
| 模型清單 | `GET /v1/models` | | 設定頁「測試連線」用 |

## 用 curl 驗證

文字：

```bash
curl https://apihub.agnes-ai.com/v1/chat/completions \
  -H "Authorization: Bearer $AGNES_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"agnes-2.0-flash","messages":[{"role":"user","content":"用一句話介紹短影片"}]}'
```

圖片（會扣費，一張就好）：

```bash
curl https://apihub.agnes-ai.com/v1/images/generations \
  -H "Authorization: Bearer $AGNES_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"agnes-image-2.0-flash","prompt":"a cat sitting in a cardboard box, soft light","n":1,"size":"1024x1792"}'
```

影片提交（會扣費，Day 19 前可以先跳過）：

```bash
curl https://apihub.agnes-ai.com/v1/videos \
  -H "Authorization: Bearer $AGNES_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"agnes-video-v2.0","prompt":"a cat slowly turns its head","width":720,"height":1280,"num_frames":97,"frame_rate":24}'
```

回傳含 `task_id`，之後 `GET /v1/videos/{task_id}` 看 `status`，`completed` 時有 `url` 或 `video_url`。

## 影片 API 的幾個硬規則（先記起來）

- `frame_rate` 固定 24。
- `num_frames` 必須是 8n+1（9、17、25 … 441），441 幀約 18 秒。
- 圖生影片：頂層 `image` 放 base64（不含 data URI 前綴）。
- 首尾幀：`extra_body: {"image": [首幀 b64, 尾幀 b64], "mode": "keyframes"}`。
- 參考圖：`extra_body: {"image": [最多 4 張]}`。
- 對併發敏感，一次跑一個任務最穩。

## 開發策略

1. 前兩週幾乎只用文字模型，費用可忽略。
2. 圖片與影片先用 mock 供應商跑通流程（Day 10），再切真實模型。
3. 影片預設用 ffmpeg Ken Burns，Agnes 影片為可選。

## 給 Claude Code 的提示詞
```
建立 config.example.yaml，包含 llm / tts / image / video / render 五個區塊：
llm 與 image 與 video 各有 provider、api_key（空）、base_url（預設 https://apihub.agnes-ai.com/v1）、model；
tts 預設 provider: edge、voice: zh-TW-HsiaoChenNeural、speed: 1.0。
再寫 scripts/agnes_ping.py：用 httpx 讀環境變數 AGNES_API_KEY，呼叫 /models 並列出模型名稱。不要把金鑰寫進檔案。
```

## 今日檢查清單
- [ ] `echo $env:AGNES_API_KEY` 有值。
- [ ] `uv run python scripts/agnes_ping.py` 列出模型。
- [ ] 知道 `num_frames` 為什麼要是 8n+1。

## 明日預告
Day 04 第一支程式：用 httpx 呼叫 chat/completions，處理串流，並用三層防禦拿到可靠的 JSON。
