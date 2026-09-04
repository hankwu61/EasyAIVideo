# Day 14｜時間軸與字幕：從音訊長度推算場景時長與逐句字幕

> 30 天打造 AI 短影片生成平台 — 第 14 天

## 今日目標
- 實作 `services/timeline.py`：場景時長、轉場間隔、總長度。
- 把旁白切成適合閱讀的字幕句，按字數比例分配時間碼。
- 輸出 SRT 與內部 cue 結構，給 Day 16 的字幕圖層使用。

## 場景時長怎麼定

```
scene.duration = audio_duration + lead_in + tail
```

- `lead_in`（0.2 秒）：畫面先出現一下再開口，比較自然。
- `tail`（0.4 秒）：唸完留白，避免下一場搶拍。
- 若場景沒有語音（無聲模式），用字數估算：中文每秒 4 字，最少 2 秒。

```python
def build_timeline(project: Project, *, lead_in=0.2, tail=0.4) -> list[SceneTiming]:
    t = 0.0
    out = []
    for s in project.scenes:
        speech = s.audio_duration or max(2.0, len(s.narration) / 4)
        dur = round(speech + lead_in + tail, 3)
        out.append(SceneTiming(scene_id=s.id, start=t, duration=dur, speech_start=t + lead_in, speech_end=t + lead_in + speech))
        s.duration = dur
        t += dur
    return out
```

## 字幕切句

一行字幕不宜超過 18 個中文字（直式）或 28 字（橫式）。切句規則按優先順序：

1. 先按句號、問號、驚嘆號切。
2. 太長再按逗號、頓號、分號切。
3. 還太長就按字數硬切，盡量在詞邊界。

```python
import re

def split_cues(text: str, max_chars: int) -> list[str]:
    sentences = [s for s in re.split(r"(?<=[。！？!?])", text) if s.strip()]
    cues = []
    for sent in sentences:
        if len(sent) <= max_chars:
            cues.append(sent.strip()); continue
        parts = [p for p in re.split(r"(?<=[，、；,;])", sent) if p.strip()]
        buf = ""
        for p in parts:
            if len(buf) + len(p) > max_chars and buf:
                cues.append(buf.strip()); buf = ""
            buf += p
        if buf: cues.append(buf.strip())
    # 硬切保險
    final = []
    for c in cues:
        while len(c) > max_chars:
            final.append(c[:max_chars]); c = c[max_chars:]
        final.append(c)
    return [c.rstrip("，、；,;") for c in final if c]
```

## 時間碼分配

沒有逐字時間戳的情況下，最實用的方法是**按字數比例**分配語音區間：

```python
def assign_times(cues: list[str], speech_start: float, speech_end: float) -> list[Cue]:
    total = sum(len(c) for c in cues) or 1
    t, out = speech_start, []
    for c in cues:
        d = (speech_end - speech_start) * len(c) / total
        out.append(Cue(text=c, start=t, end=t + d))
        t += d
    return out
```

實測誤差在 ±0.3 秒內，觀眾幾乎察覺不到。若之後需要更精準，可以把 wav 送給 Gemini 文字模型做逐句對齊（多模態輸入音訊），或改用每句分別合成語音再串接——Day 28 劇情演繹模式會採用後者。

## SRT 輸出

```python
def to_srt(cues: list[Cue]) -> str:
    def ts(t): 
        h, r = divmod(t, 3600); m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"
    return "\n".join(f"{i}\n{ts(c.start)} --> {ts(c.end)}\n{c.text}\n" for i, c in enumerate(cues, 1))
```

寫到 `data/projects/<id>/subtitles.srt`，前端提供下載，讓使用者可以拿去 YouTube 上傳字幕。

## 資料模型補充

```python
class Cue(BaseModel):
    text: str; start: float; end: float; speaker: str | None = None

class Scene(BaseModel):
    ...
    cues: list[Cue] = []
```

時間軸在每次「產生素材」完成後重算一次，並存進 project。

## 給 Antigravity 的提示詞
```
實作 services/timeline.py：build_timeline、split_cues（直式 18 字、橫式 28 字）、assign_times、to_srt；
在 models 加入 Cue 與 scene.cues；pipeline 在素材生成後呼叫 rebuild_timeline 並輸出 subtitles.srt；
新增 GET /api/projects/{id}/subtitles.srt。寫單元測試覆蓋切句的三種情況。
```

## 今日檢查清單
- [ ] 每個場景的 `duration` = 語音長度 + 0.6 秒。
- [ ] 沒有任何字幕超過字數上限，也沒有以逗號結尾的字幕。
- [ ] SRT 能被 VLC 正確載入。

## 第二週回顧
腳本、文稿分段、供應商抽象、圖片、語音、時間軸全部就位。專案資料夾裡已經有一整套素材，下週把它們變成影片。

## 明日預告
Day 15 ffmpeg 入門：用 zoompan 濾鏡做 Ken Burns 動態鏡頭，把每張靜態圖變成有推拉平移的片段。
