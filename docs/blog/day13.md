# Day 13｜Gemini TTS 配音：預建聲音、風格指令與多語言

> 30 天打造 AI 短影片生成平台 — 第 13 天

## 今日目標
- 實作 `GeminiTTS`：把旁白變成 wav，回傳精確長度。
- 用自然語言控制語氣（興奮、沉穩、耳語）。
- 處理 PCM 轉 wav、長文本切段與速度控制。

## Gemini TTS 的特點

- 模型：`gemini-2.5-flash-preview-tts`（快、便宜）、`gemini-2.5-pro-preview-tts`（更自然）。
- 30 種預建聲音（Kore、Puck、Charon、Aoede、Leda、Fenrir…），每種都支援多語言，中文旁白直接用即可。
- **語氣用文字控制**：在文本前加「用興奮的語氣說：」之類的指示，模型會照做。這比 SSML 直覺得多。
- 回傳的是 **24kHz、16-bit、單聲道 PCM**，沒有檔頭，要自己包成 wav。
- 單次輸入上限約 32k token，一個場景的旁白遠低於此。

## GeminiTTS

```python
import wave
from pathlib import Path
from google import genai
from google.genai import types

class GeminiTTS:
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def synthesize(self, text: str, *, voice: str, language: str, out: Path,
                         style: str | None = None) -> dict:
        prompt = f"{style}：{text}" if style else text     # 例如「以溫暖沉穩、略帶好奇的語氣朗讀」
        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
            ),
        )
        pcm = resp.candidates[0].content.parts[0].inline_data.data
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(pcm)
        duration = len(pcm) / (24000 * 2)
        return {"path": out, "duration": duration}
```

`duration` 直接從位元組數算，不需要 ffprobe，而且是精確值，Day 14 的時間軸全靠它。

## 語氣由風格預設帶入

在 `presets.STYLES` 每種風格加 `voice_style`：

```python
"cinematic": {..., "voice_style": "以電影預告片般沉穩、有張力的語氣朗讀"},
"flat":      {..., "voice_style": "以輕鬆、親切、像朋友聊天的語氣朗讀"},
```

使用者也可以在專案選項覆寫 `voice_style`。

## 語速

Gemini TTS 沒有直接的語速參數，兩種做法：

1. 提示詞：「語速稍快」「慢慢地說」，效果自然但不精確。
2. 後製：ffmpeg `atempo=1.1`，精確但略有機械感。

我們提供 `options.speech_rate`（0.8–1.3），用 ffmpeg 後製，因為時間軸需要可預測的長度。

## 管線：generate_audio

```python
async def generate_audio(self, project, *, only=None, progress=None):
    pdir = self.projects.project_dir(project.id)
    targets = [s for s in project.scenes if (only is None or s.id in only) and (s.audio_stale or not s.audio_path)]
    style = project.options.voice_style or STYLES[project.options.style]["voice_style"]
    for n, scene in enumerate(targets, 1):
        out = pdir / f"scene_{scene.index + 1:02d}.wav"
        r = await self.providers.tts.synthesize(
            clean_for_tts(scene.narration), voice=project.options.voice,
            language=project.options.language, out=out, style=style)
        if project.options.speech_rate != 1.0:
            r = await apply_tempo(out, project.options.speech_rate)
        scene.audio_path, scene.audio_duration, scene.audio_stale = rel(out), r["duration"], False
        await self.db.save_project(project)
        if progress: await progress(n / len(targets), f"配音 {n}/{len(targets)}")
```

`clean_for_tts` 移除 emoji、全形括號內容、markdown 符號，並把「AI」這種縮寫視情況替換成「A I」，避免唸成怪音。

## 試聽

設定頁與新增專案表單都需要「試聽聲音」：`POST /api/tts/preview` 帶 `voice`、`text`，回傳短 wav。把結果快取在 `data/cache/tts/<voice>_<hash>.wav`，同一句不重複扣費。

## 給 Antigravity 的提示詞
```
實作 providers/tts/gemini.py（PCM 轉 wav、精確 duration、style 前綴）、clean_for_tts、apply_tempo（ffmpeg atempo）、
pipeline.generate_audio、POST /api/tts/preview（含快取）。用 Kore 與 Puck 各合成一句繁中旁白，回報長度與檔案路徑。
```

## 今日檢查清單
- [ ] 每個場景都有 `scene_XX.wav`，`audio_duration` 與實際播放長度一致。
- [ ] 改 `voice_style` 後語氣有明顯差異。
- [ ] 試聽同一句兩次，第二次不會呼叫 API。

## 明日預告
Day 14 時間軸與字幕：由音訊長度決定場景時長，把旁白切成逐句字幕並產生 SRT。
