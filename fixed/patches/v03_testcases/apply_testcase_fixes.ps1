param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
$PatchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PayloadRoot = Join-Path $PatchRoot "patch_payload"

function Resolve-ProjectRoot {
    param([string]$Candidate)

    if ($Candidate -and (Test-Path (Join-Path $Candidate "main.py"))) {
        return (Resolve-Path $Candidate).Path
    }

    $Current = (Get-Location).Path

    if (Test-Path (Join-Path $Current "main.py")) {
        return $Current
    }

    $Parent = Split-Path -Parent $PatchRoot

    if (Test-Path (Join-Path $Parent "main.py")) {
        return $Parent
    }

    $InputPath = Read-Host "Nhập đường dẫn project có main.py"

    if (-not (Test-Path (Join-Path $InputPath "main.py"))) {
        throw "Không tìm thấy main.py tại: $InputPath"
    }

    return (Resolve-Path $InputPath).Path
}

$TargetRoot = Resolve-ProjectRoot $ProjectRoot
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path $TargetRoot "_patch_backups\testcase_fixes_$Timestamp"

Write-Host "Project: $TargetRoot" -ForegroundColor Cyan
Write-Host "Backup : $BackupRoot" -ForegroundColor Cyan

$Files = @(
    "core\vision_processor.py",
    "core\config_service.py",
    "core\serial_service.py",
    "core\camera_service.py",
    "desktop_app\main_window.py",
    "scripts\test_vision_core.py",
    "scripts\test_serial_disconnect.py"
)

foreach ($RelativePath in $Files) {
    $Source = Join-Path $PayloadRoot $RelativePath
    $Target = Join-Path $TargetRoot $RelativePath
    $Backup = Join-Path $BackupRoot $RelativePath

    if (-not (Test-Path $Source)) {
        throw "Patch thiếu file: $Source"
    }

    if (Test-Path $Target) {
        $BackupDir = Split-Path -Parent $Backup
        New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
        Copy-Item $Target $Backup -Force
    }

    $TargetDir = Split-Path -Parent $Target
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    Copy-Item $Source $Target -Force

    Write-Host "Đã cập nhật: $RelativePath" -ForegroundColor Green
}

Write-Host ""
Write-Host "PATCH HOÀN TẤT." -ForegroundColor Green
Write-Host "Config/colors.json và số liệu hiệu chỉnh màu KHÔNG bị ghi đè." -ForegroundColor Yellow
Write-Host "Chạy tiếp: .\run_regression_tests.ps1" -ForegroundColor Yellow
