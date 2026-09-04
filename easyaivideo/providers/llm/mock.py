"""Mock LLM: deterministic output so the whole pipeline runs without any API key."""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def _between(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end in body else body


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in re.split(r"(?<=[。！？!?；;])(?![」』\"”])\s*|(?<=\.)\s+|\n+", text) if s and s.strip()]
    return [p for p in parts if re.search(r"[A-Za-z0-9぀-ヿ㐀-鿿가-힯]", p)]


def _is_cjk(prompt: str) -> bool:
    return any(k in prompt for k in ("Traditional Chinese", "Simplified Chinese", "Japanese", "Korean"))


class MockLLM:
    name = "mock"

    async def complete(self, prompt: str, *, system: Optional[str] = None) -> str:
        return json.dumps(await self.complete_json(prompt), ensure_ascii=False)

    async def complete_json(self, prompt: str, *, system: Optional[str] = None) -> dict[str, Any]:
        cjk = _is_cjk(prompt)
        if prompt.startswith("TASK: ANALYZE_DOCUMENT"):
            doc = _between(prompt, "<<<\n", "\n>>>")
            names = re.findall(r"[「『\"]([^」』\"]{1,8})[」』\"]", doc)
            candidates = list(dict.fromkeys(n for n in names if 1 < len(n) <= 4))[:3] or (["主角", "配角"] if cjk else ["Hero", "Friend"])
            chars = [
                {"name": n, "description": ("示範角色描述（mock LLM）" if cjk else "Demo character (mock LLM)"),
                 "gender": "female" if i % 2 else "male",
                 "appearance": f"person in traditional clothing, distinct look number {i + 1}, detailed face, soft light"}
                for i, n in enumerate(candidates)
            ]
            return {
                "overview": {"synopsis": doc[:160].replace("\n", " "), "genre": "示範" if cjk else "Demo",
                             "theme": "mock LLM 無法真正分析，請設定 LLM。" if cjk else "Configure an LLM for real analysis.",
                             "world_setting": ""},
                "characters": chars,
                "locations": [{"name": "主要場景" if cjk else "Main location", "description": ""}],
            }
        if prompt.startswith("TASK: REVIEW_SUMMARY"):
            rows = [ln for ln in prompt.splitlines() if "|" in ln and ln.split("|")[0].strip().isdigit()]
            low = [ln.split("|")[0].strip() for ln in rows if ln.split("|")[1].strip().isdigit() and int(ln.split("|")[1]) <= 2]
            if cjk:
                text = f"共 {len(rows)} 個場景。" + (f"場景 {', '.join(low)} 的畫面與旁白不符，建議先修正。" if low else "畫面與旁白大致相符。") + "（mock 摘要）"
            else:
                text = f"{len(rows)} scenes reviewed. " + (f"Scenes {', '.join(low)} do not match the narration; fix them first." if low else "Visuals match the narration.") + " (mock summary)"
            return {"summary": text}
        if prompt.startswith("TASK: EPISODE_TITLES"):
            idx = [int(i) for i in re.findall(r"\[EPISODE (\d+)\]", prompt)]
            return {"episodes": [{"index": i, "title": (f"第 {i} 集" if cjk else f"Episode {i}"), "summary": ""} for i in idx]}
        if prompt.startswith("TASK: EPISODE_SCRIPT"):
            mode = "drama" if "(drama)" in prompt.split("\n", 1)[0] else "narration"
            excerpt = _between(prompt, "EXCERPT:\n<<<\n", "\n>>>")
            title = _between(prompt, "EPISODE TITLE: ", "\n").strip() or "Episode"
            sents = _sentences(excerpt) or [excerpt[:60]]
            n = max(3, min(12, len(sents) // 3 or 1))
            per = max(1, -(-len(sents) // n))
            scenes = []
            for i in range(0, len(sents), per):
                chunk = sents[i : i + per]
                scene: dict[str, Any] = {"image_prompt": f"illustration of: {' '.join(chunk)[:100]}", "location": None}
                if mode == "drama":
                    scene["lines"] = [{"speaker": None, "text": s} for s in chunk]
                else:
                    scene["narration"] = "".join(chunk) if cjk else " ".join(chunk)
                scenes.append(scene)
            return {"title": title, "scenes": scenes}
        if "SEGMENTS:" in prompt:
            block = prompt.split("SEGMENTS:", 1)[1].split("\n\nTASKS", 1)[0]
            segments = [re.sub(r"^\d+\.\s*", "", line).strip() for line in block.strip().splitlines() if line.strip()]
            return {
                "title": (segments[0][:12] if segments else "Untitled"),
                "image_prompts": [f"illustration of: {s[:80]}" for s in segments],
            }
        topic = prompt.split("TOPIC:", 1)[1].split("\n\nREQUIREMENTS", 1)[0].strip() if "TOPIC:" in prompt else "topic"
        n = 5
        m = re.search(r"exactly (\d+) scenes", prompt)
        if m:
            n = int(m.group(1))
        scenes = []
        for i in range(1, n + 1):
            if cjk:
                narration = f"這是關於「{topic[:20]}」的第 {i} 段示範旁白。請在設定頁面配置 LLM，即可由 AI 撰寫真正的腳本。"
            else:
                narration = f"This is demo narration number {i} about {topic[:40]}. Configure an LLM in Settings to get a real AI-written script."
            scenes.append({"narration": narration, "image_prompt": f"{topic[:60]}, scene {i}, wide establishing shot, soft light"})
        return {"title": topic[:12] if cjk else " ".join(topic.split()[:6]), "scenes": scenes}

    async def test(self) -> str:
        return "Mock LLM is active (no external calls)."
