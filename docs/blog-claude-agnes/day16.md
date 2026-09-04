# Day 16｜用 PIL 繪製標題與字幕圖層：中文字型、描邊與安全區

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 16 天

## 今日目標
- `services/overlay.py`：透明 PNG 字幕與標題圖層。
- 字型自動偵測（`render.font_path` 可覆寫）、描邊、換行、安全區。
- 兩種字幕樣式：`plain` 與 `karaoke`（用 Day 14 的逐字時間）。

## 為什麼用 PIL 而不是 drawtext

Windows 上 `drawtext` 的字型路徑跳脫是惡夢；`subtitles` 濾鏡需要 libass。PIL 完全掌控字型、描邊、底框，且能離線預覽。

## 字型偵測

```python
CANDIDATES = {
    "Windows": ["C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/mingliu.ttc"],
    "Darwin": ["/System/Library/Fonts/PingFang.ttc"],
    "Linux": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"],
}
def find_font(cfg) -> Path:
    if cfg.render.font_path and Path(cfg.render.font_path).exists():
        return Path(cfg.render.font_path)
    for f in Path("resources/fonts").glob("*.[to]t[fc]"):
        return f
    for c in CANDIDATES.get(platform.system(), []):
        if Path(c).exists(): return Path(c)
    raise ProviderError("找不到中文字型，請在設定頁指定 font_path 或放入 resources/fonts/")
```

## 字幕圖層

```python
def render_subtitle(text, size, *, font_path, font_size, bottom_ratio, out) -> Path:
    w, h = size
    font = ImageFont.truetype(str(font_path), font_size)
    img = Image.new("RGBA", size, (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    lines = wrap(text, font, int(w * 0.86), d)
    line_h = int(font_size * 1.35); y = int(h * (1 - bottom_ratio)) - line_h * len(lines)
    for line in lines:
        x = (w - d.textlength(line, font=font)) / 2
        d.text((x, y), line, font=font, fill="white", stroke_width=max(2, font_size // 12), stroke_fill="black")
        y += line_h
    img.save(out); return out
```

`font_size` 來自 `render.subtitle_size`（預設 56）依比例縮放：直式 ×1、橫式 ×1.3、方形 ×1.15。

## 安全區

| 比例 | 字幕底線 | 左右邊界 |
|---|---|---|
| 9:16 | 82% | 7% |
| 16:9 | 90% | 5% |
| 1:1 | 88% | 6% |

標題在頂部 8% 以下，只在第一場前 3 秒出現，圓角半透明底框。

## 卡拉 OK 樣式

底層：白字整句。上層：黃字整句，ffmpeg 用 `crop` 隨時間展開：

```
[hl]crop=w='min(iw, iw*(t-{s})/{dur})':h=ih:x=0:y=0[hlc]; [base][hlc]overlay=0:0
```

`s` 是該句開始、`dur` 是該句長度。逐字精準需要每個字的寬度，進階版用 `words` 逐字算 `crop` 寬度序列（`if(lt(t,t1),w1,if(lt(t,t2),w2,...))`）。先做線性版本，已經很像了。

## 疊到片段

```python
def overlay_chain(cues, scene_start, first_input=1):
    parts, prev = [], "[0:v]"
    for i, c in enumerate(cues):
        idx = first_input + i
        s, e = c.start - scene_start, c.end - scene_start
        parts.append(f"{prev}[{idx}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[v{idx}]")
        prev = f"[v{idx}]"
    return ";".join(parts), prev
```

## 給 Claude Code 的提示詞
```
實作 services/overlay.py（find_font、wrap、render_subtitle、render_title、karaoke 雙層輸出）與 ffmpeg.overlay_chain。
寫 scripts/preview_subtitle.py 對三種比例各輸出範例圖層疊在 placeholder 上，三張圖給我看；另外輸出一段 5 秒 karaoke 範例影片。
```

## 今日檢查清單
- [ ] 三種比例字幕在安全區、置中、黑邊清楚。
- [ ] 長句自動換行不超過兩行。
- [ ] 設定頁指定 `font_path` 後立即生效。

## 明日預告
Day 17 串接場景、混入 BGM、響度正規化，產出第一支完整影片。
