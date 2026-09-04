# Day 18｜直式 9:16、橫式 16:9、方形 1:1：一份腳本三種輸出

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 18 天

## 今日目標
- 比例貫穿全管線：圖片尺寸、提示詞、字幕、Ken Burns、Agnes 影片。
- 「換比例重輸出」：語音與時間戳沿用，只重做圖片與合成。
- xfade 轉場與三檔輸出品質。

## 比例影響表

| 環節 | 9:16 | 16:9 | 1:1 |
|---|---|---|---|
| 圖片（short_edge 1024） | 1024×1816 | 1816×1024 | 1024×1024 |
| 提示詞附註 | vertical portrait, subject centered | wide cinematic | square |
| 字幕字級倍率 / 字數 | 1.0 / 18 | 1.3 / 28 | 1.15 / 20 |
| 安全區底線 | 82% | 90% | 88% |
| Ken Burns 偏好 | zoom_in、pan_up/down | zoom_in、pan_left/right | zoom_in/out |
| Agnes 影片（720p） | 720×1280 | 1280×720 | 720×720 |

集中在 `presets.ASPECTS`，所有寫死的地方改讀表。

## 換比例複製

`POST /api/projects/{id}/duplicate?aspect=16:9`：
1. 新 id、新資料夾。
2. 保留 title、scenes 的文字欄位、`audio_path`、`words_path`、`audio_duration`、`cues`，並實際複製 mp3 與 words.json。
3. `image_stale=True`、清空 `image_path`、`clip_path`。
4. 按「產生素材」只重做圖片與動態，Edge-TTS 雖免費，但省下的是時間。

## xfade 轉場

```python
def xfade_chain(n, durations, transition="fade", d=0.4):
    vparts, prev, offset = [], "[0:v]", 0.0
    for i in range(1, n):
        offset += durations[i-1] - d
        vparts.append(f"{prev}[{i}:v]xfade=transition={transition}:duration={d}:offset={offset:.3f}[v{i}]"); prev = f"[v{i}]"
    aparts, aprev = [], "[0:a]"
    for i in range(1, n):
        aparts.append(f"{aprev}[{i}:a]acrossfade=d={d}[a{i}]"); aprev = f"[a{i}]"
    return ";".join(vparts + aparts), prev, aprev
```

每個轉場吃掉 `d` 秒，時間軸與字幕的絕對時間要扣除。`ProjectOptions.transition: none | fade | dissolve | slideleft | circleopen`，預設 `none` 走 concat（快）。

## 輸出品質

```python
QUALITY = {"draft": ("ultrafast", 28), "normal": ("veryfast", 23), "high": ("slow", 18)}
```

`render.crf` 為 normal 的預設；工作台預覽用 draft，匯出用 high。

## 給 Claude Code 的提示詞
```
把 presets.ASPECTS 擴成含 size/hint/sub_scale/sub_chars/bottom/motions/video_size 的表並全面改用；
實作 duplicate?aspect=、transition 與 xfade_chain（含時間軸扣除）、QUALITY 三檔。
對同一專案輸出三種比例，各抽一幀給我比較。
```

## 今日檢查清單
- [ ] 三種比例字幕都在安全區。
- [ ] 換比例後「產生素材」沒有呼叫 TTS。
- [ ] `fade` 轉場時總長 = 場景總和 − 轉場數 × 0.4，字幕不錯位。

## 明日預告
Day 19 Agnes 影片生成：非同步提交、輪詢、下載，三種模式與片長規則。
