# Day 28｜劇情演繹模式：多角色台詞、多說話者 TTS 與說話者字幕

> 30 天打造 AI 短影片生成平台 — 第 28 天

## 今日目標
- 系列的第二種內容模式：角色各自說台詞，旁白補足敘述。
- 每句台詞用該角色的聲音合成，或用 Gemini TTS 的多說話者一次生成。
- 字幕逐句依語音時間顯示並標示說話者。

## 兩種模式的差別

| | 旁白解說（Day 27） | 劇情演繹（今天） |
|---|---|---|
| 場景內容 | 一段旁白 | 多行：`speaker` + `text` |
| 聲音 | 單一旁白聲 | 每個角色自己的聲音 + 旁白聲 |
| 字幕 | 按字數比例 | 每行一段語音，時間精確 |
| 適合 | 知識型、劇情摘要 | 對話密集的小說、廣播劇風格 |

## 場景結構擴充

```python
class Line(BaseModel):
    speaker: str | None = None      # None = 旁白
    text: str
    audio_path: str | None = None
    duration: float | None = None
    start: float | None = None      # 場景內偏移

class Scene(BaseModel):
    ...
    lines: list[Line] = []          # 劇情演繹模式使用；narration 由 lines 串接而成
```

`narration` 保留為所有 `text` 的串接，讓工作台與時間軸的既有邏輯不用改。

## 改編提示詞

```python
DRAMA_SYSTEM = """你是廣播劇編劇。把小說片段改編成約 {target_seconds} 秒的劇情演繹影片。
角色清單（speaker 必須完全等於其中的 name）：{character_names}
每個場景輸出 lines：角色台詞 speaker 填角色名，旁白 speaker 填 null。
台詞可以取自原文或合理改寫，保持角色語氣；旁白只補足動作與情緒，簡短。
每場 3–8 行，總長約 {target_seconds} 秒（中文每秒 4 字）。image_prompt 含出場角色時貼上其 appearance。"""
```

schema 的 `speaker` 用 `Literal[...]` 動態建構（`Literal[tuple(names)]`），模型就不會拼錯角色名。

## 語音：兩種做法

### 做法一：逐行合成（穩定、時間精確）

每行呼叫一次 TTS，用該角色的 `voice`，得到精確 `duration`；場景音訊由 ffmpeg 串接，行與行之間留 0.25 秒：

```python
async def synth_lines(self, project, scene, pdir):
    t = 0.0
    parts = []
    for i, line in enumerate(scene.lines):
        voice = self.voice_for(project, line.speaker)
        out = pdir / f"scene_{scene.index+1:02d}_line_{i+1:02d}.wav"
        r = await self.providers.tts.synthesize(line.text, voice=voice, language=..., out=out,
                                                style=self.style_for(project, line.speaker))
        line.audio_path, line.duration, line.start = rel(out), r["duration"], t
        parts.append(out); t += r["duration"] + 0.25
    await concat_audio(parts, gap=0.25, out=pdir / f"scene_{scene.index+1:02d}.wav")
    scene.audio_duration = t - 0.25
```

角色的語氣可以從 `Character.description` 派生，例如「以冷靜、略帶傲慢的語氣說」。

### 做法二：Gemini 多說話者一次生成（更自然的對話節奏）

Gemini TTS 支援在同一次請求裡指定最多兩位說話者：

```python
config=types.GenerateContentConfig(
    response_modalities=["AUDIO"],
    speech_config=types.SpeechConfig(
        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                types.SpeakerVoiceConfig(speaker="小明", voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck"))),
                types.SpeakerVoiceConfig(speaker="小美", voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"))),
            ])))
contents = "小明：你真的要走？\n小美：我沒有選擇。"
```

對話的停頓與接話會更像真人，但拿不到每句的時間，字幕又得回到比例估算。我們預設用做法一，兩位角色以內的場景可選做法二，字幕改用 Gemini 文字模型對音訊做逐句對齊（把 wav 與文字一起送，要求回每句的 start/end）。

## 說話者字幕

`Cue.speaker` 已在 Day 14 預留。字幕圖層在文字前加「小明：」並用不同顏色：

```python
SPEAKER_COLORS = ["#FFD166", "#06D6A0", "#EF476F", "#118AB2", "#F78C6B"]
color = SPEAKER_COLORS[hash(speaker) % len(SPEAKER_COLORS)] if speaker else "white"
d.text((x, y), f"{speaker}：", font=font, fill=color, stroke_width=..., stroke_fill="black")
d.text((x + name_w, y), text, font=font, fill="white", ...)
```

旁白行用斜體或較淡的顏色區分。時間碼直接來自 `line.start` 與 `line.duration`，不再估算。

## 工作台調整

劇情模式下場景卡片的旁白區變成「台詞列表」：每行一個說話者下拉選單 + 文字框，可新增／刪除／排序行；每行右側有播放鍵試聽該行。改任何一行都把 `audio_stale=True`，但只重合成改動的行（用文字 hash 判斷）。

## 給 Antigravity 的提示詞
```
擴充 Scene.lines 與 Line 模型、DRAMA_SYSTEM 與動態 Literal speaker schema、逐行 TTS 合成與 concat_audio、
多說話者 TTS 選項、Cue.speaker 的彩色說話者字幕、工作台的台詞列表編輯。
用 Day 27 的小說建立劇情模式系列，生成第 1 集，把 subtitles.srt 前 10 條與一張含說話者字幕的截圖給我。
```

## 今日檢查清單
- [ ] 每行台詞使用對應角色的聲音，旁白用系列聲音。
- [ ] 字幕出現時間與該句語音開始時間誤差 < 0.1 秒。
- [ ] 只改一行台詞，其他行的 wav 不會重新合成。

## 第四週回顧
前端工作台、即時進度、下載、小說分集、劇情演繹全部完成。平台功能已經完整，最後兩天處理成本、穩定性與部署。

## 明日預告
Day 29 成本、配額與穩定性：重試與退避、快取、安全設定、費用估算與每日預算。
