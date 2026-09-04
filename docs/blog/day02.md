# Day 02｜安裝 Antigravity IDE：Agent Manager、Editor 與 vibe coding 心法

> 30 天打造 AI 短影片生成平台 — 第 2 天

## 今日目標
- 安裝 Antigravity IDE 並登入 Google 帳號。
- 理解 Agent Manager 與 Editor 兩種工作視圖。
- 建立一套 30 天都適用的 vibe coding 工作流程。

## Antigravity 是什麼

Antigravity 是 Google 推出的 agent-first IDE。它以 VS Code 為基底，所以熟悉的快捷鍵、擴充套件都能用，但核心差異在於：

- **Agent Manager**：一個像「任務控制台」的視圖，可以同時派多個 Agent 平行處理不同任務（例如一個寫後端、一個寫前端）。
- **Editor**：傳統的編輯器視圖，右側有 Agent 側欄，適合一邊看程式一邊對話。
- **Artifacts**：Agent 在執行任務時會產出「任務清單」「實作計畫」「Walkthrough」等文件，讓你在它動手前先審閱計畫，而不是只看到最後的 diff。
- **內建瀏覽器代理**：Agent 可以自己開瀏覽器測試網頁、截圖、看 console 錯誤，這對我們之後做前端工作台非常有用。
- **多模型**：預設使用 Gemini 3 系列，也可以切換其他模型。

## 安裝

1. 到 [antigravity.google](https://antigravity.google/) 下載對應平台的安裝檔（Windows / macOS / Linux）。
2. 安裝後用 Google 帳號登入。
3. 第一次啟動可以匯入 VS Code 的設定與擴充套件，建議直接匯入。
4. 開啟昨天建立的 `EasyAIVideo` 資料夾。

## 兩種模式：Planning 與 Fast

在對話框旁邊可以切換模式：

- **Planning**：Agent 先產出實作計畫（Artifact），你審閱、留言修改後它才動手。適合「新增一個模組」這種中大型任務。
- **Fast**：直接執行，適合「幫我把這個函式改成 async」這種小修改。

原則：**看不清楚邊界的任務用 Planning，邊界清楚的用 Fast。**

## vibe coding 心法

vibe coding 不是「什麼都丟給 AI」，而是把自己的角色從「打字的人」變成「產品經理 + 審查者」。三個原則：

### 1. 先寫規格，再寫程式
每天開工前，先用一段文字把今天要做的模組描述清楚：輸入、輸出、邊界情況、不做什麼。這段文字就是給 Agent 的提示詞，也是你自己的驗收標準。

### 2. 小步快跑，每步可驗證
一次只讓 Agent 做一個可以驗證的單位。例如「寫出 `providers/llm/gemini.py`，並附上一個能直接執行的 `if __name__ == "__main__"` 範例」，而不是「把整個 AI 管線寫完」。

### 3. 把知識沉澱在專案裡
Antigravity 支援專案層級的「知識」（knowledge）與規則檔。把架構決策、命名慣例、不要碰的檔案（例如 `config.yaml` 含真實金鑰）寫進去，Agent 就不會每次都重新猜。

## 建立專案規則檔

在專案根目錄建立 `.agent/rules.md`（或 Antigravity 設定中的自訂規則），內容像這樣：

```markdown
# EasyAIVideo 開發規則
- Python 3.11，套件用 uv 管理，執行指令一律 `uv run ...`。
- 後端程式放在 `easyaivideo/`，前端放在 `frontend/`。
- 所有 AI 呼叫都經過 `easyaivideo/providers/` 的抽象介面，不要在 router 或 service 直接呼叫 SDK。
- `config.yaml` 含使用者的真實 API Key，永遠不要覆寫或提交；改用 `config.example.yaml`。
- 新增功能時附上可以直接執行的最小範例或測試。
- 註解與 UI 文字使用繁體中文，程式識別字用英文。
```

## 給 Antigravity 的提示詞
第一個任務，用 Planning 模式：

```
請在目前空專案中初始化 git，建立 .gitignore（Python、Node、.venv、data/、config.yaml），
建立 README.md 寫上專案一句話描述，並建立 .agent/rules.md 放入我提供的開發規則。
完成後列出你建立的檔案。
```

觀察 Agent 產出的計畫 Artifact，確認它沒有多做（例如不要幫你先裝一堆套件）。

## 今日檢查清單
- [ ] Antigravity 已安裝並登入。
- [ ] 能切換 Agent Manager / Editor 視圖，知道 Planning / Fast 的差別。
- [ ] 專案已有 `.gitignore`、`README.md`、`.agent/rules.md`。

## 明日預告
Day 03 到 Google AI Studio 取得 Gemini API Key，認識可用的模型（文字、圖片、TTS、Veo）與免費／付費配額。
