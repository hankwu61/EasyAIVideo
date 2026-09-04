# Day 30｜部署與回顧：Docker、區網部署、備份與下一個 30 天

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 30 天

## 今日目標
- 三種部署：本機一鍵、Docker、區網給團隊用。
- 備份與搬遷。
- 回顧 30 天的決策，列出下一個 30 天。

## 部署一：本機

`start.bat` / `start.sh` 已可用。加 `--host 0.0.0.0` 讓手機能開，設定頁顯示區網 IP 與 QR code。Windows 用工作排程器或 nssm 做成服務。

## 部署二：Docker

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

```bash
docker build -t easyaivideo .
docker run -d -p 8000:8000 -v easyaivideo-data:/data -e AGNES_API_KEY=$AGNES_API_KEY easyaivideo
```

`fonts-noto-cjk` 解決中文字幕；Edge-TTS 需要容器能連外網。

## 部署三：區網給團隊

- 反向代理（Caddy 一行設定）加 Basic Auth 或內網 SSO。**不要**把生成介面公開到網際網路，Agnes 金鑰會被別人花光。
- `EASYAIVIDEO_AUTH=user:pass` 環境變數啟用內建 Basic Auth 中介層。
- 多人同時用時把 `video.concurrency` 保持 1、圖片 2，任務會排隊而不是互撞。

## 備份

`GET /api/backup.zip`：`easyaivideo.db`、`config.yaml`（遮罩金鑰）、`projects/`。解壓到新機器的 `data/` 即可。

## 30 天回顧：哪些決策值得

| 決策 | 回報 |
|---|---|
| 六段管線、每段獨立存檔 | 任何一步失敗都能續做，單場景重生免費得到 |
| 供應商抽象層 + mock | 開發期幾乎零成本；Agnes 換別的 OpenAI 相容服務只改 base_url |
| httpx 而非供應商 SDK | 沒有版本綁定，同一段程式碼打 OpenAI、DeepSeek、Agnes、本地 Ollama |
| 三層 JSON 防禦 | 不管服務支不支援 `response_format` 都穩 |
| Edge-TTS 逐字時間戳 | 免費拿到精準字幕，付費 TTS 反而多半沒有 |
| stale 旗標 | 換比例只重做圖、改一行只重合成一行 |
| Project 整包 JSON | 場景欄位長到 20 個沒 migrate 過 |

## Claude Code 的使用心得

- **CLAUDE.md 是槓桿**：每次它犯同樣的錯就加一行，30 天後它幾乎不需要提醒。
- **Plan 模式先看再做**：大部分錯誤在計畫階段就能看出，比看 diff 便宜得多。
- **一次一個可驗證單位** + 「跑測試把結果貼給我」，成功率遠高於「做完整個功能」。
- **子代理做探索與驗證**，主對話不被檔案內容塞滿。
- **hooks 做自動化**：編輯後自動 lint 與跑相關測試，回歸在發生的當下就被抓到。
- **launch.json + 瀏覽器面板**：前端週幾乎不用自己點，只看截圖與 console。

## Agnes AI 與 Edge-TTS 的使用心得

- Agnes 一把金鑰三種能力，設定頁的「同步金鑰」按鈕是小事但很省心。
- 圖片端點的 `image` 參考圖陣列是角色一致性的關鍵；影片端點是裸 base64，兩者不同要記得。
- 影片 API 的 8n+1 幀規則與併發 1 的限制，寫進程式就不會再踩。
- Edge-TTS 免費但沒有 SLA：重試、釘版本、退回方案三件事做好就很穩。

## 下一個 30 天

1. **卡拉 OK 逐字精準版**：用 words 計算每個字的寬度序列。
2. **模板系統**：風格、字型、字幕位置、轉場、BGM 打包成可分享模板。
3. **多語言版本**：翻譯旁白 + 對應語言的 Edge-TTS 聲音，一鍵輸出多語影片。
4. **AI 審片**：把成品關鍵幀送給 Agnes 多模態模型，指出畫面與旁白不符處。
5. **ComfyUI 供應商**：本地 GPU 跑圖生影片工作流，抽象層已經在。
6. **多使用者與每人預算**。
7. **排程發布**：合成完自動上傳 YouTube Shorts / TikTok。

## 給 Claude Code 的最後一個提示詞
```
建立 Dockerfile（多階段、ffmpeg、Noto CJK、uv、/data volume）、docker-compose.yml、GET /api/backup.zip、
EASYAIVIDEO_AUTH Basic Auth 中介層、設定頁區網 IP 與 QR。更新 README 部署章節與 CLAUDE.md。
本機 docker build 並啟動，用預覽確認可建立專案並以 mock 設定跑完一次。
```

## 今日檢查清單
- [ ] 容器內中文字幕正常。
- [ ] 刪掉容器重建，專案還在。
- [ ] README 部署章節能讓新人照著跑。

## 結語

30 天前是一句話：「輸入主題，輸出影片」。現在是一個有工作台、任務佇列、能改編整本小說、能估費用的平台，而且語音免費、AI 金鑰只有一把。
重點不在任何一個模型或工具，而是把問題切成能獨立驗證的小段，然後讓 Claude Code 一段一段幫你蓋起來。
祝你的下一個 30 天順利。
