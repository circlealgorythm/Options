# Environment initialization, dependency installation, and verification (PowerShell)

$PythonPath = "C:\Users\circlealgorythm\AppData\Local\Programs\Python\Python311\python.exe"
$InstallCmd = "$PythonPath -m pip install -r requirements.txt"
$VerifyCmd = "$PythonPath -m pytest tests/"
$StartCmd = "$PythonPath main.py"

Write-Host "=== 1. Check Working Directory ===" -ForegroundColor Cyan
Write-Host "Current path: $pwd"

Write-Host "`n=== 2. Install Dependencies ===" -ForegroundColor Cyan
Invoke-Expression $InstallCmd

Write-Host "`n=== 3. Run Verification ===" -ForegroundColor Cyan
Invoke-Expression $VerifyCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== Verification Successful! ===" -ForegroundColor Green
    Write-Host "To start the pipeline, run: $StartCmd" -ForegroundColor Yellow
} else {
    Write-Host "`n!!! Verification Failed. Please fix failing tests before starting work. !!!" -ForegroundColor Red
}
