# QuickScope Interview Bot - Setup Script (PowerShell)
# Run this to set up your development environment

Write-Host "=== QuickScope Interview Bot Setup ===" -ForegroundColor Cyan

# Check Python version
Write-Host "`nChecking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Please install Python 3.11+." -ForegroundColor Red
    exit 1
}
Write-Host "Found: $pythonVersion" -ForegroundColor Green

# Check if Poetry is installed
Write-Host "`nChecking for Poetry..." -ForegroundColor Yellow
$poetryVersion = poetry --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Found: $poetryVersion" -ForegroundColor Green
    Write-Host "`nInstalling dependencies with Poetry..." -ForegroundColor Yellow
    poetry install
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Dependencies installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Failed to install dependencies." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Poetry not found. Using pip instead..." -ForegroundColor Yellow
    
    # Create virtual environment
    Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    
    # Activate virtual environment
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    .\venv\Scripts\Activate.ps1
    
    # Install dependencies
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install --upgrade pip
    pip install langgraph langchain-core langchain-openai pydantic pydantic-settings python-dotenv pytest pytest-asyncio pytest-mock black ruff
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Dependencies installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "ERROR: Failed to install dependencies." -ForegroundColor Red
        exit 1
    }
}

# Check for .env file
Write-Host "`nChecking for .env file..." -ForegroundColor Yellow
if (Test-Path .env) {
    Write-Host ".env file found." -ForegroundColor Green
} else {
    Write-Host ".env file not found. Creating from template..." -ForegroundColor Yellow
    Copy-Item env.example .env
    Write-Host "IMPORTANT: Edit .env and add your OPENAI_API_KEY!" -ForegroundColor Red
}

# Verify flows directory
Write-Host "`nVerifying flows directory..." -ForegroundColor Yellow
if (Test-Path flows) {
    $flowCount = (Get-ChildItem flows -Filter "*.json").Count
    Write-Host "Found $flowCount flow definition(s)" -ForegroundColor Green
} else {
    Write-Host "WARNING: flows directory not found!" -ForegroundColor Red
}

Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env and add your OPENAI_API_KEY" -ForegroundColor White
Write-Host "2. Run: poetry run quickscope (or: python -m src.cli)" -ForegroundColor White
Write-Host "3. Optional: Run: langgraph dev (Studio UI)" -ForegroundColor White
Write-Host "`nTo run tests: pytest" -ForegroundColor Cyan
Write-Host "To format code: black src tests" -ForegroundColor Cyan
Write-Host "To lint: ruff src tests" -ForegroundColor Cyan
