param(
    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = "E:\Nhan_dien_san_pham_V03"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$BackupRoot = Join-Path $ProjectRoot "fixed\backups"

$LatestBackup = Get-ChildItem $BackupRoot -Directory |
    Where-Object { $_.Name -like "v07_production_counter_*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $LatestBackup) {
    Write-Host "[ERROR] Không tìm thấy backup V07." -ForegroundColor Red
    exit 1
}

Copy-Item (Join-Path $LatestBackup.FullName "main_window.py") (Join-Path $ProjectRoot "desktop_app\main_window.py") -Force
Copy-Item (Join-Path $LatestBackup.FullName "product_counter_service.py") (Join-Path $ProjectRoot "core\product_counter_service.py") -Force
Copy-Item (Join-Path $LatestBackup.FullName "run_regression_tests.ps1") (Join-Path $ProjectRoot "run_regression_tests.ps1") -Force
Copy-Item (Join-Path $LatestBackup.FullName ".gitignore") (Join-Path $ProjectRoot ".gitignore") -Force

$BackupCounterTest = Join-Path $LatestBackup.FullName "test_product_counter_persistence.py"
$ProjectCounterTest = Join-Path $ProjectRoot "scripts\test_product_counter_persistence.py"

if (Test-Path $BackupCounterTest) {
    Copy-Item $BackupCounterTest $ProjectCounterTest -Force
}
elseif (Test-Path $ProjectCounterTest) {
    Remove-Item $ProjectCounterTest -Force
}

$BackupCountersJson = Join-Path $LatestBackup.FullName "counters.json"
$ProjectCountersJson = Join-Path $ProjectRoot "config\counters.json"

if (Test-Path $BackupCountersJson) {
    Copy-Item $BackupCountersJson $ProjectCountersJson -Force
}

Write-Host "[OK] Đã rollback V07 từ: $($LatestBackup.FullName)" -ForegroundColor Green
