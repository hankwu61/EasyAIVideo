#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "[EasyAIVideo] uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[EasyAIVideo] WARNING: ffmpeg not found on PATH. Rendering will fail until it is installed."
fi
if [ ! -f frontend/dist/index.html ]; then
  echo "[EasyAIVideo] Building frontend..."
  (cd frontend && npm install && npm run build)
fi

echo "[EasyAIVideo] Starting server on http://127.0.0.1:8000"
exec uv run easyaivideo --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
