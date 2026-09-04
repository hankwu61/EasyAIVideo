# Day 14｜逐字時間戳：Edge-TTS WordBoundary 做出精準字幕與 SRT

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 14 天

## 今日目標
- `services/timeline.py`：場景時長、轉場間隔、總長度。
- 用 `words.json` 把旁白切成字幕句，時間碼精確到字。
- 沒有時間戳（silent 或上傳的語音）時退回按字數比例估算。

## 場景時長

```python
def build_timeline(project, *, lead_in=0.2, tail=0.4):
    t = 0.0; out = []
    for s in project.scenes:
        speech = s.audio_duration or max(2.0, len(s.narration) / 4)
        s.duration = round(speech + lead_in + tail, 3)
        out.append(SceneTiming(scene_id=s.id, start=t, lead_in=lead_in, speech=speech, duration=s.duration))
        t += s.duration
    return out
```

## 切句

一行字幕上限：直式 18 字、橫式 28 字、方形 20 字。優先在句號／問號／驚嘆號切，其次逗號／頓號，最後硬切。

```python
def split_cues(text: str, max_chars: int) -> list[str]: ...   # 同前一系列 Day 14
```

## 用時間戳對齊

Edge-TTS 的 `WordBoundary` 對中文通常是逐字或逐詞。演算法：把字幕句的字依序對應到 `words` 序列，該句的 `start` 是第一個字的 start，`end` 是最後一個字的 end。

```python
def align_cues(cues: list[str], words: list[dict], speech_offset: float) -> list[Cue]:
    """words: [{text, start, end}]，時間相對於音訊開頭；speech_offset 是場景內語音開始的偏移。"""
    out, wi = [], 0
    flat = [(ch, w) for w in words for ch in w["text"] if not ch.isspace()]
    for cue in cues:
        chars = [c for c in cue if not c.isspace() and c not in "，。！？、；：,.!?;:"]
        if not chars or wi >= len(flat):
            out.append(Cue(text=cue, start=None, end=None)); continue
        start = flat[wi][1]["start"]
        wi = min(wi + len(chars), len(flat))
        end = flat[wi - 1][1]["end"]
        out.append(Cue(text=cue, start=speech_offset + start, end=speech_offset + end))
    # 補洞：沒對到的句子用相鄰句平均
    fill_gaps(out)
    # 相鄰句之間留 0.05 秒，避免閃爍
    for a, b in zip(out, out[1:]):
        a.end = min(a.end, b.start - 0.05)
    return out
```

字數對應會因為標點、英文單字、數字（「2024」一個 word 四個字）產生偏移，`fill_gaps` 與最後的裁切讓結果穩定。實測誤差在 ±0.1 秒。

## 退回策略

```python
def timed_cues(scene, timing, aspect):
    cues = split_cues(scene.narration, SUB_CHARS[aspect])
    words = load_words(scene.words_path)
    if words:
        return align_cues(cues, words, timing.lead_in + timing.start)
    return proportional(cues, timing.start + timing.lead_in, timing.start + timing.lead_in + timing.speech)
```

`proportional` 按字數比例分配，誤差 ±0.3 秒，給 silent 模式與使用者上傳的語音用。

## SRT

`to_srt(all_cues)` 寫到 `subtitles.srt`，`GET /api/projects/{id}/subtitles.srt` 下載。也順便輸出 `subtitles.vtt`，網頁 `<track>` 可以直接用來預覽字幕。

## 卡拉 OK 式字幕（加分）

既然有逐字時間，可以做「正在唸的字變色」：字幕圖層每個字一張 PNG 太多，改用兩層：底層白字整句、上層黃字整句 + `crop` 濾鏡隨時間展開寬度。Day 16 會提供選項 `subtitle_style: plain | karaoke`。

## 給 Claude Code 的提示詞
```
實作 services/timeline.py：build_timeline、split_cues、align_cues（含 fill_gaps 與相鄰裁切）、proportional 退回、to_srt/to_vtt；
models 加 Cue 與 scene.cues；素材完成後 rebuild_timeline 並輸出 srt/vtt；GET subtitles.srt / .vtt。
寫單元測試：純中文、含英文與數字、含標點三種 words 情境。
```

## 今日檢查清單
- [ ] 字幕開始時間與該句語音誤差 < 0.1 秒（用 VLC 對）。
- [ ] 沒有 words.json 的場景也能產生字幕。
- [ ] 沒有任何字幕重疊。

## 第二週回顧
腳本、文稿、抽象層、Agnes 圖片、Edge-TTS、逐字字幕。素材齊了，下週合成。

## 明日預告
Day 15 ffmpeg 入門：zoompan 做 Ken Burns。
