# Day 17｜串接場景、混入 BGM：淡入淡出、音量正規化與 loudnorm

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 17 天

## 今日目標
- `compose_scene()`：片段 + mp3 + 字幕 + 標題 → `final_XX.mp4`。
- `concat()` 串接；`mix_bgm()` 循環、淡入淡出、ducking、loudnorm。
- 第一支完整 `output.mp4`。

## 兩層合成

第一層每場一支完成品，第二層串接加 BGM。改一場只重做一場。

## compose_scene

```python
async def compose_scene(self, project, scene, timing, pdir):
    out = pdir / f"final_{scene.index+1:02d}.mp4"
    inputs = ["-i", abs(scene.clip_path), "-i", abs(scene.audio_path)]
    overlays = []
    if project.options.subtitle:
        for i, cue in enumerate(scene.cues, 1):
            png = render_subtitle(cue.text, size, ..., out=pdir / f"cue_{scene.index+1:02d}_{i:02d}.png")
            overlays.append((png, cue.start - timing.start, cue.end - timing.start))
    if project.options.show_title and scene.index == 0:
        overlays.append((render_title(project.title, size, ..., out=pdir / "title.png"), 0.0, 3.0))
    for png, _, _ in overlays: inputs += ["-i", str(png)]

    chain, last = overlay_chain([Cue(text="", start=s, end=e) for _, s, e in overlays], 0.0, first_input=2)
    delay = int(timing.lead_in * 1000)
    fc = ";".join(p for p in [chain, f"[1:a]adelay={delay}|{delay},apad[a]"] if p)
    await run_ffmpeg(*inputs, "-filter_complex", fc, "-map", last, "-map", "[a]", "-t", f"{scene.duration:.3f}",
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", str(cfg.render.crf),
                     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-pix_fmt", "yuv420p", str(out))
    return out
```

Edge-TTS 的 mp3 是 24 kHz，這裡統一重採樣到 48 kHz，避免串接時取樣率不一致。

## concat

```python
async def concat(finals, out):
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in finals), encoding="utf-8")
    await run_ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out))
```

## BGM

```python
async def mix_bgm(video, bgm, out, total, *, volume, fade=2.0):
    fc = (f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{total:.3f},volume={volume},"
          f"afade=t=in:st=0:d={fade},afade=t=out:st={total-fade:.3f}:d={fade}[bgm];"
          f"[0:a][bgm]sidechaincompress=threshold=0.05:ratio=4:attack=50:release=400[mix];"
          f"[mix]loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    await run_ffmpeg("-i", str(video), "-i", str(bgm), "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                     "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out))
```

- `aloop` + `atrim`：BGM 長短都對齊影片。
- `sidechaincompress`：旁白時自動壓低 BGM。
- `loudnorm`：-16 LUFS，各平台不會忽大忽小。
- `volume` 來自 `project.options.bgm_volume`，預設 0.2。

`data/bgm/` 放 mp3/wav 即出現在 `GET /api/bgm`。

## render

```python
async def render(self, project, progress=None):
    timings = build_timeline(project)
    finals = [await self.compose_scene(project, s, t, pdir) for s, t in zip(project.scenes, timings)]
    merged = pdir / "merged.mp4"; await concat(finals, merged)
    out = pdir / "output.mp4"
    if project.options.bgm:
        await mix_bgm(merged, bgm_dir / project.options.bgm, out, sum(t.duration for t in timings), volume=project.options.bgm_volume)
    else:
        merged.replace(out)
    project.output_path, project.status = rel(out), "rendered"
    await self.db.save_project(project)
```

`final_XX.mp4` 快取判斷：若片段、語音、字幕圖層都沒變（比對 mtime 或 hash），跳過重做。

## 給 Claude Code 的提示詞
```
實作 compose_scene（overlay、adelay+apad、48k 重採樣）、concat、mix_bgm（aloop/afade/sidechaincompress/loudnorm）、render、
GET /api/bgm、POST /api/projects/{id}/render，以及 final_XX.mp4 的快取判斷。
在 8001 用 mock+placeholder+edge 從建立到 render 跑完整流程，把 output.mp4 的 ffprobe 資訊貼給我。
```

## 今日檢查清單
- [ ] `output.mp4` 手機可播、音畫同步。
- [ ] BGM 結尾淡出、旁白清楚。
- [ ] 只改第 3 場再 render，第 1、2 場沒重做。

## 明日預告
Day 18 一份腳本三種比例，以及 xfade 轉場。
