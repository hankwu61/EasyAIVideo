# Day 18｜直式 9:16、橫式 16:9、方形 1:1：一份腳本三種輸出

> 30 天打造 AI 短影片生成平台 — 第 18 天

## 今日目標
- 讓比例成為貫穿整條管線的一等公民：圖片、字幕、Ken Burns、Veo 都依比例調整。
- 提供「換比例重新輸出」：腳本與語音沿用，只重做圖片與合成。
- 加入場景之間的轉場（交叉淡入淡出）。

## 比例影響哪些環節

| 環節 | 9:16 | 16:9 | 1:1 |
|---|---|---|---|
| 圖片尺寸 | 1080×1920 | 1920×1080 | 1080×1080 |
| 圖片提示詞 | "vertical portrait composition, subject centered" | "wide cinematic composition" | "square composition" |
| 字幕字級 | 高度 3.2% | 高度 4.5% | 高度 3.8% |
| 字幕字數上限 | 18 | 28 | 20 |
| 安全區底線 | 82% | 90% | 88% |
| Ken Burns | 直向平移較自然 | 橫向平移較自然 | 推近拉遠 |
| Veo | `aspect_ratio="9:16"` | `"16:9"` | 目前不支援，改用 16:9 後裁切 |

全部集中到 `presets.ASPECTS`：

```python
ASPECTS = {
    "9:16": dict(size=(1080, 1920), hint="vertical 9:16 portrait composition, subject centered",
                 sub_ratio=0.032, sub_chars=18, bottom=0.18, motions=["zoom_in", "pan_up", "pan_down"]),
    "16:9": dict(size=(1920, 1080), hint="wide 16:9 cinematic composition",
                 sub_ratio=0.045, sub_chars=28, bottom=0.10, motions=["zoom_in", "pan_left", "pan_right"]),
    "1:1":  dict(size=(1080, 1080), hint="square 1:1 composition",
                 sub_ratio=0.038, sub_chars=20, bottom=0.12, motions=["zoom_in", "zoom_out"]),
}
```

所有之前寫死數字的地方都改成讀這張表。

## 換比例重新輸出

使用者常常先做直式給 Shorts，又想要橫式給 YouTube。流程：

1. `POST /api/projects/{id}/duplicate?aspect=16:9`：複製專案（新 id、新資料夾）。
2. 複製時保留 `title`、`scenes[].narration / image_prompt / video_prompt / audio_path / audio_duration / cues`，把語音檔案實際複製過去。
3. 把 `image_stale=True`、清空 `image_path`、`clip_path`。
4. 使用者按「產生素材」只會重做圖片與動態，語音不用重花。

這就是 Day 07 設計 `stale` 旗標的回報。

## 轉場

concat demuxer 只能硬切。要交叉淡入淡出得用 `xfade`，一次串接所有場景並重編碼：

```python
def xfade_chain(n: int, durations: list[float], transition="fade", d=0.4) -> str:
    parts, prev, offset = [], "[0:v]", 0.0
    for i in range(1, n):
        offset += durations[i - 1] - d
        parts.append(f"{prev}[{i}:v]xfade=transition={transition}:duration={d}:offset={offset:.3f}[v{i}]")
        prev = f"[v{i}]"
    # 音訊對應用 acrossfade
    aparts, aprev = [], "[0:a]"
    for i in range(1, n):
        aparts.append(f"{aprev}[{i}:a]acrossfade=d={d}[a{i}]")
        aprev = f"[a{i}]"
    return ";".join(parts + aparts), prev, aprev
```

注意每次轉場會吃掉 `d` 秒總長度，時間軸與字幕 offset 要跟著減。轉場種類 `fade`、`dissolve`、`slideleft`、`circleopen` 等都可用，放進 `ProjectOptions.transition`，預設 `none`（用 concat）以保持速度。

## 輸出品質設定

```python
QUALITY = {
    "draft":  ["-preset", "ultrafast", "-crf", "28"],
    "normal": ["-preset", "veryfast", "-crf", "20"],
    "high":   ["-preset", "slow", "-crf", "17"],
}
```

工作台預覽用 `draft`，最後匯出用 `high`。

## 給 Antigravity 的提示詞
```
把 presets.ASPECTS 擴充成含 size/hint/sub_ratio/sub_chars/bottom/motions 的表，並把 image、overlay、kenburns、timeline 全部改成讀取此表。
實作 POST /api/projects/{id}/duplicate?aspect=（保留語音、標記圖片過期），ProjectOptions.transition 與 xfade 串接，
以及 QUALITY 三檔。對同一個專案輸出三種比例，各截一幀給我比較。
```

## 今日檢查清單
- [ ] 三種比例的字幕都清楚且在安全區內。
- [ ] 換比例複製後「產生素材」不會重新呼叫 TTS。
- [ ] `transition=fade` 時總長度等於場景總和減去轉場數 × 0.4 秒，字幕沒有錯位。

## 明日預告
Day 19 接上 Veo：文生影片、圖生影片、首尾幀三種模式，讓場景真的動起來。
