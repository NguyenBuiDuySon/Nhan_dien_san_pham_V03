# Vision V2

## Chạy chương trình

```powershell
uv run python vision_v2/vision_main.py
```

## Phím điều khiển

- Kéo chuột trái: chọn ROI
- P: lưu ROI
- R: reload `colors.json`
- T: DEBUG / OPERATOR
- Q: thoát

## Ghi chú

Hiện tại ROI kéo bằng chuột đóng vai trò vùng sản phẩm.
Khi có YOLO, chỉ thay nguồn `product_crop` bằng bbox do model trả về.
