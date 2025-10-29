# Setup script for ml_service (Windows PowerShell)
# Usage (from ml_service folder):
#   .\setup_env.ps1

param(
    [string]$venvDir = ".venv",
    [switch]$InstallAll = $true
)

Write-Host "Creating virtual environment in: $venvDir" -ForegroundColor Cyan
python -m venv $venvDir

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
# Activate the virtualenv in this script (affects current PowerShell session)
. "$PSScriptRoot\$venvDir\Scripts\Activate.ps1"

Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

if ($InstallAll) {
    Write-Host "Installing ml_service requirements (from ml_service\requirements.txt)..." -ForegroundColor Cyan
    pip install -r "$PSScriptRoot\requirements.txt"
} else {
    Write-Host "Installing minimal deps: flask-cors, PyPDF2, nltk" -ForegroundColor Cyan
    pip install flask-cors PyPDF2 nltk
}

# Download NLTK tokenizers if nltk is installed
Write-Host "Downloading common NLTK data (punkt) if nltk is available..." -ForegroundColor Cyan
$nltkScript = @"
import importlib
try:
    import nltk
    nltk.download('punkt')
    print('NLTK punkt downloaded')
except Exception as e:
    print('NLTK not available or download failed:', e)
"@

$nltkPath = Join-Path $PSScriptRoot '_nltk_download.py'
Set-Content -Path $nltkPath -Value $nltkScript -Encoding UTF8
python $nltkPath
Remove-Item $nltkPath -Force

Write-Host "Setup complete. To activate the virtualenv in this shell run:`n.\$venvDir\Scripts\Activate.ps1`" -ForegroundColor Green
Write-Host "Then run: python app.py  (or: python -m ml_service.app from repo root)" -ForegroundColor Green
