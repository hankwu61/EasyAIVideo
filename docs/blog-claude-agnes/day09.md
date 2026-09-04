# Day 09｜貼上文稿也能用：長文分段、文件擷取與多編碼偵測

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 9 天

## 今日目標
- 文稿模式：逐字保留原文，只切段與補提示詞。
- 超長文稿：程式粗切 + 模型細切 + 並行合併。
- 上傳 `.txt` `.md` `.docx` `.pdf` `.epub`，自動偵測 UTF-8 / Big5 / GB18030。

## 兩種輸入

| 輸入 | 行為 |
|---|---|
| 主題 | 模型從零撰寫 |
| 文稿 | **逐字保留**，模型只切場景並補 `image_prompt` / `video_prompt` |

## 分段提示詞

```python
SEGMENT_SYSTEM = """你是短影片分鏡師。把使用者的文稿切成約 {scene_count} 個場景：
1. 每場 narration 必須逐字取自原文，不可改寫、省略或新增；所有 narration 依序串接後必須等於原文（標點與換行可調整）。
2. 每場配英文 image_prompt（風格 {style}，禁止文字）與 video_prompt。
3. 給影片一個 10 字內標題。
切分原則：一場一畫面，句意轉折處切，每場 {min_chars}–{max_chars} 字。只輸出 JSON。"""
```

程式端驗證：把 narration 去空白標點後串接，與原文比 `difflib.SequenceMatcher().ratio()`，低於 0.95 就把差異回饋給模型重試一次（溫度降到 0.2）。

## 粗切

```python
def rough_chunks(text: str, max_chars: int = 1500) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > max_chars and buf:
            chunks.append(buf); buf = ""
        buf = f"{buf}\n{p}" if buf else p
    if buf: chunks.append(buf)
    return chunks
```

每塊各自分段，`asyncio.gather` 並行（Semaphore 限 3），合併後重新編號。

## 文件擷取

```bash
uv add python-docx pypdf ebooklib beautifulsoup4
```

```python
def decode_bytes(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "big5", "gb18030"):
        try: return data.decode(enc)
        except UnicodeDecodeError: continue
    return data.decode("utf-8", errors="replace")

def load_text(path: Path) -> str:
    s = path.suffix.lower()
    if s in {".txt", ".md"}: return decode_bytes(path.read_bytes())
    if s == ".docx": return "\n\n".join(p.text for p in docx.Document(path).paragraphs)
    if s == ".pdf": return "\n\n".join(pg.extract_text() or "" for pg in PdfReader(path).pages)
    if s == ".epub":
        book = epub.read_epub(str(path))
        return "\n\n".join(BeautifulSoup(i.get_content(), "html.parser").get_text("\n")
                           for i in book.get_items_of_type(ITEM_DOCUMENT))
    raise ValueError(f"不支援：{s}")
```

路由：`POST /api/source/extract`（只擷取回文字）與 `POST /api/projects/{id}/source`（寫入專案）。

## 管線分流

```python
draft = await llm.segment_script(project.source_text, ...) if project.source_text else await llm.write_script(project.topic, ...)
```

## 給 Claude Code 的提示詞
```
新增 SEGMENT_SYSTEM、OpenAICompatLLM.segment_script（相似度驗證與回饋重試）、rough_chunks 與並行合併、
services/source_loader.py（五種格式、多編碼）、/api/source/extract 與 /api/projects/{id}/source。
用 tests/fixtures/ 放一篇 Big5 編碼的 txt 與一個 docx 寫測試。用一篇 3000 字繁中文章實測，回報相似度。
```

## 今日檢查清單
- [ ] 800 字文稿 → 6–8 場，原文一字不差。
- [ ] Big5 txt 不亂碼。
- [ ] 5000 字在 30 秒內完成。

## 明日預告
Day 10 供應商抽象層與 mock，讓整條管線零成本跑通。
