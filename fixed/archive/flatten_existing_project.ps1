$ErrorActionPreference = "Stop"

# Dùng khi project đang có dạng:
# Nhan_dien_san_pham_V02\
#   .venv\
#   Nhan_dien_san_pham\
#       main.py
#       config\
#       core\
#       ...

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Child = Join-Path $Root "Nhan_dien_san_pham"

Set-Location $Root

if (-not (Test-Path $Child)) {
    Write-Host "Không thấy thư mục con: $Child" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $Child "main.py"))) {
    Write-Host "Thư mục con không chứa main.py. Dừng để tránh di chuyển nhầm." -ForegroundColor Red
    exit 1
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $Root "backup_before_flatten_$Timestamp"

Write-Host "Sao lưu thư mục con vào: $Backup" -ForegroundColor Cyan
Copy-Item $Child $Backup -Recurse

# .vscode ở thư mục cha có thể đang ghim Python 3.14.
if (Test-Path (Join-Path $Root ".vscode")) {
    $OldVscode = Join-Path $Root ".vscode_old_$Timestamp"
    Write-Host "Đổi tên .vscode cũ thành: $OldVscode" -ForegroundColor Yellow
    Rename-Item (Join-Path $Root ".vscode") $OldVscode
}

Write-Host "Di chuyển nội dung project ra thư mục cha..." -ForegroundColor Cyan

Get-ChildItem -LiteralPath $Child -Force | ForEach-Object {
    $Destination = Join-Path $Root $_.Name

    if (Test-Path $Destination) {
        Write-Host "Bỏ qua vì đã tồn tại: $($_.Name)" -ForegroundColor Yellow
    }
    else {
        Move-Item -LiteralPath $_.FullName -Destination $Root
    }
}

# Chỉ xóa thư mục con nếu đã rỗng.
if (-not (Get-ChildItem -LiteralPath $Child -Force)) {
    Remove-Item $Child
    Write-Host "Đã xóa thư mục con rỗng." -ForegroundColor Green
}
else {
    Write-Host "Thư mục con vẫn còn file trùng tên. Kiểm tra thủ công: $Child" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "ĐÃ LÀM PHẲNG CẤU TRÚC PROJECT." -ForegroundColor Green
Write-Host "Bước tiếp theo: chạy .\setup_py31312.ps1" -ForegroundColor Yellow
