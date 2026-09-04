# Day 09｜貼上文稿也能用：長文分段、場景切分與提示詞補全

> 30 天打造 AI 短影片生成平台 — 第 9 天

## 今日目標
- 使用者貼上自己的文稿時，不改寫內容，只做分段與補提示詞。
- 處理超長文稿：先在程式端粗切，再交給 Gemini 細切。
- 支援 `.txt` / `.md` / `.docx` / `.pdf` 上傳並自動偵測編碼。

## 兩種輸入，兩條路

| 輸入 | 行為 |
|---|---|
| 主題 | Gemini 從零撰寫（Day 08） |
| 文稿 | **保留原文**，Gemini 只負責切成場景並補 `image_prompt` / `video_prompt` |

使用者貼文稿通常是因為那是他們的講稿或文案，被 AI 改寫會很反感。所以提示詞要明講「逐字保留」。

## 分段提示詞

```python
SEGMENT_SYSTEM = """你是短影片分鏡師。使用者提供一段文稿，請：
1. 把文稿切成 {scene_count} 個左右的場景。每個場景的 narration 必須逐字取自原文，不可改寫、不可省略、不可新增文字，
   所有場景的 narration 串接起來必須等於原文（可調整標點與換行）。
2. 每個場景配一個英文 image_prompt（風格：{style}，不得含文字）與 video_prompt。
3. 給整支影片一個 10 字內的標題。
切分原則：一個場景一個畫面；句意轉折處切；每場 {min_chars}–{max_chars} 字。"""
```

輸出 schema 沿用 `ScriptDraft`。程式端做一次驗證：把所有 narration 去掉空白與標點後串接，和原文比對相似度（`difflib.SequenceMatcher`），低於 0.95 就重試一次並降溫。

## 超長文稿的粗切

Gemini 的上下文很大（百萬 token 等級），但一次要它切 200 個場景會讓輸出品質與速度都變差。策略：

```python
def rough_chunks(text: str, max_chars: int = 1500) -> list[str]:
    """按段落切成 1500 字左右的區塊，段落太長再按句號切。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > max_chars and buf:
            chunks.append(buf); buf = ""
        buf = f"{buf}\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    return chunks
```

每個區塊各自呼叫分段，最後把場景合併並重新編號。多個區塊可以用 `asyncio.gather` 並行，注意免費層的每分鐘配額。

## 文件擷取

`services/source_loader.py`：

```python
from pathlib import Path

def load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return decode_bytes(path.read_bytes())
    if suffix == ".docx":
        import docx
        return "\n\n".join(p.text for p in docx.Document(path).paragraphs)
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if suffix == ".epub":
        ...  # ebooklib + BeautifulSoup
    raise ValueError(f"不支援的格式：{suffix}")

def decode_bytes(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "big5", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")
```

```bash
uv add python-docx pypdf ebooklib beautifulsoup4
```

路由：`POST /api/projects/{id}/source`（multipart 上傳，寫入 `project.source_text`）。

## 管線分流

```python
async def write_script(self, project):
    if project.source_text:
        draft = await self.llm.segment_script(project.source_text, ...)
    else:
        draft = await self.llm.write_script(project.topic, ...)
    ...
```

## 給 Antigravity 的提示詞
```
新增 prompts.SEGMENT_SYSTEM、GeminiLLM.segment_script（保留原文、相似度驗證與重試）、rough_chunks 分塊與並行合併、
services/source_loader.py（txt/md/docx/pdf/epub，多編碼偵測）、POST /api/projects/{id}/source 上傳路由，
並讓 pipeline.write_script 依 source_text 有無分流。用一篇 3000 字的繁中文章測試，確認 narration 串接後與原文相似度 > 0.95。
```

## 今日檢查清單
- [ ] 貼上 800 字文稿 → 6–8 個場景，原文一字不差。
- [ ] 上傳 Big5 編碼的 txt 不會出現亂碼。
- [ ] 5000 字文稿能在 30 秒內完成分段。

## 明日預告
Day 10 建立供應商抽象層與 mock 實作，讓整條管線在沒有金鑰、不花錢的情況下也能跑通。
