$ErrorActionPreference = "Stop"

# Luôn chạy app bằng đúng Python trong .venv của project.
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$MainFile = Join-Path $ProjectRoot "main.py"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Chưa có .venv hợp lệ." -ForegroundColor Red
    Write-Host "Hãy chạy trước: .\setup_py31312.ps1" -ForegroundColor Yellow
    exit 1
}

Set-Location $ProjectRoot

Write-Host "Đang chạy bằng:" -ForegroundColor Cyan
& $PythonExe --version

& $PythonExe $MainFile
