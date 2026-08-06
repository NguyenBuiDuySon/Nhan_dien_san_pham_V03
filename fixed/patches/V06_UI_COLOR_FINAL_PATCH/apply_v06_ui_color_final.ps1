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
    Write-Host "[ERROR] Không tìm thấy .venv Python: $ProjectPython" -ForegroundColor Red
    exit 1
}

Write-Host "=== V06 UI + COLOR METADATA FINAL PATCH ===" -ForegroundColor Cyan

& $ProjectPython $PatchPython $ProjectRoot
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$MainFile = Join-Path $ProjectRoot "desktop_app\main_window.py"
$RepositoryFile = Join-Path $ProjectRoot "core\color_repository.py"

Write-Host "Kiểm tra cú pháp..." -ForegroundColor Cyan
& $ProjectPython -m py_compile $MainFile $RepositoryFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Compile thất bại. Đang tự khôi phục backup..." -ForegroundColor Red

    $LatestBackup = Get-ChildItem $BackupRoot -Directory |
        Where-Object { $_.Name -like "v06_ui_color_final_*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if ($LatestBackup) {
        Copy-Item (Join-Path $LatestBackup.FullName "main_window.py") $MainFile -Force
        Copy-Item (Join-Path $LatestBackup.FullName "color_repository.py") $RepositoryFile -Force

        $BackupColors = Join-Path $LatestBackup.FullName "colors.json"
        if (Test-Path $BackupColors) {
            Copy-Item $BackupColors (Join-Path $ProjectRoot "config\colors.json") -Force
        }

        Write-Host "[OK] Đã khôi phục source và colors.json." -ForegroundColor Yellow
    }

    exit $LASTEXITCODE
}

Write-Host "Sửa metadata colors.json..." -ForegroundColor Cyan
Push-Location $ProjectRoot
try {
    & $ProjectPython -c "from core.color_repository import ColorRepository; r=ColorRepository(); print('[OK] Colors:', ', '.join(r.color_keys()))"
}
finally {
    Pop-Location
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Không thể migrate colors.json." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "V06 PATCH HOÀN TẤT." -ForegroundColor Green
