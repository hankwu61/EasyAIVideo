# Day 04｜第一支程式：用 httpx 呼叫 Agnes chat/completions，並可靠地拿到 JSON

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 4 天

## 今日目標
- 用 uv 初始化專案，安裝 `httpx`、`pydantic`、`pyyaml`。
- 完成三種呼叫：一般、串流、JSON 模式。
- 寫出 `extract_json()`：不管模型多不聽話都能取出 JSON，再用 Pydantic 驗證。

## 初始化

```bash
uv init --name easyaivideo --python 3.11
uv add httpx pydantic pyyaml
```

## 最小呼叫

`scripts/hello_agnes.py`：

```python
import os, httpx

BASE = "https://apihub.agnes-ai.com/v1"
HEADERS = {"Authorization": f"Bearer {os.environ['AGNES_API_KEY']}", "Content-Type": "application/json"}

def chat(prompt: str, system: str | None = None, model: str = "agnes-2.0-flash") -> str:
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    r = httpx.post(f"{BASE}/chat/completions", headers=HEADERS,
                   json={"model": model, "messages": messages, "temperature": 0.8}, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

print(chat("用一句話介紹什麼是短影片。"))
```

## 串流

```python
def chat_stream(prompt: str):
    with httpx.stream("POST", f"{BASE}/chat/completions", headers=HEADERS,
                      json={"model": "agnes-2.0-flash", "messages": [{"role": "user", "content": prompt}], "stream": True},
                      timeout=120) as r:
        for line in r.iter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            delta = json.loads(line[6:])["choices"][0]["delta"].get("content", "")
            print(delta, end="", flush=True)
```

SSE 格式與 OpenAI 相同。Day 25 前端逐字顯示腳本會用到。

## JSON：三層防禦

OpenAI 相容服務對 `response_format` 的支援程度不一，所以不能只靠它。三層：

1. **提示詞**：system 明講「只輸出 JSON，不要 markdown 圍欄，不要解釋」。
2. **response_format**：帶 `{"type": "json_object"}`，若服務回 400 就拿掉再試一次。
3. **extract_json**：直接解析 → 找 ```json 圍欄 → 找第一個 `{` 到最後一個 `}`。

```python
import json, re
from pydantic import BaseModel, ValidationError

def extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        return json.loads(text[s:e + 1])
    raise ValueError(f"回覆不含 JSON：{text[:120]!r}")

class Scene(BaseModel):
    narration: str
    image_prompt: str

class Script(BaseModel):
    title: str
    scenes: list[Scene]

def chat_json(prompt: str, system: str, schema: type[BaseModel], retries: int = 2):
    body = {"model": "agnes-2.0-flash", "temperature": 0.8,
            "messages": [{"role": "system", "content": system + "\n只輸出 JSON。"}, {"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}}
    last = None
    for attempt in range(retries + 1):
        r = httpx.post(f"{BASE}/chat/completions", headers=HEADERS, json=body, timeout=180)
        if r.status_code == 400 and "response_format" in body:
            body.pop("response_format"); continue          # 服務不支援就退回純提示詞
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        try:
            return schema.model_validate(extract_json(text))
        except (ValueError, ValidationError) as e:
            last = e
            body["messages"].append({"role": "assistant", "content": text})
            body["messages"].append({"role": "user", "content": f"上面的輸出不符合要求：{e}。請只輸出正確的 JSON。"})
    raise RuntimeError(f"三次都拿不到合法 JSON：{last}")
```

驗證失敗時把錯誤回饋給模型再試，比單純重打成功率高很多。

## 非同步版本

之後供應商層用 `httpx.AsyncClient`：

```python
async with httpx.AsyncClient(timeout=180) as client:
    r = await client.post(f"{BASE}/chat/completions", headers=HEADERS, json=body)
```

## 常見錯誤
- 401：金鑰錯或沒帶 `Bearer `。
- 404 model not found：模型名稱打錯，去 `/models` 查。
- 回覆被 markdown 圍欄包住：`extract_json` 第二層會處理。
- 中文被轉成 `\uXXXX`：`json.loads` 會還原，不用管。

## 給 Claude Code 的提示詞
```
建立 scripts/hello_agnes.py 示範 chat、串流、chat_json 三種呼叫，chat_json 需含 response_format 退回、extract_json 三層解析、
Pydantic 驗證失敗回饋重試。用 uv run 執行，把三種輸出貼給我。金鑰只從環境變數 AGNES_API_KEY 讀。
```

## 今日檢查清單
- [ ] 三種呼叫都成功。
- [ ] 故意把 system 改成「用 markdown 回答」，`chat_json` 仍能解析。
- [ ] 能解釋為什麼需要三層防禦。

## 明日預告
Day 05 畫出整個系統的架構圖與資料流，決定模組邊界與目錄結構。
