# Day 26｜影片預覽、下載與素材打包 zip

> 30 天打造 AI 短影片生成平台 — 第 26 天

## 今日目標
- 工作台右半邊：影片播放器、下載按鈕、字幕下載、素材 zip。
- 輸出版本紀錄：每次合成保留一份，可以回看與比較。
- Range 請求支援，讓影片可以拖曳進度條。

## 預覽區

```tsx
function Preview({ project }: { project: Project }) {
  if (!project.output_path) return <EmptyState text="尚未合成影片" />;
  const src = `/data/${project.output_path}?v=${project.updated_at}`;
  return (
    <div className="sticky top-4 space-y-3">
      <video key={src} src={src} controls playsInline className={aspectClass(project.options.aspect)} />
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

`key={src}` 讓 React 在檔案更新時重建 `<video>`，否則會停在舊影片。直式影片限制最大高度 70vh，橫式限制寬度。

## Range 請求

`StaticFiles` 已支援 `Range` 標頭，Chrome 拖進度條沒問題。若之後改成自訂路由回傳影片，記得用 `FileResponse` 並保留 `Accept-Ranges`。

## 打包 zip

```python
import zipfile, io
from fastapi.responses import StreamingResponse

@router.get("/api/projects/{pid}/export.zip")
async def export_zip(pid: str, svc=Depends(get_project_service)):
    p = await svc.get(pid)
    pdir = svc.project_dir(pid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", p.model_dump_json(indent=2))
        z.writestr("script.md", render_script_md(p))
        for s in p.scenes:
            for attr in ("image_path", "audio_path", "clip_path"):
                path = getattr(s, attr)
                if path: z.write(svc.abs(path), arcname=Path(path).name)
        if p.output_path: z.write(svc.abs(p.output_path), "output.mp4")
        if (pdir / "subtitles.srt").exists(): z.write(pdir / "subtitles.srt", "subtitles.srt")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{pid}.zip"'})
```

`script.md` 把標題、每場旁白與提示詞整理成人類可讀的文件，方便拿去其他剪輯軟體用。

## 版本紀錄

每次 `render` 完成，把 `output.mp4` 複製成 `output_<timestamp>.mp4`，並在 project 記錄：

```python
class OutputVersion(BaseModel):
    path: str; created_at: datetime; duration: float; size: int; note: str = ""

class Project(BaseModel):
    ...
    outputs: list[OutputVersion] = []
```

保留最近 5 版，超過的刪檔。前端 `Versions` 列表點一下就切換播放器來源，可以「設為目前」或「刪除」。

## 匯出品質選單

下載按鈕旁邊一個小選單：「快速預覽」「一般」「高品質」，對應 Day 18 的 `QUALITY`。選高品質會重新合成一次（只重做第二層串接與編碼，很快）。

## 分享連結

單機工具通常不需要，但如果你把伺服器放在區網，`GET /share/{pid}` 回一個極簡 HTML 頁只含播放器，手機掃 QR code 就能看。QR code 用 `qrcode` 套件在前端生成。

## 給 Antigravity 的提示詞
```
實作 Preview 元件（video、下載影片/SRT/zip、版本列表與切換）、export.zip 路由（含 script.md）、
OutputVersion 與 render 後的版本保留（最多 5 版）、匯出品質選單、/share/{pid} 極簡頁。
用瀏覽器合成一次、下載 zip 並列出其中的檔案給我。
```

## 今日檢查清單
- [ ] 合成完成後播放器自動換成新影片，拖曳進度條正常。
- [ ] zip 內有 project.json、script.md、所有素材與 output.mp4。
- [ ] 合成 6 次後只保留 5 個版本檔。

## 明日預告
Day 27 長文／小說 → 分集影片：匯入整本文件、Gemini 分析概要與角色、規劃分集、每集變成子專案。
