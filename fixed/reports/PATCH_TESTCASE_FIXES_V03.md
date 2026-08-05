# Patch v0.3 — Sửa các test case đã ghi nhận

Patch này **không ghi đè**:

- `config/colors.json`
- `config/background_reference.png`
- thông số HSV đã hiệu chỉnh
- số liệu test của người dùng

## Các lỗi đã sửa

### TC-01 — Nền bàn bị đếm thành sản phẩm màu

Trước đây, khi chưa lấy nền, HSV vẫn được phép đưa kết quả vào Stability và Counter.

Sau patch:

- `require_background = true` là mặc định.
- Chưa lấy nền: chỉ xem preview, Counter bị khóa.
- Nền trống: không tích lũy phiếu Stability.
- Dùng hysteresis hiện diện với hai ngưỡng vào/rời.
- YOLO sau này vẫn có thể xác nhận `PRODUCT` mà không phụ thuộc nền.

### TC-02 — Ẩn/hiện mask làm hỏng bố cục

Sau patch:

- Nút `ẨN MASK / HIỆN MASK` nằm ở thanh nút camera.
- Ẩn/hiện toàn bộ panel mask.
- Khôi phục lại stretch ratio camera/mask.
- Không còn mất nút khi panel mask bị ẩn.

### TC-03 — Rút ESP32 nhưng trạng thái vẫn xanh

Sau patch:

- App kiểm tra kết nối mỗi 750 ms.
- Kiểm tra tên COM còn tồn tại và driver còn phản hồi.
- Rút USB: chuyển đỏ `MẤT KẾT NỐI`.
- Mở lại nút quét COM/kết nối.
- Nếu AUTO đang chạy thì app tự chuyển PAUSED.
- Chọn COM thật sẽ mở COM thật, kể cả khi mock mode đang bật.
- Chỉ `MOCK_COM` mới là kết nối giả lập.

### TC-04 — Bấm TẮT CAMERA làm app thoát/QFont pointSize=-1

Sau patch:

- Camera có trạng thái `stopping`.
- Bỏ frame trễ sau khi bấm tắt.
- Dừng QThread bất đồng bộ, không chặn event loop.
- Không dùng `QLabel.clear()` khi reset preview.
- Chuẩn hóa QFont trước khi hiển thị thông báo.
- Nút chỉ bật lại sau khi camera release xong.

### TC-05 — VS Code tự chạy nhầm Python 3.14

Phần này được xử lý bởi cấu trúc project phẳng và `.venv` đặt tại root.

Luôn chạy:

```powershell
.\run_app.ps1
```

và chọn:

```text
.venv\Scripts\python.exe
```

## Chạy test tự động

Từ thư mục có `main.py`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\run_regression_tests.ps1
```

## Test thủ công sau patch

### A. Presence/Counter

1. Bật camera nhưng chưa lấy nền.
2. Đặt vật hoặc để bàn màu trong Sample Box.
3. Kết quả phải báo `CHƯA LẤY NỀN`; bộ đếm không tăng.
4. Để vùng trống và bấm `LẤY NỀN`.
5. Để trống 10 giây: bộ đếm không tăng.
6. Đặt một vật: đếm đúng một lần.
7. Giữ vật 10 giây: không tăng lại.
8. Lấy vật ra rồi đặt vật mới: được phép đếm tiếp.

### B. Mask layout

1. Nhấn `ẨN MASK`.
2. Camera giãn đúng vùng giữa.
3. Nút đổi thành `HIỆN MASK`.
4. Nhấn lại: panel mask trở lại đúng tỷ lệ.

### C. ESP32

1. Quét COM và kết nối COM thật.
2. Trạng thái xanh.
3. Rút USB.
4. Trong tối đa khoảng 1 giây, trạng thái phải chuyển đỏ.
5. Nút quét COM và kết nối phải hoạt động lại.

### D. Camera lifecycle

1. Bật camera.
2. Nhấn `TẮT CAMERA`.
3. App không thoát.
4. Chờ nút trở lại `BẬT CAMERA`.
5. Bật lại camera lần nữa.
6. Lặp 5 lần.
