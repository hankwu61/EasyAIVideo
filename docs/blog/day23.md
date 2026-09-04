# Day 23｜新增專案表單：主題、語言、風格、比例、聲音與 BGM 選擇

> 30 天打造 AI 短影片生成平台 — 第 23 天

## 今日目標
- 完成 `NewProject` 頁：主題／文稿兩種輸入、上傳文件、所有選項。
- 聲音與 BGM 可試聽；風格有縮圖預覽。
- 「建立並開始生成」一鍵排入完整流程，並跳轉到工作台。

## 表單結構

```
┌ 內容來源 ──────────────────────────────┐
│ ( ) 主題   [為什麼貓咪喜歡紙箱          ] │
│ ( ) 文稿   [貼上文字…            ] [上傳] │
├ 影片設定 ──────────────────────────────┤
│ 語言 [繁體中文 ▾]  目標長度 [60 秒 ▾]    │
│ 比例 [9:16] [16:9] [1:1]                │
│ 風格 [電影感][動漫][扁平][水彩][3D]     │
│ 聲音 [Kore ▾] ▶試聽   語氣 [沿用風格 ▾] │
│ 背景音樂 [無 ▾] ▶試聽   音量 ───o───     │
│ 鏡頭動態 ( ) Ken Burns ( ) AI 影片(Veo) │
│ [x] 字幕  [x] 顯示標題  轉場 [無 ▾]      │
├──────────────────────────────────────┤
│           [ 只建立 ]  [ 建立並開始生成 ]  │
└──────────────────────────────────────┘
```

## 表單狀態

用 `react-hook-form` 或簡單的 `useState<ProjectCreate>`。選項初始值來自 `GET /api/presets` 的預設，記住使用者上次的選擇（`localStorage`）。

```tsx
const { data: presets } = useQuery({ queryKey: ["presets"], queryFn: api.presets });
const [form, setForm] = useState<ProjectCreate>(() => loadLast() ?? defaultForm);

const create = useMutation({
  mutationFn: (start: boolean) => api.projects.create({ ...form, start }),
  onSuccess: (p) => { saveLast(form); qc.invalidateQueries({ queryKey: ["projects"] }); navigate(`/projects/${p.id}`); },
});
```

後端 `ProjectCreate.start=true` 時，建立專案後直接 `queue.submit(full)`，回傳的 Project 帶 `active_task_id`，工作台一打開就能顯示進度。

## 文稿上傳

```tsx
<input type="file" accept=".txt,.md,.docx,.pdf,.epub" onChange={async e => {
  const f = e.target.files?.[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  const { text } = await req<{ text: string }>("POST", "/api/source/extract", fd, true);
  setForm(s => ({ ...s, source_text: text }));
}} />
```

`POST /api/source/extract` 只做文字擷取不建專案，讓使用者上傳後還能編輯內容再送出。顯示字數與預估片長（字數 ÷ 4 秒）。

## 聲音試聽

```tsx
async function preview(voice: string) {
  const res = await fetch("/api/tts/preview", { method: "POST", headers: {...}, body: JSON.stringify({ voice, text: "你好，這是聲音試聽。" }) });
  const blob = await res.blob();
  new Audio(URL.createObjectURL(blob)).play();
}
```

後端有快取（Day 13），所以反覆點不會扣費。

## 風格預覽圖

每種風格放一張預先生成的縮圖在 `frontend/public/styles/<id>.jpg`，用同一個提示詞「a cat sitting in a cardboard box」以不同風格生成，讓使用者直覺理解差異。

## BGM 選單

`GET /api/bgm` 回 `[{name, duration}]`，點試聽用 `<audio src="/data/bgm/<name>">`。音量滑桿對應 `options.bgm_volume`（0.05–0.4，預設 0.18）。

## 鏡頭動態的提示

選 AI 影片時，表單下方即時顯示：「預估 6 段 × 8 秒 Veo，需付費層」，並在沒有金鑰或供應商設為 kenburns 時反灰，引導到設定頁。

## 驗證

- 主題模式：主題不可空、200 字內。
- 文稿模式：至少 50 字。
- 送出後按鈕鎖定，錯誤顯示在表單頂端（用 `ApiError.detail`）。

## 給 Antigravity 的提示詞
```
實作 NewProject 頁：主題/文稿切換、文件上傳（POST /api/source/extract）、語言/長度/比例/風格（含縮圖）/聲音（試聽）/語氣/BGM（試聽＋音量）/
鏡頭動態/字幕/標題/轉場，記住上次選項，「只建立」與「建立並開始生成」兩個按鈕。後端補 /api/source/extract 與 ProjectCreate.start。
用瀏覽器填一次表單並送出，截圖表單與跳轉後的畫面。
```

## 今日檢查清單
- [ ] 送出後 2 秒內跳到工作台且能看到任務進度。
- [ ] 上傳 docx 後文字出現在文稿框並可編輯。
- [ ] 聲音與 BGM 試聽正常，重複點不會產生新的 API 呼叫。

## 明日預告
Day 24 分鏡工作台：逐場景編輯旁白與提示詞、單場景重生、拖曳上傳自己的圖片／語音、新增刪除排序。
