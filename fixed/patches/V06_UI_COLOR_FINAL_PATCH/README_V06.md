# V06 UI + Color Metadata Final Patch

## Sửa bốn mục còn tồn tại

- Tăng vùng HSV Binary Mask nhưng giữ Camera là vùng chính.
- Bỏ chữ `TEST`, chỉ giữ tên màu.
- Làm nền các nút màu tối và dịu hơn.
- Sửa `ui_color` bị rơi về vàng sau thêm/sửa/xóa màu.

## File bị sửa

- `desktop_app/main_window.py`
- `core/color_repository.py`
- `config/colors.json` có thể được chuẩn hóa metadata

## Chạy trong Terminal VS Code

```powershell
cd E:\Nhan_dien_san_pham_V03

Get-ChildItem `
  ".\fixed\patches\V06_UI_COLOR_FINAL_PATCH\*.ps1" |
  Unblock-File

Set-ExecutionPolicy `
  -Scope Process `
  -ExecutionPolicy Bypass `
  -Force

& ".\fixed\patches\V06_UI_COLOR_FINAL_PATCH\apply_v06_ui_color_final.ps1" `
  -ProjectRoot "E:\Nhan_dien_san_pham_V03"
```

Sau đó:

```powershell
.\run_regression_tests.ps1
.\run_app.ps1
```

## Test tay cuối

1. Mask lớn hơn V05.
2. Ẩn/hiện Mask 5 lần, layout không đổi.
3. Nút chỉ còn tên màu.
4. Nút màu không còn chói.
5. Thêm màu mới: chữ thống kê phải đúng màu.
6. Sửa dải ĐỎ: chữ ĐỎ vẫn đỏ.
7. Đóng/mở app: màu chữ vẫn đúng.
8. Xóa màu mới: app không văng.

## Backup

```text
fixed/backups/v06_ui_color_final_YYYYMMDD_HHMMSS/
```
