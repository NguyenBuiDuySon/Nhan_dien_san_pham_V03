# V07 — Production Counter

## Nội dung

- Xóa toàn bộ nút cộng đếm thủ công.
- Đổi `THỐNG KÊ SẢN PHẨM` thành `BỘ ĐẾM SẢN XUẤT`.
- Chỉ giữ nút `RESET BỘ ĐẾM`.
- RESET có hộp xác nhận.
- Tự lưu số đếm vào `config/counters.json`.
- Mở lại app sẽ đọc lại số đếm cũ.
- Tự lưu sau khi tăng, reset, CRUD màu và đóng app.
- Thêm regression test cho lưu bộ đếm.
- Đưa `counters.json` vào `.gitignore`.

## Cài patch trong Terminal VS Code

Đóng app trước.

```powershell
cd E:\Nhan_dien_san_pham_V03

Get-ChildItem `
  ".\fixed\patches\V07_PRODUCTION_COUNTER_PATCH\*.ps1" |
  Unblock-File

Set-ExecutionPolicy `
  -Scope Process `
  -ExecutionPolicy Bypass `
  -Force

& ".\fixed\patches\V07_PRODUCTION_COUNTER_PATCH\apply_v07_production_counter.ps1" `
  -ProjectRoot "E:\Nhan_dien_san_pham_V03"
```

Sau khi hiện `V07 PATCH HOÀN TẤT`:

```powershell
.\run_regression_tests.ps1
.\run_app.ps1
```

## Test tay

1. Không còn các nút màu dùng để cộng thử.
2. Đếm ĐỎ = 2 và XANH DƯƠNG = 3.
3. Đóng app rồi mở lại.
4. ĐỎ vẫn bằng 2 và XANH DƯƠNG vẫn bằng 3.
5. Bấm RESET, chọn `No`: số không đổi.
6. Bấm RESET, chọn `Yes`: toàn bộ về 0.
7. Đóng/mở app: vẫn giữ 0.

## Rollback

```powershell
& ".\fixed\patches\V07_PRODUCTION_COUNTER_PATCH\rollback_v07_production_counter.ps1" `
  -ProjectRoot "E:\Nhan_dien_san_pham_V03"
```
