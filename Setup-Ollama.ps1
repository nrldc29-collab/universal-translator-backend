# Setup-Ollama.ps1
# Downloads and installs Ollama, starts the service, pulls mistral model, and configures .env

$ErrorActionPreference = "Stop"

Write-Host "=== Ollama Setup Script ===" -ForegroundColor Cyan

# Check if Ollama is already installed
$ollamaPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (Test-Path $ollamaPath) {
    Write-Host "Ollama already installed at: $ollamaPath" -ForegroundColor Green
} else {
    Write-Host "Ollama not found. Downloading installer..." -ForegroundColor Yellow
    
    # Download Ollama installer
    $installerUrl = "https://ollama.com/download/OllamaSetup.exe"
    $installerPath = "$env:TEMP\OllamaSetup.exe"
    
    Write-Host "Downloading from $installerUrl..."
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    
    Write-Host "Installing Ollama silently..."
    Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait
    
    # Wait for installation to complete
    Start-Sleep -Seconds 5
    
    if (Test-Path $ollamaPath) {
        Write-Host "Ollama installed successfully" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Ollama installation failed" -ForegroundColor Red
        exit 1
    }
    
    # Cleanup installer
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
}

# Start Ollama service
Write-Host "Starting Ollama service..." -ForegroundColor Yellow
Start-Process -FilePath $ollamaPath -ArgumentList "serve" -WindowStyle Hidden

# Wait for Ollama to be ready
Write-Host "Waiting for Ollama service to start..."
$maxAttempts = 30
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts -and -not $ready) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ready = $true
            Write-Host "Ollama service is ready" -ForegroundColor Green
        }
    } catch {
        $attempt++
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "ERROR: Ollama service failed to start" -ForegroundColor Red
    exit 1
}

# Pull mistral model
Write-Host "Pulling mistral model (this may take a while, ~4GB)..." -ForegroundColor Yellow
$pullProcess = Start-Process -FilePath $ollamaPath -ArgumentList "pull", "mistral" -NoNewWindow -PassThru -Wait

if ($pullProcess.ExitCode -eq 0) {
    Write-Host "Mistral model pulled successfully" -ForegroundColor Green
} else {
    Write-Host "WARNING: Mistral model pull failed with exit code $($pullProcess.ExitCode)" -ForegroundColor Yellow
}

# Verify model is available
Write-Host "Verifying mistral model..."
try {
    $models = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing | ConvertFrom-Json
    $hasMistral = $models.models | Where-Object { $_.name -like "mistral*" }
    if ($hasMistral) {
        Write-Host "Mistral model is available" -ForegroundColor Green
    } else {
        Write-Host "WARNING: Mistral model not found in available models" -ForegroundColor Yellow
    }
} catch {
    Write-Host "WARNING: Could not verify mistral model" -ForegroundColor Yellow
}

# Configure .env
$envPath = ".env"
if (Test-Path $envPath) {
    Write-Host "Updating .env file..." -ForegroundColor Yellow
    $envContent = Get-Content $envPath -Raw
    
    if ($envContent -match "OLLAMA_ENABLED\s*=") {
        $envContent = $envContent -replace "OLLAMA_ENABLED\s*=.*", "OLLAMA_ENABLED=true"
    } else {
        $envContent += "`nOLLAMA_ENABLED=true"
    }
    
    Set-Content -Path $envPath -Value $envContent -NoNewline
    Write-Host "Set OLLAMA_ENABLED=true in .env" -ForegroundColor Green
} else {
    Write-Host "WARNING: .env file not found. Creating it..." -ForegroundColor Yellow
    Set-Content -Path $envPath -Value "OLLAMA_ENABLED=true"
    Write-Host "Created .env with OLLAMA_ENABLED=true" -ForegroundColor Green
}

Write-Host "=== Ollama Setup Complete ===" -ForegroundColor Cyan
Write-Host "Ollama is running at http://localhost:11434" -ForegroundColor Green
Write-Host "You can now restart the backend with: python backend/app.py" -ForegroundColor Green
