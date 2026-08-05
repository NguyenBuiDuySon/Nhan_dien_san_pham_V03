# TEST RESULT — HMI v0.1

Ngày test: 04/08/2026  
Người test: Nguyễn Bùi Duy Sơn  
Phiên bản: HMI v0.1  

---

## 1. Kết quả tổng quan

| Nhóm test | Kết quả | Ghi chú |
|---|---|---|
| Smoke test | PASS | Import, config, counter, camera source OK |
| Khởi động app | PASS | App mở ổn, không lỗi import |
| Camera | PASS | Source 0 chạy ổn |
| Camera source sai | PASS/WARN | Source 1 không khả dụng, app không crash |
| HSV preview | PASS | Mask và label màu hoạt động mức demo |
| Bộ đếm sản phẩm | PASS | Test đỏ/lá/xanh/lỗi tăng đúng |
| Chế độ bảo trì | PASS | Jog mock, home, hút/nhả hoạt động |
| AUTO / PAUSE / ESTOP / RESET | PASS | Phản hồi log và state đúng |
| ESP32 mock | PASS | Mock serial hoạt động |
| Health check | PASS | Check camera, serial, model, counter, gantry |
| Đóng app | PASS | Không còn lỗi QThread chính |

---

## 2. Kết luận

App đạt mức demo HMI v0.1.

Có thể tạm khóa app để chuyển sang:

- Nhận diện riêng
- ESP32 động lực
- Mạch điện
- PCB
- Test phần cứng

---

## 3. Ghi chú

HSV hiện chỉ là preview cơ bản, chưa phải nhận diện chính thức.

Model YOLO hiện mới lưu path và giả lập trạng thái sẵn sàng, chưa inference thật.

Các lệnh gantry hiện đang mock/logic giao diện, chưa điều khiển driver thật.