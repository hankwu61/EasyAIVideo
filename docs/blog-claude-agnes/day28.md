# Day 28｜劇情演繹模式：多角色台詞、Edge-TTS 多聲音與說話者字幕

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 28 天

## 今日目標
- 系列第二種模式：角色各說台詞，旁白補敘述。
- 每行台詞用該角色的 Edge-TTS 聲音逐行合成，串接成場景音訊。
- 字幕逐句依語音時間顯示並以顏色標示說話者。

## 與旁白解說的差別

| | 旁白解說 | 劇情演繹 |
|---|---|---|
| 場景內容 | 一段旁白 | 多行 `speaker` + `text` |
| 聲音 | 單一旁白聲 | 每角色一個 Edge-TTS 聲音 + 旁白聲 |
| 字幕 | 逐字時間戳對齊 | 每行一段語音，時間天生精確 |

Edge-TTS 在這裡特別合適：免費，所以逐行合成幾十次也不心疼；每行都有 WordBoundary，字幕仍能逐字精準。

## 模型

```python
class Line(BaseModel):
    speaker: str | None = None; text: str
    audio_path: str | None = None; words_path: str | None = None
    duration: float | None = None; start: float | None = None

class Scene(BaseModel): ...; lines: list[Line] = []
```

`narration` 保留為所有 `text` 串接。

## 改編提示詞

```python
DRAMA_SYSTEM = """你是廣播劇編劇。把小說片段改編成約 {target_seconds} 秒的劇情演繹影片。
角色清單（speaker 必須完全等於其中一個 name）：{character_names}
每場輸出 lines：角色台詞 speaker 填角色名，旁白填 null。台詞可取自原文或合理改寫；旁白只補動作與情緒，簡短。
每場 3–8 行，總長約 {target_seconds} 秒（每秒 4 字）。image_prompt 含出場角色時貼上其 appearance。只輸出 JSON。"""
```

程式端驗證 `speaker` 在角色清單內，不在就用最相近的名字修正（`difflib.get_close_matches`），仍找不到就當旁白。

## 逐行合成

```python
async def synth_lines(self, project, scene, pdir):
    t, parts = 0.0, []
    for i, line in enumerate(scene.lines):
        voice = self.voice_for(project, line.speaker)          # 角色聲音或旁白聲音
        out = pdir / f"scene_{scene.index+1:02d}_line_{i+1:02d}.mp3"
        h = hashlib.md5(f"{voice}|{project.options.speed}|{line.text}".encode()).hexdigest()
        if line.audio_path and line.hash == h:                  # 沒改的行不重合成
            r = cached(line)
        else:
            r = await self.providers.tts.synthesize(clean_for_tts(line.text), voice, project.options.speed, out)
            line.audio_path, line.words_path, line.hash = rel(out), rel(r.words_path), h
        line.duration, line.start = r.duration, t
        parts.append(out); t += r.duration + 0.25
    await concat_audio(parts, gap=0.25, out=pdir / f"scene_{scene.index+1:02d}.mp3")
    scene.audio_duration = t - 0.25
```

`concat_audio` 用 ffmpeg `concat` 加 `anullsrc` 間隔。每行的 words.json 時間加上 `line.start` 就是場景內的絕對時間，Day 14 的 `align_cues` 直接可用。

## 說話者字幕

`Cue.speaker` 在字幕前加「小明：」並上色：

```python
SPEAKER_COLORS = ["#FFD166", "#06D6A0", "#EF476F", "#118AB2", "#F78C6B"]
```

旁白行用較淡的白色。每行一個 cue（過長再按 Day 14 規則切）。

## 工作台

劇情模式下卡片的旁白區變成台詞列表：說話者下拉 + 文字框，可新增／刪除／排序，每行播放鍵。改任一行只重合成該行（hash 判斷）。

## 給 Claude Code 的提示詞
```
擴充 Line 與 scene.lines、DRAMA_SYSTEM 與 speaker 驗證修正、synth_lines（hash 快取）與 concat_audio、words 時間加 line.start 後對齊、
彩色說話者字幕、工作台台詞列表。用 Day 27 的小說建立劇情模式系列生成第 1 集，貼 subtitles.srt 前 10 條與一張說話者字幕截圖。
```

## 今日檢查清單
- [ ] 每行台詞用對應角色聲音。
- [ ] 字幕與語音誤差 < 0.1 秒。
- [ ] 只改一行，其他行 mp3 沒重做。

## 第四週回顧
工作台、進度、下載、小說分集、劇情演繹。功能完整，最後兩天處理穩定性與部署。

## 明日預告
Day 29 成本與穩定性：Agnes 併發與限流、Edge-TTS 失敗處理、快取、重試、用量記錄。
