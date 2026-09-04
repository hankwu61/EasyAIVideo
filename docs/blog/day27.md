# Day 27｜長文／小說 → 分集影片：內容分析、角色設定與分集規劃

> 30 天打造 AI 短影片生成平台 — 第 27 天

## 今日目標
- 新增「系列專案」：匯入整本小說或長文件，拆成多集短影片。
- 用 Gemini 分析概要、角色（含英文外觀描述與配音）、常見場景。
- 依目標長度規劃分集，每集變成一個沿用工作台的子專案。

## 系列專案的資料模型

```python
class Character(BaseModel):
    id: str; name: str; description: str        # 性格、角色定位
    appearance: str                             # 英文外觀描述，給圖片模型
    gender: Literal["male", "female", "other"] = "other"
    voice: str = "Kore"                         # 依性別自動配對
    image_path: str | None = None

class Episode(BaseModel):
    index: int; title: str; summary: str
    start_char: int; end_char: int              # 對應原文的區間
    project_id: str | None = None               # 子專案

class Series(BaseModel):
    id: str; title: str
    source_text: str = ""
    synopsis: str = ""; genre: str = ""; themes: list[str] = []; world: str = ""
    characters: list[Character] = []
    locations: list[str] = []
    episodes: list[Episode] = []
    options: ProjectOptions = ProjectOptions()
    mode: Literal["narration", "drama"] = "narration"   # Day 28
    episode_target_seconds: int = 90
```

存在 SQLite 的 `series` 表，同樣整包 JSON。

## 步驟一：匯入文檔

沿用 Day 09 的 `source_loader`，支援多檔累加（一本書可能是多個章節檔）。前端顯示總字數與預估集數。

## 步驟二：內容分析

長文本正是 Gemini 大上下文的用武之地，整本書直接送：

```python
ANALYZE_SYSTEM = """你是影視改編顧問。閱讀全文後輸出：
- synopsis：300 字內故事概要
- genre、themes（3–5 個）、world（世界觀與時代背景，100 字內）
- characters：主要角色 3–8 位，每位含 name、description（性格與定位）、appearance（英文，具體到髮型、服裝、年齡、體型，供圖片模型使用）、gender
- locations：反覆出現的場景 3–8 個（中文）
只根據原文，不要杜撰。"""
```

超過模型上限（極少見）時取頭、中、尾各 20 萬字。

配音自動配對：`gender=female` 從 Kore/Aoede/Leda 輪流，`male` 從 Puck/Charon/Fenrir 輪流，旁白固定用系列的 `options.voice`。

分析結果可以在前端全部手動修改。角色卡片有「生成角色圖」按鈕（Day 12 的 character sheet），之後每一集的場景圖都會帶這張參考圖，讓主角在 20 集裡長得一樣。

## 上下文快取

同一本書會被送給模型很多次（分析、分集、每集改編）。用 Gemini 的 context caching 把原文快取起來，之後每次呼叫只付快取讀取的價格：

```python
cache = await client.aio.caches.create(
    model="gemini-2.5-flash",
    config=types.CreateCachedContentConfig(
        contents=[series.source_text], system_instruction=ANALYZE_SYSTEM, ttl="3600s"))
resp = await client.aio.models.generate_content(
    model="gemini-2.5-flash", contents="請分析。",
    config=types.GenerateContentConfig(cached_content=cache.name, response_schema=Analysis, ...))
```

快取名稱存在 `series.cache_name`，過期就重建。

## 步驟三：規劃分集

分集是**程式切 + 模型補標題**，不讓模型決定切點，避免它漏掉段落：

```python
def plan_episodes(text: str, target_seconds: int) -> list[tuple[int, int]]:
    chars_per_ep = target_seconds * 4 * 1.2        # 旁白濃縮比例約 1:1.2
    paras = paragraph_spans(text)                 # [(start, end), ...]
    eps, cur_start, cur_len = [], 0, 0
    for s, e in paras:
        cur_len += e - s
        if cur_len >= chars_per_ep:
            eps.append((cur_start, e)); cur_start, cur_len = e, 0
    if cur_len: eps.append((cur_start, len(text)))
    return eps
```

然後一次呼叫 Gemini，給每集區間的文字，要它回 `[{index, title, summary}]`。標題與摘要都可以在前端編輯，也可以拖曳調整分界。

## 步驟四：生成集數

每集 = 一個子專案：

```python
async def create_episode_project(self, series: Series, ep: Episode) -> Project:
    p = Project(topic=f"{series.title} 第 {ep.index} 集：{ep.title}", options=series.options,
                source_text=series.source_text[ep.start_char:ep.end_char],
                series_id=series.id, episode_index=ep.index, characters=series.characters)
    ...
```

改編提示詞與一般文稿不同：不是逐字保留，而是**濃縮重述**，並帶入概要、角色外觀、場景清單：

```python
ADAPT_SYSTEM = """你是短影片編劇，把小說片段改編成約 {target_seconds} 秒的旁白解說影片。
故事概要：{synopsis}
角色（image_prompt 中出現角色時必須使用其英文外觀描述）：{characters}
常見場景：{locations}
規則：旁白濃縮重述本集劇情，保留關鍵對白與轉折；每場 image_prompt 若含角色，直接貼上該角色的 appearance；風格 {style}。"""
```

前端「生成全部集數」把每集依序排入任務佇列（Day 20），可以在系列頁看到每集的狀態與縮圖，點進去就是熟悉的工作台。

## 給 Antigravity 的提示詞
```
新增 Series/Character/Episode 模型與 series 表、routers/series.py（建立、匯入多檔、analyze、plan、generate_episode、generate_all）、
prompts 的 ANALYZE_SYSTEM 與 ADAPT_SYSTEM、context caching、plan_episodes 切分、角色配音自動配對、
前端 SeriesWorkbench 頁（四個步驟分頁）。用一篇 2 萬字的公有領域小說測試分析與分集，截圖角色卡片與分集列表。
```

## 今日檢查清單
- [ ] 匯入 2 萬字後分析在 60 秒內完成，角色 appearance 是具體的英文描述。
- [ ] 分集數 ≈ 字數 ÷ (目標秒數 × 4.8)。
- [ ] 第 1 集與第 5 集的主角圖片外觀一致。

## 明日預告
Day 28 劇情演繹模式：角色各說各的台詞、多說話者 TTS、逐句依語音時間顯示並標示說話者的字幕。
