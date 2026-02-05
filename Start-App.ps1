<#
.SYNOPSIS
    Start the Exchange MCP Application

.DESCRIPTION
    Launches the Exchange MCP backend server with the web-based chat interface.

.PARAMETER Mode
    Run mode: 'full' (default), 'backend', or 'dev'

.PARAMETER Model
    Ollama model to use (default: llama3.2)

.PARAMETER Port
    Port to run the server on (default: 8000)

.PARAMETER SyncInterval
    Minutes between automatic data syncs (default: 5)

.PARAMETER SkipChecks
    Skip Ollama and data file checks (faster startup)

.EXAMPLE
    .\Start-App.ps1
    
.EXAMPLE
    .\Start-App.ps1 -Mode backend

.EXAMPLE
    .\Start-App.ps1 -Mode dev -Port 8080
#>

param(
    [ValidateSet('full', 'backend', 'dev')]
    [string]$Mode = "full",
    [string]$Model = "llama3.2",
    [int]$Port = 8000,
    [int]$SyncInterval = 5,
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Exchange MCP Assistant - Mode: $Mode" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Virtual Environment
$venvPath = Join-Path $scriptDir ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "ERROR: Virtual environment not found at $venvPath" -ForegroundColor Red
    Write-Host "Run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
Write-Host "Activating virtual environment..." -ForegroundColor Gray
. $activateScript

# Pre-flight Checks
if (-not $SkipChecks) {
    # Use DATA_FILE env var if set, otherwise default
    $dataPath = if ($env:DATA_PATH) { $env:DATA_PATH } else { Join-Path $scriptDir "data" }
    $dataFile = if ($env:DATA_FILE) { $env:DATA_FILE } else { Join-Path $dataPath "exchange_mcp.json" }
    if (-not (Test-Path $dataFile)) {
        Write-Host "WARNING: Data file not found. Generating..." -ForegroundColor Yellow
        $generateScript = Join-Path $scriptDir "scripts\Generate-SingleUserData.ps1"
        if (Test-Path $generateScript) {
            & pwsh -File $generateScript
        } else {
            Write-Host "ERROR: Cannot find data generation script" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Data file found" -ForegroundColor Green
    }
    
    Write-Host "Checking Ollama..." -ForegroundColor Gray
    try {
        $ollamaCheck = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
        Write-Host "Ollama is running" -ForegroundColor Green
        
        $models = $ollamaCheck.models | ForEach-Object { $_.name }
        $modelFound = $models -contains $Model -or $models -contains "${Model}:latest"
        
        if (-not $modelFound) {
            Write-Host "Model '$Model' not found. Pulling..." -ForegroundColor Yellow
            ollama pull $Model
            if ($LASTEXITCODE -ne 0) {
                Write-Host "ERROR: Failed to pull model" -ForegroundColor Red
                exit 1
            }
        } else {
            Write-Host "Model '$Model' is available" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "ERROR: Ollama is not running!" -ForegroundColor Red
        Write-Host "Start with: ollama serve" -ForegroundColor Yellow
        exit 1
    }
}

# Environment Variables
$env:OLLAMA_MODEL = $Model
$env:PORT = $Port
$env:SYNC_INTERVAL_MINUTES = $SyncInterval
$env:HOST = "127.0.0.1"

# Set DATA_PATH if not already set (allows .env override)
if (-not $env:DATA_PATH) {
    $env:DATA_PATH = Join-Path $scriptDir "data"
}
if (-not $env:DATA_FILE) {
    $env:DATA_FILE = Join-Path $env:DATA_PATH "exchange_mcp.json"
}
if (-not $env:CHROMA_DB_PATH) {
    $env:CHROMA_DB_PATH = Join-Path $env:DATA_PATH "chroma_db"
}

if ($Mode -eq "dev") {
    $env:DEBUG = "true"
}

# Display Configuration
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  URL:    http://127.0.0.1:$Port"
Write-Host "  Model:  $Model"
Write-Host "  Sync:   Every $SyncInterval minutes"
Write-Host "  Debug:  $($Mode -eq 'dev')"
Write-Host ""

$url = "http://127.0.0.1:$Port"

# Start Server based on mode
if ($Mode -eq "full") {
    Write-Host "Opening browser at $url ..." -ForegroundColor Gray
    Start-Job -ScriptBlock {
        param($u)
        Start-Sleep -Seconds 3
        Start-Process $u
    } -ArgumentList $url | Out-Null
    
    Write-Host "Starting server... Press Ctrl+C to stop" -ForegroundColor Cyan
    Write-Host ""
    python -m backend.server
}
elseif ($Mode -eq "backend") {
    Write-Host "Starting backend server (API only)..." -ForegroundColor Cyan
    Write-Host "  API: $url/api/" -ForegroundColor Gray
    Write-Host "  Docs: $url/docs" -ForegroundColor Gray
    Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
    Write-Host ""
    python -m backend.server
}
elseif ($Mode -eq "dev") {
    Write-Host "Starting development server with auto-reload..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
    Write-Host ""
    
    Start-Job -ScriptBlock {
        param($u)
        Start-Sleep -Seconds 3
        Start-Process $u
    } -ArgumentList $url | Out-Null
    
    python -m uvicorn backend.server:app --host 127.0.0.1 --port $Port --reload
}
