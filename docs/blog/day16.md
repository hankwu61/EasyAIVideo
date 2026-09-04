# Day 16｜用 PIL 繪製標題與字幕圖層：中文字型、描邊與安全區

> 30 天打造 AI 短影片生成平台 — 第 16 天

## 今日目標
- 建立 `services/overlay.py`：用 PIL 產生透明 PNG 的標題與字幕圖層。
- 解決中文字型尋找、描邊、自動換行與安全區。
- 讓 ffmpeg 用 `overlay` 濾鏡在指定時間段疊上字幕。

## 為什麼不用 ffmpeg 的 drawtext / subtitles 濾鏡

- `drawtext` 在 Windows 上字型路徑要跳脫冒號與反斜線，中文常常出錯。
- `subtitles` 濾鏡需要 libass，有些 ffmpeg 版本沒編進去，且樣式控制有限。
- PIL 畫圖層：完全掌控字型、描邊、陰影、圓角底框，且可以事先預覽。

代價是多幾個 PNG 檔，完全可接受。

## 字型尋找

```python
from pathlib import Path
import platform

FONT_CANDIDATES = {
    "Windows": ["C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/mingliu.ttc"],
    "Darwin": ["/System/Library/Fonts/PingFang.ttc", "/Library/Fonts/Arial Unicode.ttf"],
    "Linux": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"],
}

def find_font(preferred: str | None = None) -> Path:
    local = Path("resources/fonts")
    if local.exists():
        for f in local.glob("*.[to]t[fc]"):
            return f
    for cand in FONT_CANDIDATES.get(platform.system(), []):
        if Path(cand).exists():
            return Path(cand)
    raise FileNotFoundError("找不到中文字型，請把字型檔放到 resources/fonts/")
```

專案內 `resources/fonts/` 優先，方便部署到 Linux 容器時自帶字型。

## 字幕圖層

```python
from PIL import Image, ImageDraw, ImageFont

def render_subtitle(text: str, size: tuple[int, int], *, font_path: Path, font_size: int | None = None,
                    bottom_ratio: float = 0.18, out: Path) -> Path:
    w, h = size
    font_size = font_size or int(h * 0.032)               # 直式 1920 → 61px
    font = ImageFont.truetype(str(font_path), font_size)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    lines = wrap(text, font, max_width=int(w * 0.86), draw=d)
    line_h = int(font_size * 1.35)
    total_h = line_h * len(lines)
    y = int(h * (1 - bottom_ratio)) - total_h            # 底部安全區以上

    for line in lines:
        tw = d.textlength(line, font=font)
        x = (w - tw) / 2
        d.text((x, y), line, font=font, fill="white",
               stroke_width=max(2, font_size // 12), stroke_fill="black")
        y += line_h
    img.save(out)
    return out

def wrap(text, font, max_width, draw):
    lines, buf = [], ""
    for ch in text:
        if draw.textlength(buf + ch, font=font) > max_width and buf:
            lines.append(buf); buf = ""
        buf += ch
    if buf: lines.append(buf)
    return lines
```

中文逐字換行即可；若語言是英文，改成逐詞換行。

## 安全區

手機短影片平台（Reels、Shorts、TikTok）的底部約 15–20% 會被進度條與按鈕遮住，右側約 12% 有互動按鈕。所以：

- 直式：字幕底線在 82% 高度以上，左右各留 7%。
- 橫式：底線在 90% 高度以上。
- 標題：頂部 8% 以下，避開狀態列。

`bottom_ratio` 按比例給不同值，放在 `presets.ASPECTS` 一起管理。

## 標題圖層

`render_title(title, size, ...)`：字級為字幕的 1.6 倍、粗體、半透明圓角底框：

```python
d.rounded_rectangle([x - pad, y - pad, x + tw + pad, y + th + pad], radius=24, fill=(0, 0, 0, 140))
```

標題只在第一個場景出現 3 秒，`enable='between(t,0,3)'`。

## 疊到片段上

每個場景的 cue 各畫一張 PNG，ffmpeg 用 `overlay` 濾鏡串起來：

```python
def overlay_filter(cues: list[Cue], scene_start: float, n_inputs: int) -> str:
    chain, prev = [], "[0:v]"
    for i, c in enumerate(cues, 1):
        s, e = c.start - scene_start, c.end - scene_start
        chain.append(f"{prev}[{i}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[v{i}]")
        prev = f"[v{i}]"
    return ";".join(chain), prev
```

指令：`-i clip.mp4 -i cue_01.png -i cue_02.png ... -filter_complex "<chain>" -map "[vN]"`。

一個場景通常 2–4 句字幕，輸入數不會太多；若超過 20 張，改成先把字幕燒進一段透明影片再疊。

## 給 Antigravity 的提示詞
```
實作 services/overlay.py：find_font、wrap、render_subtitle（描邊、安全區）、render_title（圓角底框），
與 services/ffmpeg.py 的 overlay_filter。寫一個 scripts/preview_subtitle.py 對三種比例各輸出一張範例圖層並疊在 placeholder 圖上，
把三張結果圖給我看。
```

## 今日檢查清單
- [ ] 三種比例的字幕都落在安全區內、置中、有黑色描邊。
- [ ] 長句自動換行不超過兩行。
- [ ] 在沒有微軟正黑體的 Linux 上，放入 `resources/fonts/NotoSansCJK.ttc` 後可正常顯示。

## 明日預告
Day 17 把所有片段、語音、字幕、標題串起來，混入背景音樂，做淡入淡出與響度正規化，產出第一支完整影片。
