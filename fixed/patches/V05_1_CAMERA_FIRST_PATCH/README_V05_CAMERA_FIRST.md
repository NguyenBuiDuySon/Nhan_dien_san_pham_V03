# V05.1 Camera-first Layout — đã sửa lỗi chuỗi xuống dòng

## Mục tiêu

- Camera View luôn là vùng hiển thị chính.
- Mask chỉ là panel phụ thấp, khoảng 190–220 px.
- Khi cửa sổ được phóng lớn, phần tăng thêm thuộc về Camera View.
- Bấm `ẨN MASK` hoặc `HIỆN MASK` không thay đổi kích thước các panel.
- Khi ẩn, vùng mask vẫn giữ nguyên vị trí và chỉ hiện thông báo `ĐÃ ẨN HIỂN THỊ`.
- Không thay đổi cấu hình HSV, ROI, bộ đếm, camera hoặc ESP32.

## Cách đặt thư mục

Chép nguyên thư mục `V05_CAMERA_FIRST_PATCH` vào:

```text
E:\Nhan_dien_san_pham_V03\fixed\patches\
```

## Chạy trong Terminal VS Code

Đóng app trước rồi chạy:

```powershell
cd E:\Nhan_dien_san_pham_V03

Get-ChildItem .\fixed\patches\V05_CAMERA_FIRST_PATCH\*.ps1 | Unblock-File
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

& ".\fixed\patches\V05_CAMERA_FIRST_PATCH\apply_v05_camera_first.ps1" `
    -ProjectRoot "E:\Nhan_dien_san_pham_V03"
```

Sau đó:

```powershell
.\run_regression_tests.ps1
.\run_app.ps1
```

## Test giao diện

1. Bật camera.
2. Quan sát Camera View phải lớn hơn Mask rõ rệt.
3. Bấm ẨN/HỆN MASK 5 lần.
4. Kích thước Camera View, cột trái và cột phải không được thay đổi.
5. Mask hiện lại phải tiếp tục cập nhật ảnh nhị phân.

## Rollback

Patch tự sao lưu vào:

```text
fixed\backups\v05_camera_first_YYYYMMDD_HHMMSS\
```


## Sửa trong V05.1

- Sửa lỗi `SyntaxError: unterminated string literal` khi chèn chuỗi `MASK VIEW\n\n...`.
- Nếu compile thất bại, script tự khôi phục `main_window.py` từ backup mới nhất.
