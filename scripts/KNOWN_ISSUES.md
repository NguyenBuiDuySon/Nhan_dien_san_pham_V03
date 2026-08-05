# KNOWN ISSUES — HMI v0.1

## LOW — Log lặp khi bấm nút nhiều lần

Mô tả:

- Bấm nhiều lần các nút bảo trì như HÚT THỬ, NHẢ THỬ, VỀ GỐC, DỪNG TRỤC sẽ sinh nhiều log.
- Đây là hành vi hiện tại của HMI mock.

Trạng thái:

- Accepted for v0.1

Hướng xử lý sau:

- Khi gắn ESP32 thật, thêm trạng thái BUSY / DONE / ERROR.
- Chặn bấm lặp khi lệnh chưa hoàn tất.
- Có thể thêm command cooldown 200–500 ms.

---

## LOW — HSV preview chưa ổn định tuyệt đối

Mô tả:

- HSV có thể nhận nhầm khi ánh sáng thay đổi.
- Vùng nền/bóng đổ có thể lọt vào mask.

Trạng thái:

- Accepted for v0.1

Hướng xử lý sau:

- Làm vision_lab riêng.
- Thêm ROI.
- Thêm trackbar chỉnh HSV.
- Thêm contour filtering.
- Kết hợp YOLO + HSV.

---

## MEDIUM — Model YOLO chưa inference thật

Mô tả:

- App mới lưu đường dẫn model.
- Nút tải model hiện chỉ giả lập trạng thái sẵn sàng.

Trạng thái:

- Planned

Hướng xử lý sau:

- Tạo ModelService.
- Load `.pt` hoặc `.onnx`.
- Detect vật thể.
- Trả bbox, class, confidence.

---

## MEDIUM — Serial/ESP32 hiện đang mock

Mô tả:

- App có SerialService và mock COM.
- Chưa test với ESP32 thật.

Trạng thái:

- Planned

Hướng xử lý sau:

- Chốt protocol serial.
- Test gửi lệnh AUTO, PAUSE, RESUME, ESTOP, JOG, HOME.
- ESP32 phản hồi ACK / DONE / ERROR.

---

## HIGH — Chưa có homing/limit switch thật

Mô tả:

- Gantry hiện mới mô phỏng vị trí.
- Chưa đọc công tắc hành trình thật.
- Chưa có bảo vệ va chạm phần cứng.

Trạng thái:

- Planned for hardware phase

Hướng xử lý sau:

- Thiết kế limit switch X_MIN/X_MAX/Y_MIN/Y_MAX/Z_MIN/Z_MAX.
- Viết homing sequence.
- Chặn vượt hành trình bằng firmware.