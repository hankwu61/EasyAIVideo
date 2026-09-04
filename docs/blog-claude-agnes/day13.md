# Day 13｜Edge-TTS 配音：免費的微軟神經語音、聲音清單、語速與重試

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 13 天

## 今日目標
- 實作 `EdgeTTS`：旁白 → mp3，取得精確長度。
- 整理繁中／簡中／粵語／英文常用聲音清單，支援語速。
- 重試與逾時；試聽 API 與快取。

## Edge-TTS 是什麼

`edge-tts` 套件透過 Edge 瀏覽器的「大聲朗讀」服務取得微軟神經語音。免費、不需金鑰、品質接近 Azure TTS，繁中有曉臻、曉雨、雲哲三個聲音。限制：需要網路；官方沒有承諾的 SLA，偶爾會失敗，所以一定要重試。

```bash
uv add edge-tts
uv run edge-tts --list-voices | grep zh-
```

## EdgeTTS 供應商

```python
import asyncio, json
from pathlib import Path
import edge_tts

def speed_to_rate(speed: float) -> str:      # 1.1 → "+10%"
    return f"{int(round((speed - 1.0) * 100)):+d}%"

class EdgeTTS:
    name = "edge"

    async def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TTSResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        last = None
        for attempt in range(3):
            try:
                com = edge_tts.Communicate(text, voice or "zh-TW-HsiaoChenNeural", rate=speed_to_rate(speed))
                words = []
                with output_path.open("wb") as fh:
                    async for chunk in asyncio.wait_for(_iter(com.stream()), timeout=90):
                        if chunk["type"] == "audio":
                            fh.write(chunk["data"])
                        elif chunk["type"] == "WordBoundary":
                            words.append({"text": chunk["text"], "start": chunk["offset"] / 1e7,
                                          "end": (chunk["offset"] + chunk["duration"]) / 1e7})
                if output_path.stat().st_size == 0:
                    raise ProviderError("Edge TTS 輸出空檔")
                words_path = output_path.with_suffix(".words.json")
                words_path.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
                duration = await probe_duration(output_path)
                return TTSResult(path=output_path, duration=duration, words=words, words_path=words_path)
            except Exception as e:           # 網路抖動、服務端 403/超時都重試
                last = e
                await asyncio.sleep(1.5 * (attempt + 1))
        raise ProviderError(f"Edge TTS 失敗：{last}")
```

用 `stream()` 而不是 `save()`，因為 `WordBoundary` 事件只在串流時提供。`offset`、`duration` 單位是 100 奈秒，除以 1e7 變秒。明天的字幕全靠 `words`。

`asyncio.wait_for` 包住 async generator 需要一個小工具 `_iter`，或改用 `asyncio.timeout()` 上下文。

## 聲音清單

```python
EDGE_VOICES = [
    ("zh-TW-HsiaoChenNeural", "曉臻（女）", "zh-TW", "Female"),
    ("zh-TW-HsiaoYuNeural", "曉雨（女）", "zh-TW", "Female"),
    ("zh-TW-YunJheNeural", "雲哲（男）", "zh-TW", "Male"),
    ("zh-CN-XiaoxiaoNeural", "晓晓（女）", "zh-CN", "Female"),
    ("zh-CN-YunxiNeural", "云希（男）", "zh-CN", "Male"),
    ("zh-CN-YunyangNeural", "云扬（男，新聞）", "zh-CN", "Male"),
    ("zh-HK-HiuGaaiNeural", "曉佳（女，粵語）", "zh-HK", "Female"),
    ("zh-HK-WanLungNeural", "雲龍（男，粵語）", "zh-HK", "Male"),
    ("en-US-AriaNeural", "Aria (F)", "en-US", "Female"),
    ("en-US-GuyNeural", "Guy (M)", "en-US", "Male"),
    ("ja-JP-NanamiNeural", "Nanami (F)", "ja-JP", "Female"),
]
```

`list_voices()` 回這張表；設定頁另有「載入全部聲音」按鈕呼叫 `edge_tts.list_voices()` 取得完整清單（三百多個）。

## 語速

Edge-TTS 原生支援 `rate`，不用 ffmpeg 後製，時間戳也會跟著正確。`ProjectOptions.speed` 0.7–1.5。也有 `pitch="+0Hz"`、`volume="+0%"` 可玩。

## 文字清理

```python
def clean_for_tts(s: str) -> str:
    s = re.sub(r"[\U0001F300-\U0001FAFF]", "", s)        # emoji
    s = re.sub(r"[（(【\[].*?[)）】\]]", "", s)
    s = s.replace("AI", "A I").replace("&", "和")
    return s.strip()
```

## 管線與試聽

`generate_audio` 與圖片對稱：只做 `audio_stale` 或缺少的場景，存 `audio_path`、`words_path`、`audio_duration`。

`POST /api/tts/preview`：`{voice, text?, speed?}` 回 mp3，快取在 `data/cache/tts/<voice>_<hash>.mp3`。Edge-TTS 雖然免費，但重複呼叫會拖慢並增加失敗機會。

## 給 Claude Code 的提示詞
```
實作 providers/tts/edge.py（stream 取 WordBoundary、words.json、probe_duration、3 次重試、90 秒逾時）、EDGE_VOICES 與 list_voices、
clean_for_tts、pipeline.generate_audio、POST /api/tts/preview（快取）、設定頁載入全部聲音。
用曉臻與雲哲各合成一句繁中旁白，回報長度與 words.json 前 5 筆。
```

## 今日檢查清單
- [ ] 每場都有 mp3 與 words.json。
- [ ] `speed=1.2` 時長度縮短且 words 的時間跟著變。
- [ ] 斷網時任務失敗訊息清楚，恢復後重跑成功。

## 明日預告
Day 14 用逐字時間戳做精準字幕：切句、對齊、SRT，以及沒有時間戳時的退回策略。
