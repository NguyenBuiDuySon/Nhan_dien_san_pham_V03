# Các thay đổi đã ghép

## Vision chạy trực tiếp trong app

- Camera vẫn chạy bằng `CameraService`/`QThread`, không chặn giao diện.
- Frame được đưa qua `VisionProcessor` rồi hiển thị trong Camera View.
- Không cần chạy `vision_main.py` riêng.

## Nhận diện màu

- ROI kéo trực tiếp bằng chuột trên Camera View.
- Sampling Box ở giữa ROI để giảm nền.
- Nút **LẤY NỀN** tạo ảnh nền tham chiếu.
- Chỉ các pixel thay đổi so với nền được dùng để phân loại màu.
- Confidence, margin và UNKNOWN.
- Morphology OPEN/CLOSE; GaussianBlur mặc định tắt.

## Stability và đếm

- Bỏ phiếu nhiều frame.
- Một sản phẩm chỉ đếm một lần.
- Phải lấy vật ra khỏi vùng kiểm tra trước khi đếm vật tiếp theo.
- Bộ đếm và nút test được dựng động theo `colors.json`.

## Quản lý màu

- Trackbar Low/High H/S/V bằng QSlider.
- Xem ảnh mẫu, mask và ảnh lọc màu trực tiếp.
- Thêm màu, sửa dải, thêm nhiều dải, xóa dải, xóa màu.
- Tự ước lượng khoảng HSV từ mẫu.
- Lưu tại `config/colors.json`.

## ESP32

Khi AUTO đang chạy và Vision xác nhận sản phẩm, app gửi:

```text
SORT,<COLOR_KEY>
```

## YOLO

- Đã có `ProductDetector` tùy chọn.
- Khi chưa có model, app tự dùng Sampling Box.
- Khi có model, bbox PRODUCT được đưa vào ColorEngine.
- Ultralytics không được ép cài lúc này để tránh ảnh hưởng Python 3.14.
