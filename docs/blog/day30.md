# Day 30｜部署與回顧：打包、Docker、Cloud Run 與下一個 30 天

> 30 天打造 AI 短影片生成平台 — 第 30 天

## 今日目標
- 三種部署方式：本機一鍵啟動、Docker、Google Cloud Run。
- 備份與資料搬遷。
- 回顧 30 天的架構決策，列出下一個 30 天的方向。

## 部署一：本機

已經有 `start.bat` / `start.sh`。補上：
- `--host 0.0.0.0` 讓區網的手機能開，並在設定頁顯示區網 IP 與 QR code。
- Windows 可用 `nssm` 或工作排程器把它變成開機服務。

## 部署二：Docker

`Dockerfile`（多階段，前端在 Node 階段建置）：

```dockerfile
FROM node:20-slim AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY easyaivideo/ easyaivideo/
COPY config.example.yaml ./
COPY --from=web /app/frontend/dist frontend/dist
ENV EASYAIVIDEO_CONFIG=/data/config.yaml EASYAIVIDEO_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8000
CMD ["uv", "run", "easyaivideo", "--host", "0.0.0.0", "--port", "8000"]
```

`fonts-noto-cjk` 解決中文字幕；設定與資料都在 `/data` volume，升級映像不會掉專案。

```bash
docker build -t easyaivideo .
docker run -d -p 8000:8000 -v easyaivideo-data:/data -e GEMINI_API_KEY=$GEMINI_API_KEY easyaivideo
```

## 部署三：Cloud Run

適合想給團隊用、又不想管機器的情況。注意三件事：

1. **檔案系統是暫時的**：`/data` 要掛 Cloud Storage（Cloud Run 支援 GCS volume mount），或把素材改存 GCS、SQLite 改 Cloud SQL。單人用 GCS volume mount 最省事。
2. **請求逾時**：Cloud Run 預設 5 分鐘，但我們的任務在背景佇列跑、API 立即回 202，所以不受影響。要把「最小執行個體」設 1，否則佇列會隨容器縮到 0 消失。
3. **金鑰**：用 Secret Manager 注入 `GEMINI_API_KEY`，不要放在映像或設定檔。

```bash
gcloud run deploy easyaivideo --source . --region asia-east1 \
  --memory 2Gi --cpu 2 --min-instances 1 --timeout 3600 \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest \
  --add-volume name=data,type=cloud-storage,bucket=easyaivideo-data \
  --add-volume-mount volume=data,mount-path=/data
```

加上 IAP 或簡單的 Basic Auth 中介層，不要把生成介面公開在網際網路上，否則你的金鑰會被別人花光。

## 備份

`GET /api/backup.zip`：打包 `easyaivideo.db`、`config.yaml`（遮罩金鑰）與所有 `projects/`。搬到新機器只要解壓到 `data/` 再啟動。

## 30 天回顧：哪些決策值得

| 決策 | 回報 |
|---|---|
| 六段管線、每段獨立存檔 | 任何一步失敗都能續做；工作台的單場景重生就是免費得到的 |
| 供應商抽象層 + mock | 開發期幾乎沒花錢；換模型只改一個檔 |
| Project 整包 JSON | 場景結構從 3 個欄位長到 15 個，沒做過一次 migration |
| stale 旗標 | 「換比例只重做圖片」「改一行只重合成一行」都靠它 |
| 結構化輸出 | 從第一天到最後一天沒寫過一行 JSON 修補程式 |
| 提示詞集中管理 | A/B 與版本紀錄成為可能 |
| asyncio 佇列而非 Celery | 安裝只要 uv 與 ffmpeg |

## Antigravity 的使用心得

- **Planning 模式的計畫 Artifact 是最有價值的功能**：大部分的錯誤在計畫階段就能被你一眼看出來。
- **內建瀏覽器代理**讓前端週的驗證幾乎不用自己動手，但要明確要求「截圖給我」。
- **規則檔要持續維護**：每次它犯同樣的錯（例如直接在 router 呼叫 SDK），就把規則寫進去。
- **小任務比大任務好**：一天一個模組、附驗收條件，成功率遠高於「幫我做完整個功能」。

## Gemini API 的使用心得

- 結構化輸出 + Pydantic 是最省事的組合，`description` 就是提示詞。
- Nano Banana 帶參考圖的角色一致性，讓「小說分集」這種功能變得可行。
- TTS 用自然語言控制語氣，比 SSML 直覺；PCM 需自己包 wav，長度直接算。
- Veo 是長時間操作，設計上一定要非同步 + 輪詢，並先給使用者看預估費用。
- 上下文快取對「同一本書問很多次」的場景非常划算。

## 下一個 30 天可以做什麼

1. **逐字時間戳**：用 Gemini 多模態對音訊做逐字對齊，做卡拉 OK 式字幕。
2. **模板系統**：把風格、字型、字幕位置、轉場、BGM 打包成可分享的模板。
3. **多語言版本**：同一個專案一鍵翻譯旁白並重新配音，輸出多語影片。
4. **AI 審片**：把成品送給 Gemini 看（影片輸入），要它指出節奏、字幕錯字與畫面不符的地方。
5. **多使用者與權限**：登入、專案隔離、每人預算。
6. **外掛供應商**：保留 Gemini 為預設，但抽象層已經在，可以接 ComfyUI 或其他影片模型。
7. **排程發布**：合成完成後自動上傳 YouTube Shorts / TikTok。

## 給 Antigravity 的最後一個提示詞
```
建立 Dockerfile（多階段、ffmpeg、Noto CJK、uv、/data volume）、docker-compose.yml、GET /api/backup.zip、
設定頁的區網 IP 與 QR code、Basic Auth 中介層（環境變數 EASYAIVIDEO_AUTH=user:pass 時啟用）。
更新 README 的部署章節。本機 docker build 並啟動，用瀏覽器確認首頁可開、能建立專案並用 mock 設定跑完一次。
```

## 今日檢查清單
- [ ] Docker 容器啟動後中文字幕正常顯示。
- [ ] 刪掉容器重建，專案還在。
- [ ] README 的部署章節能讓沒看過這 30 篇的人照著跑起來。

## 結語

30 天前這只是一句話：「輸入主題，輸出影片」。現在它是一個有工作台、有任務佇列、能改編整本小說、能估算費用的平台。
真正的重點不是任何一個模型或工具，而是把問題切成可以獨立驗證的小段，然後讓 AI 幫你一段一段蓋起來。
祝你的下一個 30 天順利。
