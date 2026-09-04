# Day 04｜第一支 Gemini 程式：google-genai SDK、串流與結構化輸出

> 30 天打造 AI 短影片生成平台 — 第 4 天

## 今日目標
- 用 uv 建立專案虛擬環境並安裝 `google-genai`。
- 完成三種呼叫：一般回覆、串流回覆、JSON Schema 結構化輸出。
- 學會控制 thinking 預算與 system instruction。

## 初始化 Python 專案

```bash
cd EasyAIVideo
uv init --name easyaivideo --python 3.11
uv add google-genai pydantic pyyaml
```

`uv` 會產生 `pyproject.toml`、`uv.lock` 與 `.venv`。之後所有指令都用 `uv run python ...`，不用手動啟動虛擬環境。

## 最小呼叫

建立 `scripts/hello_gemini.py`：

```python
from google import genai

client = genai.Client()  # 自動讀取 GEMINI_API_KEY

resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="用一句話介紹什麼是短影片。",
)
print(resp.text)
```

```bash
uv run python scripts/hello_gemini.py
```

## 串流輸出

腳本生成通常要好幾秒，串流可以讓 UI 逐字顯示（Day 25 會用到）：

```python
for chunk in client.models.generate_content_stream(
    model="gemini-2.5-flash",
    contents="寫一段 100 字的貓咪短影片旁白。",
):
    print(chunk.text, end="", flush=True)
```

## 結構化輸出：這是整個平台的基石

我們的腳本、分集規劃、角色分析全都需要「一定是合法 JSON、一定符合我們的欄位」。Gemini 支援直接傳 Pydantic 模型當 schema：

```python
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

class Scene(BaseModel):
    narration: str = Field(description="繁體中文旁白，30–50 字")
    image_prompt: str = Field(description="英文畫面描述，不含文字或字幕")

class Script(BaseModel):
    title: str
    scenes: list[Scene]

client = genai.Client()
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="主題：為什麼貓咪喜歡紙箱。寫 5 個場景的知識型短影片腳本。",
    config=types.GenerateContentConfig(
        system_instruction="你是短影片編劇，輸出必須符合 schema。",
        response_mime_type="application/json",
        response_schema=Script,
        temperature=0.8,
    ),
)

script: Script = resp.parsed          # SDK 直接幫你轉成 Pydantic 物件
print(script.title)
for i, s in enumerate(script.scenes, 1):
    print(i, s.narration, "|", s.image_prompt)
```

重點：
- `response_mime_type="application/json"` + `response_schema` 會讓模型在解碼層就被限制成合法 JSON。
- `resp.parsed` 是已驗證的 Pydantic 實例；若你要原始字串用 `resp.text`。
- 欄位的 `description` 會被送給模型，等於是在 schema 裡寫提示詞。

## Thinking 預算

2.5 系列預設會「思考」，品質好但比較慢也較貴。腳本生成可以保留一點，分段這種簡單任務可以關掉：

```python
config=types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_budget=0),  # 關閉思考
)
```

## 非同步版本

FastAPI 是 async 框架，之後供應商層會用 `client.aio`：

```python
import asyncio
from google import genai

async def main():
    client = genai.Client()
    resp = await client.aio.models.generate_content(
        model="gemini-2.5-flash", contents="hi")
    print(resp.text)

asyncio.run(main())
```

## 常見錯誤
- `403 API key not valid`：金鑰貼錯或環境變數沒生效，重開終端機。
- `429 RESOURCE_EXHAUSTED`：免費層配額用完，稍等或升級付費層；Day 29 會加上重試。
- `parsed` 是 `None`：模型輸出被安全過濾或截斷，檢查 `resp.candidates[0].finish_reason`。

## 給 Antigravity 的提示詞
```
建立 scripts/hello_gemini.py，示範 google-genai 的三種呼叫：一般、串流、以 Pydantic schema 做結構化輸出
（Script 含 title 與 scenes[narration, image_prompt]）。使用 uv run 可直接執行，
並在檔案頂端註解說明如何設定 GEMINI_API_KEY。不要把金鑰寫進程式。
```

## 今日檢查清單
- [ ] `uv run python scripts/hello_gemini.py` 三種模式都成功。
- [ ] 能解釋 `response_schema` 與 `resp.parsed` 的關係。
- [ ] 知道怎麼關閉 thinking。

## 明日預告
Day 05 畫出整個系統的架構圖與資料流，決定模組邊界與目錄結構。
