# Day 23｜新增專案表單：主題、語言、風格、比例、聲音試聽與 BGM

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 23 天

## 今日目標
- `NewProject` 頁：主題／文稿切換、文件上傳、所有選項。
- Edge-TTS 聲音試聽、BGM 試聽與音量、風格縮圖。
- 「建立並開始生成」一鍵排入完整流程並跳轉工作台。

## 表單結構

```
內容來源   ( ) 主題 [____________]   ( ) 文稿 [textarea] [上傳 txt/md/docx/pdf/epub]
影片設定   語言 [繁中▾]  目標長度 [60 秒▾]   比例 [9:16][16:9][1:1]
           風格 [電影感][動漫][扁平][水彩][3D]（縮圖）
           聲音 [曉臻（女）▾] ▶試聽   語速 ──o──  1.0
           背景音樂 [無▾] ▶試聽   音量 ──o──  0.2
           鏡頭動態 ( ) Ken Burns ( ) AI 影片（Agnes）   [x] 字幕 [x] 標題  轉場 [無▾]
           [ 只建立 ]  [ 建立並開始生成 ]
```

## 狀態與送出

```tsx
const { data: presets } = useQuery({ queryKey: ["presets"], queryFn: api.presets });
const { data: voices } = useQuery({ queryKey: ["voices"], queryFn: api.tts.voices });
const [form, setForm] = useState<ProjectCreate>(() => loadLast() ?? defaults);
const create = useMutation({
  mutationFn: (start: boolean) => api.projects.create({ ...form, start }),
  onSuccess: p => { saveLast(form); qc.invalidateQueries({ queryKey: ["projects"] }); navigate(`/projects/${p.id}`); },
});
```

`start=true` 時後端建立後直接 submit `full` 任務，回傳的 Project 帶 `active_task_id`。

## 文稿上傳

```tsx
const fd = new FormData(); fd.append("file", f);
const { text } = await req<{ text: string }>("POST", "/api/source/extract", fd, true);
setForm(s => ({ ...s, source_text: text }));
```

顯示字數與預估片長（字數 ÷ 4 秒）。

## 聲音試聽

```tsx
async function preview(voice: string, speed: number) {
  const res = await fetch("/api/tts/preview", { method: "POST", headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ voice, speed, text: "你好，這是聲音試聽。" }) });
  new Audio(URL.createObjectURL(await res.blob())).play();
}
```

聲音下拉依語言過濾：語言選繁中只顯示 `zh-TW`，選粵語顯示 `zh-HK`。使用者可勾「顯示全部聲音」載入 `edge_tts.list_voices()` 的完整清單。

## AI 影片提示

選 AI 影片時顯示「預估 6 段 × 10 秒，Agnes 影片按秒計費」，`video.provider` 不是 agnes 或沒金鑰時反灰並連到設定頁。

## 驗證

主題非空且 200 字內；文稿至少 50 字；送出鎖定按鈕；錯誤顯示 `ApiError.detail`。

## 給 Claude Code 的提示詞
```
實作 NewProject 頁（主題/文稿、上傳、語言/長度/比例/風格縮圖/聲音依語言過濾+試聽/語速/BGM+音量/鏡頭動態/字幕/標題/轉場、記住上次選項、兩個按鈕）。
後端補 ProjectCreate.start 與 active_task_id、GET /api/tts/voices?all=1。用預覽填一次表單送出並截圖。
```

## 今日檢查清單
- [ ] 送出後 2 秒內到工作台並看到進度。
- [ ] 上傳 docx 後可編輯。
- [ ] 試聽重複點不打 TTS（看後端 log）。

## 明日預告
Day 24 分鏡工作台：場景卡片、自動存檔、過期標記、單場景重生、拖曳上傳與排序。
