# Day 02｜安裝 Claude Code：CLAUDE.md、Plan 模式與 vibe coding 工作流

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 2 天

## 今日目標
- 安裝 Claude Code（終端機或桌面 App）並登入。
- 理解 `CLAUDE.md`、Plan 模式、權限模式、`/init`、`@` 檔案引用。
- 建立一套 30 天都適用的每日節奏。

## 安裝

```bash
npm install -g @anthropic-ai/claude-code
cd EasyAIVideo
claude
```

第一次啟動會引導登入。也可以用 Claude 桌面 App 的 Code 分頁開啟資料夾，功能相同，還多了瀏覽器預覽面板。

## Claude Code 的四個核心概念

### 1. CLAUDE.md：專案記憶
根目錄的 `CLAUDE.md` 每次對話都會被載入。放「它應該永遠知道的事」：架構、指令、慣例、不要碰的檔案。`/init` 可以自動產生初稿，但我們自己寫更精準：

```markdown
# EasyAIVideo

## 架構
- easyaivideo/：FastAPI 後端。routers → services → providers 三層，router 不含業務邏輯，service 不直接呼叫 HTTP。
- frontend/：React + Vite + Tailwind。
- data/：專案素材與 SQLite，不進 git。

## 指令
- 安裝：`uv sync`；啟動：`uv run easyaivideo --port 8000`；測試：`uv run pytest -q`
- 前端：`cd frontend && npm run dev`（開發）/ `npm run build`（正式）

## 慣例
- Python 3.11，型別註解，async 優先；HTTP 用 httpx.AsyncClient，不裝供應商 SDK。
- 所有 AI 呼叫都經過 providers/ 的抽象介面。
- 註解與 UI 文字繁體中文，識別字英文。
- 新功能附最小可執行範例或測試。

## 禁區
- config.yaml 含真實 API Key：不要讀取內容到對話、不要覆寫、不要提交。改 config.example.yaml。
- 不要在未詢問的情況下呼叫會扣費的圖片／影片 API；測試用 mock 供應商。
```

### 2. Plan 模式
按 `Shift+Tab` 切換到 Plan 模式，Claude 只會讀程式與提出計畫，不改任何檔案。中大型任務先在 Plan 模式看計畫，確認後再切回執行。

### 3. 權限
預設每個檔案修改與指令都會詢問。常用的安全指令（`uv run pytest`、`npm run build`、`git status`）可以在 `.claude/settings.json` 允許，減少打斷：

```json
{
  "permissions": {
    "allow": ["Bash(uv run pytest*)", "Bash(uv run python*)", "Bash(npm run build*)", "Bash(git status*)", "Bash(git diff*)"]
  }
}
```

### 4. `@` 引用與斜線指令
- `@easyaivideo/services/pipeline.py` 把檔案帶進上下文。
- `/clear` 清空對話（換任務時用，省 token）。
- `/compact` 壓縮對話保留重點。
- `/commit`（若有此指令）或直接請它「用 conventional commits 提交」。

## 每日節奏

1. **開工**：`claude`，第一句話描述今天的模組：輸入、輸出、邊界、不做什麼。
2. **Plan**：中型以上任務先 Plan 模式，看它列出要動的檔案。
3. **執行**：一次一個可驗證的單位。要求「寫完跑測試並把結果貼給我」。
4. **驗證**：後端看 pytest 與 curl；前端請它用瀏覽器面板截圖。
5. **沉澱**：它犯了兩次同樣的錯，就把規則寫進 `CLAUDE.md`。
6. **提交**：`git add -A && git commit`，或請 Claude 提交並寫訊息。

## 子代理與 hooks（進階，第三週後會用到）

- 子代理：「用一個 Explore 子代理找出所有呼叫 ffmpeg 的地方」，主對話不會被大量檔案內容塞滿。
- hooks：在 `.claude/settings.json` 設定「每次編輯 Python 檔後自動跑 ruff」，讓格式問題不用你提醒。

## 給 Claude Code 的提示詞
```
初始化 git，建立 .gitignore（Python、Node、.venv、data/、config.yaml、frontend/dist），
把我提供的 CLAUDE.md 內容寫入根目錄，建立 .claude/settings.json 允許 uv run pytest、uv run python、npm run build、git status、git diff。
完成後列出建立的檔案，不要安裝任何套件。
```

## 今日檢查清單
- [ ] `claude` 能啟動並讀到 `CLAUDE.md`（問它「這個專案的架構是什麼」）。
- [ ] 能切換 Plan 模式。
- [ ] `.gitignore`、`.claude/settings.json` 存在，`git log` 有第一個 commit。

## 明日預告
Day 03 到 Agnes AI 取得 API Key，認識 OpenAI 相容端點與文字／圖片／影片模型。
