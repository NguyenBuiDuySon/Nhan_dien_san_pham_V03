$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Version = & py -3.13 --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Không tìm thấy Python 3.13 qua lệnh py -3.13." -ForegroundColor Red
    exit 1
}

Write-Host "Đang dùng: $Version" -ForegroundColor Cyan

if (Test-Path ".venv") {
    $Backup = ".venv_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Rename-Item ".venv" $Backup
    Write-Host "Đã đổi tên môi trường cũ thành $Backup" -ForegroundColor Yellow
}

& py -3.13 -m venv .venv
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r requirements.txt
& $PythonExe -c "import sys, PySide6, cv2, serial; print(sys.version); print('PySide6', PySide6.__version__); print('OpenCV', cv2.__version__)"

Write-Host "Thiết lập môi trường hoàn tất." -ForegroundColor Green
