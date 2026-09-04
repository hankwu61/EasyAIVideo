# Day 24｜分鏡工作台：逐場景編輯、單場景重生與拖曳上傳

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 24 天

## 今日目標
- `Workbench` 左半：場景卡片列表。
- 卡片：縮圖、旁白、圖片／影片提示詞、過期標記、重生／上傳／下載、語音試聽。
- 新增／刪除／拖曳排序；拖圖片、音檔、影片到場景直接替換。

## 版面

```
標題列  專案名 [撰寫腳本][產生素材][合成影片]  進度條 ▓▓▓░░ 45% 場景圖 3/6  [取消]
┌ 場景 1 ─────────────────────────┐ ┌ 預覽（Day 26）┐
│ [縮圖] 旁白 [textarea] ▶ 0:08 ⟳   │ │              │
│        圖片提示詞 [textarea] ⚠過期 │ │              │
│        影片提示詞 [textarea]      │ │              │
│        [重生][上傳][下載] [AI片段▾]│ │              │
└──────────────────────────────┘ └──────────────┘
[+ 新增場景]
```

## 場景卡片

```tsx
function SceneCard({ project, scene, task }) {
  const [draft, setDraft] = useState(scene);
  const save = useMutation({ mutationFn: (b: SceneUpdate) => api.scenes.update(project.id, scene.id, b),
                             onSuccess: p => qc.setQueryData(["project", project.id], p) });
  const debounced = useDebouncedCallback((b: SceneUpdate) => save.mutate(b), 600);
  const busy = task?.scene_id === scene.id && task.status === "running";
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4 flex gap-4">
      <Thumb scene={scene} project={project} busy={busy} />
      <div className="flex-1 space-y-2">
        <Field label="旁白" stale={scene.audio_stale} value={draft.narration}
               onChange={v => { setDraft({ ...draft, narration: v }); debounced({ narration: v }); }} />
        <Field label="圖片提示詞" stale={scene.image_stale} ... />
        <Field label="影片提示詞" ... />
        <AudioRow scene={scene} onRegen={() => api.scenes.regenAudio(project.id, scene.id)} />
      </div>
    </div>
  );
}
```

輸入 600 毫秒後自動存，回傳的 Project 直接寫入快取；`stale` 立即顯示黃色「已過期」。`task.scene_id` 對應時縮圖轉圈。

## 縮圖三按鈕與拖曳上傳

```tsx
<img src={`/data/${scene.image_path}?v=${project.updated_at}`} />
<button onClick={regen}>重新產生</button> <button onClick={pick}>上傳</button> <a href={...} download>下載</a>
```

`onDrop`：依 `file.type` 判斷 image / audio / video，`POST scenes/{sid}/upload`：
- image → PNG、裁到比例、覆蓋 `scene_XX.png`、`image_stale=False`、清 `clip_path`。
- audio → 轉 mp3 24k、ffprobe 取長度、**沒有 words.json**（字幕退回比例估算）、`audio_stale=False`。
- video → 覆蓋 `clip_XX.mp4`、`motion_override="uploaded"`。

## 場景層級的 AI 片段開關

每張卡片右下角下拉：「沿用專案設定 / Ken Burns / AI 影片」，寫入 `motion_override`。這樣可以只讓第一場與最後一場用 Agnes 影片。

## 新增／刪除／排序

- 新增：末尾加空場景、捲動聚焦。
- 刪除：確認後 `DELETE`，後端刪檔並重編號。
- 排序：`@dnd-kit/sortable`，放開後 `POST scenes/reorder`，後端重編 `index` 並重新命名檔案。

## 頂部按鈕規則

| 按鈕 | 條件 |
|---|---|
| 撰寫腳本 | 無任務；已有場景時確認覆蓋 |
| 產生素材 | 有場景且存在過期或缺少的素材 |
| 合成影片 | 所有場景都有圖與語音且無過期 |

## 給 Claude Code 的提示詞
```
實作 Workbench 左半：SceneCard（自動存、stale、busy 轉圈、三按鈕、拖曳上傳）、AudioRow、motion_override 下拉、新增/刪除/排序、頂部按鈕規則。
後端補 upload 三種 kind 與 reorder 重新命名。用預覽：改第 2 場旁白、拖一張圖到第 3 場、把第 4 場拖到第 1，每步截圖並讀 console 錯誤。
```

## 今日檢查清單
- [ ] 改旁白 1 秒內出現過期，「產生素材」可按。
- [ ] 拖圖後縮圖更新且無過期。
- [ ] 排序後重新整理，順序與檔名正確。

## 明日預告
Day 25 即時進度：輪詢 hook、SSE 選項、錯誤翻譯、取消與任務歷史。
