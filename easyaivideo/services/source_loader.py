"""Extract plain text from uploaded documents: txt, md, docx, epub, pdf."""

from __future__ import annotations

import io
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

SUPPORTED = {".txt", ".md", ".markdown", ".docx", ".epub", ".pdf"}
_COMMON_TRAD = set("的一是不了在人有我他這個們中來上大為和國地到以說時要就出會可也你對生能而子那得於著下自之年過發後作裡用道行所然家種事成方多經麼去法學如都同現當沒動面起看定天分還進好小部其些主樣理心她本前開但因只從想實")
_COMMON_SIMP = set("的一是不了在人有我他这个们中来上大为和国地到以说时要就出会可也你对生能而子那得于着下自之年过发后作里用道行所然家种事成方多经么去法学如都同现当没动面起看定天分还进好小部其些主样理心她本前开但因只从想实")


class SourceError(ValueError):
    pass


def decode_bytes(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    candidates: list[str] = []
    for enc in ("big5", "gb18030"):
        try:
            candidates.append(data.decode(enc))
        except UnicodeDecodeError:
            continue
    if not candidates:
        return data.decode("utf-8", errors="replace")
    if len(candidates) == 1:
        return candidates[0]

    def score(text: str, common: set[str]) -> float:
        cjk = [c for c in text[:20000] if "一" <= c <= "鿿"]
        return (sum(1 for c in cjk if c in common) / len(cjk)) if cjk else 0.0

    big5, gb = candidates
    return big5 if score(big5, _COMMON_TRAD) >= score(gb, _COMMON_SIMP) else gb


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("　", " ")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _docx_text(data: bytes) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        try:
            xml = zf.read("word/document.xml")
        except KeyError as exc:
            raise SourceError("Invalid .docx file (word/document.xml missing)") from exc
    root = ET.fromstring(xml)
    paragraphs = []
    for p in root.iter(f"{{{ns['w']}}}p"):
        texts = [t.text or "" for t in p.iter(f"{{{ns['w']}}}t")]
        paragraphs.append("".join(texts))
    return "\n".join(paragraphs)


class _HTMLText(HTMLParser):
    BLOCK = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "section", "article", "blockquote"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:  # type: ignore[override]
        if tag in ("script", "style", "head"):
            self._skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def _html_to_text(html: str) -> str:
    parser = _HTMLText()
    parser.feed(html)
    return parser.text()


def _epub_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        try:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
        except KeyError as exc:
            raise SourceError("Invalid .epub file (container.xml missing)") from exc
        rootfile = None
        for el in container.iter():
            if el.tag.endswith("rootfile"):
                rootfile = el.get("full-path")
                break
        if not rootfile:
            raise SourceError("Invalid .epub file (no rootfile)")
        opf = ET.fromstring(zf.read(rootfile))
        base = PurePosixPath(rootfile).parent
        manifest: dict[str, str] = {}
        spine: list[str] = []
        for el in opf.iter():
            if el.tag.endswith("item") and el.get("id") and el.get("href"):
                manifest[el.get("id", "")] = el.get("href", "")
            elif el.tag.endswith("itemref") and el.get("idref"):
                spine.append(el.get("idref", ""))
        chunks = []
        for idref in spine:
            href = manifest.get(idref)
            if not href:
                continue
            path = str(base / href) if str(base) != "." else href
            try:
                raw = zf.read(path)
            except KeyError:
                continue
            chunks.append(_html_to_text(decode_bytes(raw)))
        return "\n\n".join(chunks)


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise SourceError("pypdf is not installed") from exc
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001
            pages.append("")
    return "\n\n".join(pages)


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise SourceError(f"Unsupported file type '{ext}'. Supported: txt, md, docx, epub, pdf.")
    if ext in (".txt", ".md", ".markdown"):
        text = decode_bytes(data)
    elif ext == ".docx":
        text = _docx_text(data)
    elif ext == ".epub":
        text = _epub_text(data)
    else:
        text = _pdf_text(data)
    text = normalize(text)
    if len(text.strip()) < 10:
        raise SourceError("No readable text found in the document.")
    return text
