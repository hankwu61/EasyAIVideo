"""FastAPI application entry point."""

from __future__ import annotations

import argparse
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import FRONTEND_DIST, ensure_dirs
from .db import db
from .deps import task_queue
from .routers import config as config_router
from .routers import files, projects, resources, tasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("easyaivideo")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_dirs()
    await db.init()
    await task_queue.start()
    log.info("EasyAIVideo %s ready", __version__)
    try:
        yield
    finally:
        await task_queue.stop()
        await db.close()


app = FastAPI(title="EasyAIVideo", version=__version__, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (config_router.router, resources.router, projects.router, tasks.router, files.router):
    app.include_router(r)


@app.get("/api", include_in_schema=False)
async def api_root() -> JSONResponse:
    return JSONResponse({"service": "EasyAIVideo", "version": __version__, "docs": "/docs"})


if (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        candidate = FRONTEND_DIST / path
        if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.resolve().parents:
            return FileResponse(candidate)
        if "." in path.rsplit("/", 1)[-1]:  # looks like a static file that does not exist
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        return FileResponse(FRONTEND_DIST / "index.html")

else:

    @app.get("/", include_in_schema=False)
    async def no_frontend() -> JSONResponse:
        return JSONResponse({"message": "Frontend not built. Run `npm run build` in frontend/, or use the API at /docs."})


def run() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="EasyAIVideo server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("easyaivideo.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    run()
