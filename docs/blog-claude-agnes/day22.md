# Day 22｜前端骨架：React + Vite + Tailwind 與型別安全的 API client

> 30 天打造 AI 短影片生成平台（Claude Code × Agnes AI × Edge-TTS）— 第 22 天

## 今日目標
- `frontend/`：Vite + React + TypeScript + Tailwind。
- 薄的 API client，型別來自 `types.ts`。
- 側欄專案列表、主區域、設定頁入口、繁中／英文切換。
- 讓 Claude Code 用瀏覽器面板驗證前端。

## 建立

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm i && npm i -D tailwindcss @tailwindcss/vite
npm i react-router-dom @tanstack/react-query zustand lucide-react @dnd-kit/core @dnd-kit/sortable
```

`vite.config.ts` 設 `/api` 與 `/data` 代理到 8000；`build.outDir = "dist"`。後端在所有 `/api` 路由之後掛 `StaticFiles(directory="frontend/dist", html=True)` 並加 SPA fallback。

## API client

```ts
import type { components } from "./types";
export type Project = components["schemas"]["Project"];
export type Scene = components["schemas"]["Scene"];
export type Task = components["schemas"]["Task"];

export class ApiError extends Error { constructor(public status: number, public error: string, public detail?: string) { super(detail ?? error); } }

async function req<T>(method: string, url: string, body?: unknown, form = false): Promise<T> {
  const res = await fetch(url, { method, headers: form ? undefined : { "Content-Type": "application/json" },
                                 body: form ? (body as FormData) : body ? JSON.stringify(body) : undefined });
  if (!res.ok) { const e = await res.json().catch(() => ({ error: res.statusText })); throw new ApiError(res.status, e.error, e.detail); }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  projects: { list: () => req<Project[]>("GET", "/api/projects"), get: (id: string) => req<Project>("GET", `/api/projects/${id}`),
              create: (b: components["schemas"]["ProjectCreate"]) => req<Project>("POST", "/api/projects", b),
              generate: (id: string) => req<{ task: Task }>("POST", `/api/projects/${id}/generate`), /* assets, render, remove, duplicate */ },
  scenes: { update: (p: string, s: string, b: components["schemas"]["SceneUpdate"]) => req<Project>("PATCH", `/api/projects/${p}/scenes/${s}`, b),
            regenImage: (p: string, s: string) => req<{ task: Task }>("POST", `/api/projects/${p}/scenes/${s}/image`), /* ... */ },
  tasks: { get: (id: string) => req<Task>("GET", `/api/tasks/${id}`), cancel: (id: string) => req<Task>("POST", `/api/tasks/${id}/cancel`) },
  presets: () => req<components["schemas"]["Presets"]>("GET", "/api/presets"),
  tts: { voices: () => req<components["schemas"]["VoiceInfo"][]>("GET", "/api/tts/voices") },
  settings: { get: () => req("GET", "/api/settings"), patch: (b: unknown) => req("PATCH", "/api/settings", b),
              test: (s: string, b: unknown) => req<{ message: string }>("POST", `/api/settings/test/${s}`, b) },
};
```

## 版面與路由

```tsx
<QueryClientProvider client={qc}><BrowserRouter>
  <div className="flex h-screen bg-neutral-950 text-neutral-100">
    <Sidebar />
    <main className="flex-1 overflow-auto">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/projects/new" element={<NewProject />} />
        <Route path="/projects/:id" element={<Workbench />} />
        <Route path="/series/:id" element={<SeriesWorkbench />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </main>
  </div>
</BrowserRouter></QueryClientProvider>
```

## i18n

`src/i18n.ts` 一個字典物件 `zh-TW` / `en`，zustand store 存語言到 localStorage。

## 設定頁

五個區塊（LLM、圖片、影片、語音、輸出），每區塊「測試連線」按鈕把**表單目前的值**送到 `/api/settings/test/{section}`，成功才顯示綠色並允許儲存。LLM 區塊有「同步金鑰到圖片與影片」按鈕。語音區塊有聲音下拉與試聽。

## Claude Code 的前端驗證流程

launch.json 加一組 `frontend-dev`（`npm run dev`，port 5173）。每個前端任務都要求：「啟動 frontend-dev 預覽，操作一遍，讀 console 錯誤，截圖給我」。Claude Code 會自己開瀏覽器面板、點擊、讀 DOM，你只看截圖。

## 給 Claude Code 的提示詞
```
建立 frontend/（Vite React TS + Tailwind、代理、client.ts、React Query、路由、Sidebar、i18n、Settings 頁五區塊含測試連線與同步金鑰）；
後端加 dist 掛載與 SPA fallback；launch.json 加 frontend-dev。啟動預覽，截圖側欄、首頁與設定頁。
```

## 今日檢查清單
- [ ] `npm run dev` 側欄列出後端專案。
- [ ] `npm run build` 後 8000 埠直接看到前端。
- [ ] 設定頁測試連線四個區塊都能回訊息。

## 明日預告
Day 23 新增專案表單：主題／文稿、上傳、語言、風格、比例、Edge-TTS 聲音試聽、BGM。
