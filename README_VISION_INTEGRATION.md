# Vision tích hợp trong HMI

Bản này ghép phần nhận diện màu trực tiếp vào ứng dụng PySide6. Không chạy
`vision_v2/vision_main.py` đồng thời với app vì hai chương trình sẽ tranh camera.

## Chạy ứng dụng

```powershell
.\.venv\Scripts\activate
python main.py
```

## Quy trình test lần đầu

1. Mở app và bấm **BẬT CAMERA**.
2. Kéo chuột trực tiếp trên Camera View để tạo ROI.
3. Để vùng SAMPLE trống rồi bấm **LẤY NỀN**.
4. Đặt một sản phẩm vào giữa vùng SAMPLE.
5. Chờ nhãn chuyển từ **ĐANG XÁC NHẬN** sang **ỔN ĐỊNH**.
6. Lấy sản phẩm ra để vùng trở về trống trước khi đặt sản phẩm tiếp theo.

Ảnh nền giúp hệ thống chỉ phân tích những pixel thay đổi. Cách này giảm ảnh
hưởng của mặt bàn và hỗ trợ nhận vật xanh trên băng tải xanh tốt hơn cách chia
pixel trên toàn ROI.

## Kéo ROI

- Kéo chuột trái trên Camera View.
- ROI được lưu ngay vào `config/app_config.json`.
- Sau khi đổi ROI phải bấm **LẤY NỀN** lại.

## Thêm, sửa, xóa màu

Bấm **HIỆU CHỈNH MÀU** hoặc **MỞ TRACKBAR HSV**.

Cửa sổ hiệu chỉnh có sáu thanh trượt:

- Low H / High H
- Low S / High S
- Low V / High V

Chức năng:

- **LẤY DẢI TỪ MẪU**: ước lượng HSV từ sản phẩm trong Sampling Box.
- **LƯU DẢI HIỆN TẠI**: sửa dải đang chọn.
- **THÊM MÀU MỚI**: tạo hồ sơ màu mới.
- **THÊM DẢI HSV**: thêm dải thứ hai cho một màu, cần thiết với màu đỏ.
- **XÓA DẢI**: xóa một dải nhưng không xóa dải cuối cùng.
- **XÓA MÀU**: xóa toàn bộ hồ sơ màu.

Dữ liệu được lưu tại `config/colors.json`. App cập nhật ngay sau khi lưu.

## Stability và đếm một lần

Mặc định hệ thống dùng 7 frame gần nhất và cần 5 phiếu cùng màu. Khi đã đếm,
phải thấy vùng trống 5 frame liên tiếp mới mở khóa cho sản phẩm tiếp theo.

Thông số nằm trong `config/app_config.json`:

```json
"stability": {
  "window_size": 7,
  "minimum_votes": 5,
  "release_frames": 5
}
```

## ESP32

Khi app đang ở chế độ AUTO và một sản phẩm được xác nhận, app gửi:

```text
SORT,RED
SORT,YELLOW
SORT,GREEN
SORT,BLUE
```

Mock mode vẫn cho phép test log khi chưa cắm ESP32.

## YOLO sau khi train

YOLO hiện là tùy chọn và mặc định tắt. HSV vẫn chạy độc lập.

Sau khi có `product.pt`:

1. Cài `ultralytics` trong môi trường Python hỗ trợ PyTorch.
2. Chọn file model trong app.
3. Bấm **TẢI MODEL**.
4. Bật **Dùng YOLO để lấy bbox PRODUCT**.

Khi YOLO có bbox, pipeline tự đổi thành:

```text
YOLO PRODUCT bbox -> cắt vùng trong bbox -> HSV -> Stability -> Counter
```

Nếu YOLO chưa sẵn sàng, app tự quay về ROI + Sampling Box.

## Các file chính

- `core/vision_processor.py`: pipeline nhận diện.
- `core/color_repository.py`: CRUD `colors.json`.
- `core/stability_filter.py`: ổn định nhiều frame và khóa đếm.
- `core/product_detector.py`: điểm nối YOLO tùy chọn.
- `desktop_app/roi_camera_label.py`: kéo ROI trên Camera View.
- `desktop_app/color_calibrator_dialog.py`: trackbar và quản lý màu.
