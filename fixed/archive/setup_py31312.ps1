$ErrorActionPreference = "Stop"

# Script này phải nằm ngang hàng với main.py.
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== THIẾT LẬP MÔI TRƯỜNG PYTHON 3.13.12 ===" -ForegroundColor Cyan

# Kiểm tra Python Launcher và Python 3.13.
try {
    $PythonVersion = & py -3.13 --version 2>&1
}
catch {
    Write-Host "Không tìm thấy Python 3.13 qua lệnh: py -3.13" -ForegroundColor Red
    Write-Host "Hãy cài/chọn Python 3.13.12 rồi chạy lại script." -ForegroundColor Yellow
    exit 1
}

Write-Host "Đã tìm thấy: $PythonVersion" -ForegroundColor Green

# Không dùng lại .venv sai phiên bản. Đổi tên để vẫn có thể khôi phục.
if (Test-Path ".venv") {
    $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $BackupName = ".venv_backup_$Timestamp"
    Write-Host "Đổi tên .venv cũ thành $BackupName" -ForegroundColor Yellow
    Rename-Item ".venv" $BackupName
}

Write-Host "Đang tạo .venv bằng Python 3.13..." -ForegroundColor Cyan
& py -3.13 -m venv .venv

$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "Đang nâng cấp pip..." -ForegroundColor Cyan
& $PythonExe -m pip install --upgrade pip

Write-Host "Đang cài thư viện từ requirements.txt..." -ForegroundColor Cyan
& $PythonExe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Python đang dùng:" -ForegroundColor Cyan
& $PythonExe --version

Write-Host "Kiểm tra PySide6..." -ForegroundColor Cyan
& $PythonExe -c "import PySide6; print('PySide6 OK:', PySide6.__version__)"

Write-Host ""
Write-Host "THIẾT LẬP HOÀN TẤT." -ForegroundColor Green
Write-Host "Trong VS Code: Ctrl+Shift+P -> Python: Select Interpreter -> chọn .venv\Scripts\python.exe" -ForegroundColor Yellow
Write-Host "Chạy app bằng: .\run_app.ps1" -ForegroundColor Yellow
