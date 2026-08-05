# Rà soát trạng thái project ngày 2026-08-06

## Kết luận

File RAR người dùng gửi vẫn là source V02 trước khi áp patch V03. Script patch có ở thư mục gốc, nhưng `patch_payload` không còn ở đó và không có bằng chứng patch đã chạy thành công.

Bản clean này đã áp đồng bộ V03 lên đúng các file:

- `core/camera_service.py`
- `core/config_service.py`
- `core/serial_service.py`
- `core/vision_processor.py`
- `desktop_app/main_window.py`
- `scripts/test_vision_core.py`
- `scripts/test_serial_disconnect.py`

## Các lỗi được xử lý

1. Khóa Counter khi chưa lấy nền; thêm hysteresis phát hiện sản phẩm vào/rời vùng.
2. Ẩn/hiện toàn bộ panel Mask và khôi phục stretch layout.
3. Kiểm tra COM định kỳ và chuyển trạng thái mất kết nối khi rút ESP32.
4. Dừng camera có trạng thái `stopping`, bỏ frame trễ và tránh `QLabel.clear()` gây lỗi font.
5. `.vscode` ghim interpreter vào `.venv` của project; có script tạo môi trường Python 3.13.

## Dữ liệu được giữ nguyên

- `config/colors.json`
- `config/background_reference.png`
- ROI, camera, serial và các thông số hiện có trong `config/app_config.json`
