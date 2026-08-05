$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Chưa tìm thấy Git trong PATH." -ForegroundColor Red
    exit 1
}

if (Test-Path ".git") {
    Write-Host "Repository Git đã tồn tại." -ForegroundColor Yellow
    git status --short
    exit 0
}

git init
git add .
git commit -m "baseline: vision app v03 clean with testcase fixes"

Write-Host "Đã tạo repository Git và commit baseline." -ForegroundColor Green
