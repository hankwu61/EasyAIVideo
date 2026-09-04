# Day 22｜前端骨架：React + Vite + Tailwind 與型別安全的 API client

> 30 天打造 AI 短影片生成平台 — 第 22 天

## 今日目標
- 建立 `frontend/`：Vite + React + TypeScript + Tailwind。
- 寫一個薄的 API client，型別來自昨天的 `types.ts`。
- 完成版面骨架：側欄專案列表、主區域、設定頁入口，繁中／英文切換。

## 建立專案

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install react-router-dom @tanstack/react-query zustand lucide-react
```

`vite.config.ts`：

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8000", "/data": "http://127.0.0.1:8000" } },
  build: { outDir: "dist" },
});
```

開發時 `npm run dev` 走 5173 埠並代理到後端；正式時 `npm run build` 產出 `dist/`，由 FastAPI 掛載：

```python
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

（放在所有 `/api` 路由之後，並加一個 SPA fallback 讓 `/projects/xxx` 直接重新整理也能開。）

## API client

`src/api/client.ts`：

```ts
import type { paths, components } from "./types";

export type Project = components["schemas"]["Project"];
export type Scene = components["schemas"]["Scene"];
export type Task = components["schemas"]["Task"];

export class ApiError extends Error {
  constructor(public status: number, public error: string, public detail?: string) { super(detail ?? error); }
}

async function req<T>(method: string, url: string, body?: unknown, isForm = false): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: isForm ? undefined : { "Content-Type": "application/json" },
    body: isForm ? (body as FormData) : body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, e.error, e.detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  projects: {
    list: () => req<Project[]>("GET", "/api/projects"),
    get: (id: string) => req<Project>("GET", `/api/projects/${id}`),
    create: (b: components["schemas"]["ProjectCreate"]) => req<Project>("POST", "/api/projects", b),
    remove: (id: string) => req<void>("DELETE", `/api/projects/${id}`),
    generate: (id: string) => req<{ task: Task }>("POST", `/api/projects/${id}/generate`),
    assets: (id: string) => req<{ task: Task }>("POST", `/api/projects/${id}/assets`),
    render: (id: string) => req<{ task: Task }>("POST", `/api/projects/${id}/render`),
  },
  scenes: {
    update: (pid: string, sid: string, b: components["schemas"]["SceneUpdate"]) =>
      req<Project>("PATCH", `/api/projects/${pid}/scenes/${sid}`, b),
    regenImage: (pid: string, sid: string) => req<{ task: Task }>("POST", `/api/projects/${pid}/scenes/${sid}/image`),
  },
  tasks: {
    get: (id: string) => req<Task>("GET", `/api/tasks/${id}`),
    cancel: (id: string) => req<Task>("POST", `/api/tasks/${id}/cancel`),
  },
  presets: () => req<components["schemas"]["Presets"]>("GET", "/api/presets"),
  settings: { get: () => req("GET", "/api/settings"), patch: (b: unknown) => req("PATCH", "/api/settings", b) },
};
```

## React Query 與版面

```tsx
// src/App.tsx
<QueryClientProvider client={qc}>
  <BrowserRouter>
    <div className="flex h-screen bg-neutral-950 text-neutral-100">
      <Sidebar />                          {/* 專案列表、新增、設定 */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/projects/new" element={<NewProject />} />
          <Route path="/projects/:id" element={<Workbench />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  </BrowserRouter>
</QueryClientProvider>
```

`useQuery({ queryKey: ["projects"], queryFn: api.projects.list })` 讓側欄自動更新；任務完成後 `invalidateQueries(["project", id])`。

## i18n

不用重型套件，一個 `src/i18n.ts`：

```ts
const dict = {
  "zh-TW": { newProject: "新增專案", generate: "建立並開始生成", workbench: "工作台", ... },
  en: { newProject: "New project", generate: "Create & generate", workbench: "Workbench", ... },
};
export const useT = () => { const lang = useUI(s => s.lang); return (k: keyof typeof dict["zh-TW"]) => dict[lang][k]; };
```

語言存 `localStorage`，用 zustand 的 `useUI` store。

## 用 Antigravity 的瀏覽器代理驗證

Antigravity 可以自己開瀏覽器、點擊、截圖。今天開始每個前端任務都要求它「用瀏覽器打開 http://localhost:5173，操作一遍並截圖」，你只看截圖與 console 錯誤。

## 給 Antigravity 的提示詞
```
在 frontend/ 建立 Vite React TS + Tailwind 專案，設定 /api 與 /data 代理，建立 src/api/client.ts（型別來自 types.ts、ApiError）、
React Query provider、路由骨架（Home/NewProject/Workbench/Settings）、Sidebar 專案列表、zh-TW/en 切換。
後端加上 dist 掛載與 SPA fallback。啟動 dev server，用瀏覽器打開並截圖側欄與空的首頁給我。
```

## 今日檢查清單
- [ ] `npm run dev` 開啟後側欄列出後端專案。
- [ ] `npm run build` 後 `uv run easyaivideo` 在 8000 埠能直接看到前端。
- [ ] 後端改一個欄位名，`npm run build` 會報型別錯誤。

## 明日預告
Day 23 新增專案表單：主題或文稿、語言、風格、比例、聲音試聽、BGM 試聽、鏡頭動態，一鍵建立並開始生成。
