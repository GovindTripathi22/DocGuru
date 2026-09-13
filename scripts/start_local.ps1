# Windows PowerShell 1-Click Launch Script
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Starting Exact Template Inheritance System (Local AI Engine)  " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# 1. Start Ollama if not running
$ollamaRunning = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if (-not $ollamaRunning) {
    Write-Host ">> Starting Ollama local LLM server..." -ForegroundColor Yellow
    Start-Process -FilePath "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 2
} else {
    Write-Host "[OK] Ollama is already running on port 11434" -ForegroundColor Green
}

# 2. Start FastAPI Python Backend in background
Write-Host ">> Starting FastAPI Document Engine on port 8000..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--port", "8000", "--reload" -PassThru

# 3. Start Next.js Frontend
Write-Host ">> Starting Next.js Frontend on port 3000..." -ForegroundColor Yellow
Start-Process "http://localhost:3000"
npm run dev
