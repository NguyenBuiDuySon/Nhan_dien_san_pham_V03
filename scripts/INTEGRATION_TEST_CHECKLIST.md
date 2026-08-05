# Checklist test Vision tích hợp

## 1. Khởi động

- [ ] Chạy `python main.py` không lỗi import.
- [ ] App mở đủ ba cột giao diện.
- [ ] Camera source đúng với Phone Link.

## 2. Camera và ROI

- [ ] Bấm **BẬT CAMERA**, thấy ảnh trong app.
- [ ] Kéo chuột trên Camera View, ROI đổi theo thao tác.
- [ ] Đóng/mở app, ROI vẫn được lưu.
- [ ] Sau khi đổi ROI, log nhắc lấy nền lại.

## 3. Nền và nhận màu

- [ ] Để vùng SAMPLE trống rồi bấm **LẤY NỀN**.
- [ ] Nền trống hiển thị `CHƯA CÓ SẢN PHẨM`.
- [ ] Đỏ nhận RED/ĐỎ.
- [ ] Vàng nhận YELLOW/VÀNG.
- [ ] Xanh lá nhận GREEN/XANH LÁ.
- [ ] Xanh dương nhận BLUE/XANH DƯƠNG.
- [ ] Vật không thuộc màu cấu hình trả UNKNOWN, không đếm.

## 4. Stability và Counter

- [ ] Nhãn chuyển từ `ĐANG XÁC NHẬN` sang `ỔN ĐỊNH`.
- [ ] Một vật đứng lâu chỉ tăng bộ đếm một lần.
- [ ] Lấy vật ra, đặt vật mới vào thì đếm lần tiếp theo.
- [ ] RESET ĐẾM đưa toàn bộ số về 0.

## 5. Hiệu chỉnh màu

- [ ] Mở **HIỆU CHỈNH MÀU** khi camera đang bật.
- [ ] Sáu slider H/S/V thay đổi mask trực tiếp.
- [ ] LẤY DẢI TỪ MẪU tạo khoảng HSV ban đầu.
- [ ] Lưu sửa dải hiện tại.
- [ ] Thêm dải HSV thứ hai.
- [ ] Thêm một màu mới.
- [ ] Xóa dải và xóa màu.
- [ ] App cập nhật thống kê sau khi thay đổi màu.

## 6. ESP32 mock

- [ ] Kết nối MOCK_COM.
- [ ] Bấm AUTO.
- [ ] Khi sản phẩm được đếm, log có `SORT,COLOR`.
- [ ] PAUSE/ESTOP/RESET vẫn hoạt động.

## 7. YOLO sau này

- [ ] Khi YOLO tắt, HSV + Sampling Box vẫn chạy.
- [ ] Chọn model không làm app crash nếu chưa cài ultralytics.
- [ ] Khi có môi trường phù hợp, tải `product.pt` và bật YOLO.
