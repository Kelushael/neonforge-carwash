# CARWASH installer — Windows PowerShell
# Run: irm https://raw.githubusercontent.com/Kelushael/neonforge-carwash/master/install.ps1 | iex

Write-Host ""
Write-Host "◈ CARWASH installer" -ForegroundColor Green
Write-Host ""

# winget
$deps = @("Python.Python.3.11", "Gyan.FFmpeg")
foreach ($d in $deps) {
    Write-Host "installing $d..."
    winget install --id $d -e --accept-source-agreements --accept-package-agreements -h
}

# clone
if (-not (Test-Path "neonforge-carwash")) {
    git clone https://github.com/Kelushael/neonforge-carwash.git
}
Set-Location neonforge-carwash

# venv
python -m venv env
.\env\Scripts\Activate.ps1
pip install -q -r requirements.txt

Write-Host ""
Write-Host "✓ done" -ForegroundColor Green
Write-Host ""
Write-Host "  start server:"
Write-Host "  cd neonforge-carwash; .\env\Scripts\Activate.ps1; python server.py"
Write-Host ""
Write-Host "  then open: http://localhost:8888"
Write-Host ""
