# Day 26｜影片預覽、下載與素材打包 zip

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 26 天

## 今日目標
- 工作台右半：播放器（含 VTT 字幕軌）、下載影片、SRT、zip。
- 輸出版本紀錄，最多保留 5 版。
- 匯出品質選單與區網分享頁。

## 預覽

```tsx
function Preview({ project }) {
  if (!project.output_path) return <EmptyState text="尚未合成影片" />;
  const src = `/data/${project.output_path}?v=${project.updated_at}`;
  return (
    <div className="sticky top-4 space-y-3">
      <video key={src} src={src} controls playsInline crossOrigin="anonymous" className={aspectClass(project.options.aspect)}>
        <track kind="subtitles" srcLang="zh" src={`/api/projects/${project.id}/subtitles.vtt`} default />
      </video>
      <div className="flex gap-2">
        <a href={src} download={`${project.title}.mp4`} className="btn">下載影片</a>
        <a href={`/api/projects/${project.id}/subtitles.srt`} download className="btn-secondary">字幕 SRT</a>
        <a href={`/api/projects/${project.id}/export.zip`} className="btn-secondary">打包素材</a>
      </div>
      <Versions project={project} />
    </div>
  );
}
```

`key={src}` 讓影片更新時重建播放器。VTT 字幕軌是 Day 14 的副產品，即使影片沒燒字幕也能預覽。

## zip

```python
@router.get("/api/projects/{pid}/export.zip")
async def export_zip(pid, svc=Depends(get_project_service)):
    p = await svc.get(pid); pdir = svc.project_dir(pid); buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", p.model_dump_json(indent=2))
        z.writestr("script.md", render_script_md(p))
        for s in p.scenes:
            for attr in ("image_path", "audio_path", "words_path", "clip_path"):
                if (path := getattr(s, attr)): z.write(svc.abs(path), Path(path).name)
        for name in ("output.mp4", "subtitles.srt", "subtitles.vtt"):
            if (pdir / name).exists(): z.write(pdir / name, name)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{pid}.zip"'})
```

`script.md` 是給剪輯軟體用的人類可讀腳本。

## 版本紀錄

```python
class OutputVersion(BaseModel): path: str; created_at: datetime; duration: float; size: int; quality: str
class Project(BaseModel): ...; outputs: list[OutputVersion] = []
```

每次 render 複製 `output_<ts>.mp4`，超過 5 版刪最舊。前端列表切換播放、設為目前、刪除。

## 匯出品質與分享

下載旁選單「快速／一般／高品質」，高品質只重做第二層串接與編碼。`GET /share/{pid}` 極簡播放頁，設定頁顯示區網 IP 與 QR code。

## 給 Claude Code 的提示詞
```
實作 Preview（含 VTT 字幕軌、版本列表）、export.zip（含 script.md 與 words.json）、OutputVersion 保留 5 版、匯出品質、/share/{pid}、設定頁區網 IP 與 QR。
用預覽合成一次、下載 zip 並列出內容。
```

## 今日檢查清單
- [ ] 合成後播放器自動換新影片，字幕軌可開關。
- [ ] zip 含 project.json、script.md、素材、output.mp4。
- [ ] 合成 6 次只留 5 版。

## 明日預告
Day 27 長文／小說 → 分集：匯入、Agnes 分析概要與角色、分集規劃、子專案。
