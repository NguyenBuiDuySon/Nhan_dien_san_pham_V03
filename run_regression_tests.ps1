$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "=== COMPILE SOURCE ===" -ForegroundColor Cyan
& $PythonExe -m compileall -q core desktop_app scripts main.py

Write-Host "=== VISION CORE ===" -ForegroundColor Cyan
& $PythonExe .\scripts\test_vision_core.py

Write-Host "=== SERIAL DISCONNECT ===" -ForegroundColor Cyan
& $PythonExe .\scripts\test_serial_disconnect.py

Write-Host "Tất cả regression test đã pass." -ForegroundColor Green
