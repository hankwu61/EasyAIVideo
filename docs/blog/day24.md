# Day 24｜分鏡工作台：逐場景編輯、單場景重生與拖曳上傳

> 30 天打造 AI 短影片生成平台 — 第 24 天

## 今日目標
- 完成 `Workbench` 頁的左半邊：場景卡片列表。
- 每張卡片：縮圖、旁白、圖片提示詞、影片提示詞、過期標記、三個圖片按鈕。
- 新增／刪除／拖曳排序場景，上傳自己的圖片／語音／影片。

## 版面

```
┌ 標題列：專案名稱 [撰寫腳本][產生素材][合成影片] 進度條 ────────────────┐
├──────────────────────────┬─────────────────────────────────────┤
│ 場景 1  [縮圖]  ⋮拖曳       │  預覽區（Day 26）                     │
│  旁白 [textarea]  ▶ 0:08 ⟳ │                                     │
│  圖片提示詞 [textarea]  ⚠過期 │                                     │
│  影片提示詞 [textarea]      │                                     │
│  [重新產生][上傳][下載]     │                                     │
│ 場景 2 ...                 │                                     │
│ [+ 新增場景]               │                                     │
└──────────────────────────┴─────────────────────────────────────┘
```

## 場景卡片

```tsx
function SceneCard({ project, scene }: { project: Project; scene: Scene }) {
  const [draft, setDraft] = useState(scene);
  const save = useMutation({
    mutationFn: (b: SceneUpdate) => api.scenes.update(project.id, scene.id, b),
    onSuccess: (p) => qc.setQueryData(["project", project.id], p),
  });
  const debounced = useDebouncedCallback((b: SceneUpdate) => save.mutate(b), 600);

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 flex gap-4">
      <Thumb scene={scene} project={project} />
      <div className="flex-1 space-y-2">
        <Field label="旁白" stale={scene.audio_stale} value={draft.narration}
               onChange={v => { setDraft({ ...draft, narration: v }); debounced({ narration: v }); }} />
        <Field label="圖片提示詞" stale={scene.image_stale} value={draft.image_prompt} ... />
        <Field label="影片提示詞" value={draft.video_prompt} ... />
        <AudioRow scene={scene} onRegen={() => regenAudio.mutate()} />
      </div>
    </div>
  );
}
```

- 輸入後 600 毫秒自動存檔，回傳的 Project 直接寫進 React Query 快取，過期標記立即出現。
- `stale` 為 true 時欄位右上角顯示「已過期」黃色標籤，縮圖加半透明遮罩。

## 縮圖的三個按鈕

```tsx
<Thumb>
  <img src={`/data/${scene.image_path}?v=${project.updated_at}`} />
  <button onClick={regen}>重新產生</button>
  <button onClick={() => fileInput.current?.click()}>上傳</button>
  <a href={`/data/${scene.image_path}`} download>下載</a>
</Thumb>
```

`?v=` 破壞瀏覽器快取，重生後圖片會換。

## 拖曳上傳

把圖片直接拖到縮圖上：

```tsx
onDragOver={e => { e.preventDefault(); setHover(true); }}
onDrop={async e => {
  e.preventDefault(); setHover(false);
  const f = e.dataTransfer.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  const kind = f.type.startsWith("image/") ? "image" : f.type.startsWith("audio/") ? "audio" : "video";
  fd.append("kind", kind);
  await req("POST", `/api/projects/${project.id}/scenes/${scene.id}/upload`, fd, true);
  qc.invalidateQueries({ queryKey: ["project", project.id] });
}}
```

後端 `upload`：
- image → 轉成 PNG、裁到專案比例、覆蓋 `scene_XX.png`、`image_stale=False`、清空 `clip_path`。
- audio → 轉 wav 24k、用 ffprobe 取長度、`audio_stale=False`。
- video → 覆蓋 `clip_XX.mp4`、標記 `scene.motion_override="uploaded"`，之後動態階段跳過此場景。

## 新增／刪除／排序

- 新增：`POST /scenes` 在末尾加空場景，前端捲動到新卡片並聚焦旁白。
- 刪除：確認對話框，`DELETE /scenes/{sid}`，後端刪除對應檔案並重新編號。
- 排序：`@dnd-kit/sortable` 拖曳，放開後 `POST /scenes/reorder`。後端重編 `index`，檔名重新命名（`scene_03.png` → `scene_02.png`），避免檔名與順序不一致。

## 頂部三個按鈕的啟用規則

| 按鈕 | 可按條件 |
|---|---|
| 撰寫腳本 | 沒有任務進行中；若已有場景，先確認會覆蓋 |
| 產生素材 | 有場景，且存在過期或缺少的圖片／語音 |
| 合成影片 | 所有場景都有圖片與語音，且沒有過期 |

有任務時顯示進度條與「取消」。

## 給 Antigravity 的提示詞
```
實作 Workbench 左半：SceneCard（自動存檔、stale 標籤、縮圖三按鈕、拖曳上傳）、AudioRow（播放、時長、重生）、
新增/刪除/dnd-kit 排序、頂部三按鈕與啟用規則。後端補 scenes/{sid}/upload 三種 kind 的處理與 reorder 的檔案重新命名。
用瀏覽器修改第 2 場旁白、拖一張圖到第 3 場、把第 4 場拖到第 1 場，每步截圖。
```

## 今日檢查清單
- [ ] 改旁白後 1 秒內出現「已過期」，「產生素材」按鈕變成可按。
- [ ] 拖圖上傳後縮圖立即更新且沒有過期標記。
- [ ] 排序後重新整理頁面，順序與檔名都正確。

## 明日預告
Day 25 即時進度：輪詢與 Server-Sent Events 兩種做法，任務狀態的視覺化與錯誤呈現。
