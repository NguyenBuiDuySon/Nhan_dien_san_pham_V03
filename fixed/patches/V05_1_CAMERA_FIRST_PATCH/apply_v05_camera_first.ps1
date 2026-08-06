param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = "E:\Nhan_dien_san_pham_V03"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PatchPython = Join-Path $ScriptDir "apply_patch.py"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PatchPython)) {
    Write-Host "[ERROR] Không tìm thấy apply_patch.py" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $ProjectPython)) {
    Write-Host "[ERROR] Không tìm thấy Python trong .venv: $ProjectPython" -ForegroundColor Red
    exit 1
}

Write-Host "=== V05 CAMERA-FIRST LAYOUT ===" -ForegroundColor Cyan
& $ProjectPython $PatchPython $ProjectRoot

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$MainFile = Join-Path $ProjectRoot "desktop_app\main_window.py"

Write-Host "Kiểm tra cú pháp..." -ForegroundColor Cyan
& $ProjectPython -m py_compile $MainFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Compile thất bại. Đang tự khôi phục file backup..." -ForegroundColor Red
    $LatestBackup = Get-ChildItem (Join-Path $ProjectRoot "fixed\backups") -Directory |
        Where-Object { $_.Name -like "v05_camera_first_*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($LatestBackup) {
        Copy-Item (Join-Path $LatestBackup.FullName "main_window.py") $MainFile -Force
        Write-Host "[OK] Đã khôi phục main_window.py từ backup." -ForegroundColor Yellow
    }
    exit $LASTEXITCODE
}

Write-Host "V05 CAMERA-FIRST PATCH HOÀN TẤT." -ForegroundColor Green
