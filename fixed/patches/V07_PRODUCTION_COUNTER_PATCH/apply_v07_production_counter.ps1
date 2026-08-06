param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = "E:\Nhan_dien_san_pham_V03"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PatchPython = Join-Path $ScriptDir "apply_patch.py"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$ProjectPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BackupRoot = Join-Path $ProjectRoot "fixed\backups"

if (-not (Test-Path $ProjectPython)) {
    Write-Host "[ERROR] Không tìm thấy Python trong .venv: $ProjectPython" -ForegroundColor Red
    exit 1
}

Write-Host "=== V07 PRODUCTION COUNTER PATCH ===" -ForegroundColor Cyan

& $ProjectPython $PatchPython $ProjectRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$MainFile = Join-Path $ProjectRoot "desktop_app\main_window.py"
$CounterFile = Join-Path $ProjectRoot "core\product_counter_service.py"
$CounterTest = Join-Path $ProjectRoot "scripts\test_product_counter_persistence.py"

Write-Host "Kiểm tra cú pháp..." -ForegroundColor Cyan
& $ProjectPython -m py_compile $MainFile $CounterFile $CounterTest

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Compile thất bại. Đang tự khôi phục backup..." -ForegroundColor Red

    $LatestBackup = Get-ChildItem $BackupRoot -Directory |
        Where-Object { $_.Name -like "v07_production_counter_*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($LatestBackup) {
        Copy-Item (Join-Path $LatestBackup.FullName "main_window.py") $MainFile -Force
        Copy-Item (Join-Path $LatestBackup.FullName "product_counter_service.py") $CounterFile -Force
        Copy-Item (Join-Path $LatestBackup.FullName "run_regression_tests.ps1") (Join-Path $ProjectRoot "run_regression_tests.ps1") -Force
        Copy-Item (Join-Path $LatestBackup.FullName ".gitignore") (Join-Path $ProjectRoot ".gitignore") -Force

        Write-Host "[OK] Đã khôi phục source từ backup." -ForegroundColor Yellow
    }

    exit $LASTEXITCODE
}

Write-Host "Khởi tạo bộ đếm sản xuất..." -ForegroundColor Cyan
Push-Location $ProjectRoot
try {
    & $ProjectPython -c "from core.color_repository import ColorRepository; from core.product_counter_service import ProductCounterService; r=ColorRepository(); c=ProductCounterService(r.color_keys()); print('[OK] COUNTERS:', c.snapshot())"
}
finally {
    Pop-Location
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Không khởi tạo được config/counters.json." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "V07 PATCH HOÀN TẤT." -ForegroundColor Green
