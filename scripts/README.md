# Hệ thống phân loại sản phẩm tự động — HMI v0.1

## 1. Mô tả

Ứng dụng HMI desktop dùng cho hệ thống phân loại sản phẩm theo màu sắc bằng camera.

Phiên bản hiện tại tập trung vào giao diện điều khiển, camera preview, HSV preview, cấu hình hệ thống, thống kê sản phẩm và mô phỏng kết nối ESP32.

---

## 2. Công nghệ sử dụng

- Python
- PySide6
- OpenCV
- JSON config
- Serial mock service

---

## 3. Cấu trúc thư mục

```text
Nhan_dien_san_pham/
├── main.py
├── requirements.txt
├── README.md
├── TEST_CHECKLIST.md
├── TEST_RESULT.md
├── KNOWN_ISSUES.md
├── config/
│   └── app_config.json
├── core/
│   ├── app_state.py
│   ├── camera_service.py
│   ├── config_service.py
│   ├── gantry_service.py
│   ├── hsv_color_service.py
│   ├── product_counter_service.py
│   └── serial_service.py
├── desktop_app/
│   ├── main_window.py
│   └── theme.py
└── scripts/
    └── smoke_test.py