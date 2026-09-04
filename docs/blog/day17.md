# Day 17｜串接場景、混入 BGM：淡入淡出、音量正規化與 loudnorm

> 30 天打造 AI 短影片生成平台 — 第 17 天

## 今日目標
- 完成 `compose()`：把每個場景的片段 + 語音 + 字幕合成為場景 mp4，再串接成完整影片。
- 加入背景音樂：循環、淡入淡出、自動降低音量（ducking）。
- 產出第一支可以直接上傳的 `output.mp4`。

## 合成分兩層

**第一層：每個場景一支「完成的場景影片」**
輸入：`clip_XX.mp4`（無聲動態）、`scene_XX.wav`、字幕 PNG、標題 PNG（僅第一場）。
輸出：`final_XX.mp4`（有畫面、字幕、旁白）。

**第二層：串接 + BGM**
輸入：所有 `final_XX.mp4`、`bgm.mp3`。
輸出：`output.mp4`。

分兩層的好處：改一個場景只重做那一場，串接很快。

## 第一層：場景合成

```python
async def compose_scene(self, project, scene, timing, pdir) -> Path:
    out = pdir / f"final_{scene.index + 1:02d}.mp4"
    inputs = ["-i", abs(scene.clip_path), "-i", abs(scene.audio_path)]
    overlays = []
    if project.options.subtitle:
        for i, cue in enumerate(scene.cues, 1):
            png = render_subtitle(cue.text, size, font_path=font, out=pdir / f"cue_{scene.index+1:02d}_{i:02d}.png")
            overlays.append((png, cue.start - timing.start, cue.end - timing.start))
    if project.options.show_title and scene.index == 0:
        png = render_title(project.title, size, font_path=font, out=pdir / "title.png")
        overlays.append((png, 0.0, 3.0))

    for png, _, _ in overlays:
        inputs += ["-i", str(png)]

    chain, last = "[0:v]", "[0:v]"
    parts = []
    for i, (_, s, e) in enumerate(overlays, 2):       # 0 是影片、1 是音訊
        parts.append(f"{last}[{i}:v]overlay=0:0:enable='between(t,{s:.3f},{e:.3f})'[v{i}]")
        last = f"[v{i}]"
    # 語音延遲 lead_in，並補到場景長度
    parts.append(f"[1:a]adelay={int(timing.lead_in*1000)}|{int(timing.lead_in*1000)},apad[a]")
    fc = ";".join(parts)

    await run_ffmpeg(*inputs, "-filter_complex", fc, "-map", last, "-map", "[a]",
                     "-t", f"{scene.duration:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-pix_fmt", "yuv420p", str(out))
    return out
```

`apad` 把語音補到與畫面等長，`-t` 再裁齊，避免串接時音畫長度不一致造成漂移。

## 第二層：串接

用 concat demuxer（所有場景編碼參數一致，可以不重編碼）：

```python
async def concat(self, finals: list[Path], out: Path):
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in finals), encoding="utf-8")
    await run_ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out))
```

若想在場景之間加交叉淡入淡出，要改用 `xfade` 濾鏡並重編碼，Day 18 會提到。

## 混入 BGM

```python
async def mix_bgm(self, video: Path, bgm: Path, out: Path, total: float, *, volume=0.18, fade=2.0):
    fc = (
        f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{total:.3f},"
        f"volume={volume},afade=t=in:st=0:d={fade},afade=t=out:st={total - fade:.3f}:d={fade}[bgm];"
        f"[0:a][bgm]sidechaincompress=threshold=0.05:ratio=4:attack=50:release=400[mix];"
        f"[mix]loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    )
    await run_ffmpeg("-i", str(video), "-i", str(bgm), "-filter_complex", fc,
                     "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out))
```

三個關鍵：
- `aloop` + `atrim`：BGM 比影片短時循環，比影片長時截斷。
- `sidechaincompress`：旁白出現時自動壓低 BGM（ducking）。若嫌複雜，先用固定 `volume=0.18` 也可以。
- `loudnorm`：輸出響度統一在 -16 LUFS，符合各平台建議，避免有的影片特別小聲。

BGM 來源：`data/bgm/` 放入 mp3/wav 即會出現在清單，`GET /api/bgm` 列出檔名與長度。

## 管線：render

```python
async def render(self, project, progress=None):
    timings = build_timeline(project)
    finals = []
    for n, (s, t) in enumerate(zip(project.scenes, timings), 1):
        finals.append(await self.compose_scene(project, s, t, pdir))
        if progress: await progress(0.8 * n / len(project.scenes), f"合成場景 {n}")
    merged = pdir / "merged.mp4"
    await self.concat(finals, merged)
    out = pdir / "output.mp4"
    if project.options.bgm:
        await self.mix_bgm(merged, self.bgm_dir / project.options.bgm, out, sum(t.duration for t in timings))
    else:
        merged.replace(out)
    project.output_path, project.status = rel(out), ProjectStatus.rendered
    await self.db.save_project(project)
```

路由：`POST /api/projects/{id}/render`。

## 給 Antigravity 的提示詞
```
實作 pipeline.compose_scene（字幕/標題 overlay、adelay+apad）、concat（demuxer, -c copy）、mix_bgm（aloop、afade、sidechaincompress、loudnorm）、
render 與 POST /api/projects/{id}/render、GET /api/bgm。用 8001 埠的 placeholder+silent 設定從建立專案到 render 跑完整流程，
把 output.mp4 的 ffprobe 資訊給我。
```

## 今日檢查清單
- [ ] `output.mp4` 可以在手機播放，音畫同步。
- [ ] 有 BGM 時旁白清楚、BGM 在結尾淡出。
- [ ] 只改第 3 場的旁白再 render，第 1、2 場的 `final_XX.mp4` 沒有被重做。

## 明日預告
Day 18 一份腳本三種比例：直式、橫式、方形的輸出策略，以及場景之間的轉場。
