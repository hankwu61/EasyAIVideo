# Day 27｜長文／小說 → 分集影片：內容分析、角色設定與分集規劃

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 27 天

## 今日目標
- 系列專案：匯入整本小說或長文件，拆成多集。
- Agnes 分析概要、角色（英文外觀、性別、自動配 Edge-TTS 聲音）、常見場景。
- 程式切分集 + 模型補標題摘要；每集一個子專案沿用工作台。

## 資料模型

```python
class Character(BaseModel):
    id: str; name: str; description: str; appearance: str
    gender: Literal["male", "female", "other"] = "other"
    voice: str = "zh-TW-HsiaoChenNeural"; image_path: str | None = None

class Episode(BaseModel):
    index: int; title: str; summary: str; start_char: int; end_char: int; project_id: str | None = None

class Series(BaseModel):
    id: str; title: str; source_text: str = ""
    synopsis: str = ""; genre: str = ""; themes: list[str] = []; world: str = ""
    characters: list[Character] = []; locations: list[str] = []; episodes: list[Episode] = []
    options: ProjectOptions = ProjectOptions()
    mode: Literal["narration", "drama"] = "narration"
    episode_target_seconds: int = 90
```

## 步驟一：匯入

沿用 `source_loader`，多檔累加，顯示總字數與預估集數。

## 步驟二：分析

Agnes 文字模型的上下文長度有限（依模型而定，數萬到十幾萬 token）。整本書可能超過，策略：**先摘要再分析**。

1. 把全文按 1.5 萬字切塊，每塊請模型輸出「本段劇情摘要 + 出場角色（名字、外觀線索）+ 場景」。
2. 把所有塊摘要合併，再請模型輸出最終的概要、角色表、場景表。

```python
ANALYZE_SYSTEM = """你是影視改編顧問。根據提供的內容輸出 JSON：
synopsis（300 字內）、genre、themes（3–5）、world（100 字內）、
characters（3–8 位：name、description、appearance（英文，具體到髮型／服裝／年齡／體型）、gender）、locations（3–8 個）。
只根據內容，不杜撰。只輸出 JSON。"""
```

配音自動配對：female → 曉臻／曉雨輪流，male → 雲哲（繁中只有一個男聲，不夠時用簡中雲希、雲健），旁白固定用系列聲音。角色卡片全部可改，並有「生成角色圖」（Day 12 的 character sheet）。

## 步驟三：分集

程式按段落切、模型補標題：

```python
def plan_episodes(text, target_seconds):
    chars_per_ep = target_seconds * 4 * 1.2
    ...  # 依段落累積到 chars_per_ep 就切
```

一次呼叫模型給每集區間的**前後各 300 字 + 中間摘要**，回 `[{index, title, summary}]`。前端可編輯與拖曳分界。

## 步驟四：生成集數

每集 = 子專案，`source_text` 為該集區間，帶 `characters` 與 `series_id`。改編提示詞是**濃縮重述**而非逐字：

```python
ADAPT_SYSTEM = """你是短影片編劇，把小說片段改編成約 {target_seconds} 秒的旁白解說影片。
故事概要：{synopsis}
角色（image_prompt 出現角色時必須貼上其 appearance）：{characters}
常見場景：{locations}
旁白濃縮重述本集劇情，保留關鍵對白與轉折；風格 {style}。只輸出 JSON。"""
```

「生成全部集數」依序排入任務佇列，系列頁顯示每集狀態與縮圖。

## 用 Claude Code 的子代理做分析驗證

「用一個子代理讀 `tests/fixtures/novel.txt` 前 3 章，列出出場角色與外觀描述，再和 `/analyze` 的輸出比對，指出遺漏。」把驗證工作交給子代理，主對話保持乾淨。

## 給 Claude Code 的提示詞
```
新增 Series/Character/Episode 與 series 表、routers/series.py（建立、匯入、analyze 兩階段摘要、plan、generate_episode、generate_all）、
ANALYZE_SYSTEM/ADAPT_SYSTEM、plan_episodes、Edge-TTS 聲音自動配對、SeriesWorkbench 四步驟頁。
用一篇 2 萬字公有領域小說測試分析與分集，截圖角色卡與分集列表。
```

## 今日檢查清單
- [ ] 2 萬字分析在 90 秒內完成，appearance 是具體英文。
- [ ] 集數 ≈ 字數 ÷ (目標秒數 × 4.8)。
- [ ] 第 1 集與第 5 集主角圖外觀一致。

## 明日預告
Day 28 劇情演繹模式：角色台詞、Edge-TTS 多聲音逐行合成、說話者字幕。
