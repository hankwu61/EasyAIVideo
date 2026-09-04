# Day 03｜Google AI Studio 入門：取得 Gemini API Key、認識模型與配額

> 30 天打造 AI 短影片生成平台 — 第 3 天

## 今日目標
- 在 Google AI Studio 建立 API Key，安全地存放。
- 認識我們會用到的四類模型：文字、圖片、語音、影片。
- 了解免費層與付費層的差異，避免開發到一半被 429 卡住。

## 什麼是 Google AI Studio

[Google AI Studio](https://aistudio.google.com/) 是 Gemini API 的「駕駛艙」：

- 建立與管理 API Key。
- 在瀏覽器裡直接試提示詞（文字、圖片、語音、影片都可以），試好再貼進程式。
- 查看用量、配額與帳單。
- 「Get code」按鈕會直接產生 Python / JavaScript / curl 範例。

之後每次要調提示詞，建議先在 AI Studio 跑幾次，確認輸出穩定再寫進程式碼。

## 取得 API Key

1. 登入 AI Studio，左側點 **Get API key**。
2. **Create API key**，選擇（或建立）一個 Google Cloud 專案。
3. 複製金鑰，**只會顯示一次**。

存放方式：

```bash
# Windows PowerShell（永久寫入使用者環境變數）
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "你的金鑰", "User")

# macOS / Linux
echo 'export GEMINI_API_KEY="你的金鑰"' >> ~/.zshrc
```

`google-genai` SDK 會自動讀取 `GEMINI_API_KEY` 環境變數，程式裡不需要硬編碼。我們的平台之後會把金鑰放在 `config.yaml`（已在 `.gitignore`），並提供設定頁面讓使用者填入。

> 千萬不要把金鑰貼進提示詞、commit、或前端程式碼。之後 Antigravity 的規則檔也要註明這件事。

## 我們會用到的模型

| 用途 | 模型（範例） | 備註 |
|---|---|---|
| 腳本、文稿分析 | `gemini-2.5-flash`、`gemini-2.5-pro`、`gemini-3-pro-preview` | Flash 便宜快速，Pro 推理更好；支援 JSON Schema 結構化輸出 |
| 場景圖 | `gemini-2.5-flash-image`（Nano Banana） | 原生多模態，能用參考圖維持角色一致 |
| 場景圖（替代） | `imagen-4.0-generate-001` | 專職圖片模型，支援多種長寬比 |
| 配音 | `gemini-2.5-flash-preview-tts`、`gemini-2.5-pro-preview-tts` | 30 種預建聲音、可用自然語言控制語氣、支援多說話者 |
| 影片 | `veo-3.1-generate-preview`、`veo-3.0-fast-generate-001` | 文生影片、圖生影片、首尾幀；需付費層 |
| 內嵌 | `gemini-embedding-001` | Day 27 小說分析時可能會用到 |

在 AI Studio 左上角的模型選單可以看到目前所有可用模型與它們的輸入輸出模態，這份清單會變，請以那裡為準。

## 配額與費用

- **免費層**：文字模型有每分鐘與每日請求上限，足夠開發與測試腳本生成；圖片模型有較少的免費額度；**Veo 沒有免費層**。
- **付費層**：在 Google Cloud 專案啟用計費後，配額大幅提高，Veo 可用。
- 觀察方式：AI Studio 的 **Usage** 頁，或 Cloud Console 的 API 配額頁。

開發策略：
1. 前兩週幾乎只用文字模型，免費層夠用。
2. 圖片與 TTS 開發時，先用「mock 供應商」（Day 10）跑通流程，再切真實模型。
3. Veo 留到 Day 19，且一律以 ffmpeg Ken Burns 當預設，Veo 為可選。

## 在 AI Studio 先試一次腳本提示詞

在 AI Studio 新建一個 prompt，選 `gemini-2.5-flash`，右側 **Structured output** 開啟，貼入：

```
你是短影片編劇。根據主題「為什麼貓咪喜歡紙箱」，用繁體中文寫一支 60 秒的知識型短影片腳本。
輸出 JSON：{ "title": string, "scenes": [ { "narration": string, "image_prompt": string } ] }
每個場景旁白 30–50 字，image_prompt 用英文描述畫面，不要包含文字或字幕。共 5 個場景。
```

觀察輸出是否穩定符合 JSON。把好的版本記下來，Day 08 會把它變成程式碼。

## 給 Antigravity 的提示詞
```
在專案根目錄建立 config.example.yaml，內容包含：
gemini.api_key（空字串）、llm.model、image.model、tts.model、tts.voice、video.provider（預設 kenburns）。
再建立 easyaivideo/config.py，用 pydantic 讀取 config.yaml，若檔案不存在則從 config.example.yaml 複製。
api_key 若為空則 fallback 到環境變數 GEMINI_API_KEY。
```

## 今日檢查清單
- [ ] `echo $env:GEMINI_API_KEY`（或 `echo $GEMINI_API_KEY`）能印出金鑰。
- [ ] 在 AI Studio 成功跑出 JSON 格式的腳本。
- [ ] 知道哪些模型有免費層、哪些沒有。

## 明日預告
Day 04 寫第一支 Gemini 程式：安裝 `google-genai`、基本呼叫、串流輸出，以及用 Pydantic 定義 JSON Schema 拿到結構化結果。
