@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo [EasyAIVideo] uv not found. Install it from https://docs.astral.sh/uv/ or run: pip install uv
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [EasyAIVideo] WARNING: ffmpeg not found on PATH. Rendering will fail until it is installed.
)

if not exist "frontend\dist\index.html" (
  echo [EasyAIVideo] Building frontend...
  pushd frontend
  call npm install
  call npm run build
  popd
)

echo [EasyAIVideo] Starting server on http://127.0.0.1:8000
uv run easyaivideo --host 127.0.0.1 --port 8000
