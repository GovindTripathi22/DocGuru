@echo off
title Exact Template Inheritance System
echo ================================================================
echo   Starting Exact Template Inheritance System (Local AI Engine)
echo ================================================================

:: 1. Start Ollama in background if needed
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] Ollama is already running.
) else (
    echo Starting Ollama...
    start /B "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    timeout /t 2 /nobreak >nul
)

:: 2. Start Backend in separate window
echo Starting Python Document Backend on port 8000...
start "Document Engine Backend (Port 8000)" cmd /k "python -m uvicorn backend.app.main:app --port 8000 --reload"

:: 3. Start Frontend & Open Browser
echo Starting Next.js UI on port 3000...
start http://localhost:3000
npm run dev
