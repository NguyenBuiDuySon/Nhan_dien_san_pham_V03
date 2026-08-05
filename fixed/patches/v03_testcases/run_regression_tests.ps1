$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Không tìm thấy .venv\Scripts\python.exe"
}

Set-Location $ProjectRoot

Write-Host "=== PYTHON ===" -ForegroundColor Cyan
& $PythonExe --version

Write-Host ""
Write-Host "=== COMPILE ===" -ForegroundColor Cyan
& $PythonExe -m compileall -q core desktop_app scripts main.py

Write-Host ""
Write-Host "=== VISION REGRESSION ===" -ForegroundColor Cyan
& $PythonExe .\scripts\test_vision_core.py

Write-Host ""
Write-Host "=== SERIAL DISCONNECT REGRESSION ===" -ForegroundColor Cyan
& $PythonExe .\scripts\test_serial_disconnect.py

Write-Host ""
Write-Host "TỰ ĐỘNG TEST: PASS" -ForegroundColor Green
Write-Host "Tiếp theo chạy app và test thủ công theo PATCH_TESTCASE_FIXES.md" -ForegroundColor Yellow
