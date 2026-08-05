# Chạy bản V03 Clean

## 1. Mở đúng thư mục

Mở trực tiếp thư mục chứa `main.py`, không mở thư mục cha.

## 2. Tạo môi trường Python 3.13

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\setup_env_py313.ps1
```

## 3. Chạy regression test

```powershell
.\run_regression_tests.ps1
```

## 4. Chạy app

```powershell
.\run_app.ps1
```

## 5. Tạo Git baseline

Sau khi app và test đều pass:

```powershell
.\init_git.ps1
```

## Test tay ưu tiên

1. Bật/tắt camera 5 lần, app không được thoát.
2. Ẩn/hiện Mask 5 lần, bố cục phải trở lại bình thường.
3. Chưa lấy nền: không được tăng bộ đếm.
4. Lấy nền, đặt một vật, giữ yên: chỉ đếm một lần.
5. Cắm ESP32, kết nối, sau đó rút USB: trạng thái phải chuyển sang mất kết nối.
