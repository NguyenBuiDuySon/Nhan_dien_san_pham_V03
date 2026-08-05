from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


MODULES_TO_CHECK = [
    "core.app_state",
    "core.camera_service",
    "core.config_service",
    "core.color_repository",
    "core.gantry_service",
    "core.hsv_color_service",
    "core.product_counter_service",
    "core.product_detector",
    "core.stability_filter",
    "core.vision_processor",
    "core.serial_service",
    "desktop_app.main_window",
    "desktop_app.theme",
]


def print_pass(message: str) -> None:
    print(f"[PASS] {message}")


def print_warn(message: str) -> None:
    print(f"[WARN] {message}")


def print_fail(message: str) -> None:
    print(f"[FAIL] {message}")


def check_imports() -> bool:
    ok = True

    for module_name in MODULES_TO_CHECK:
        try:
            importlib.import_module(module_name)
            print_pass(f"Import OK: {module_name}")
        except Exception as error:
            print_fail(f"Import lỗi: {module_name} -> {error}")
            ok = False

    return ok


def check_config() -> bool:
    from core.config_service import ConfigService

    config_service = ConfigService()
    config = config_service.load()

    required_paths = [
        "serial",
        "model",
        "camera",
        "gantry",
        "colors",
        "vision",
    ]

    ok = True

    for key in required_paths:
        if key not in config:
            print_fail(f"Config thiếu key: {key}")
            ok = False
        else:
            print_pass(f"Config có key: {key}")

    return ok


def check_counter() -> bool:
    from core.product_counter_service import ProductCounterService

    counter = ProductCounterService(["red", "yellow", "green", "blue"])

    counter.increment("red")
    counter.increment("yellow")
    counter.increment("green")
    counter.increment("blue")
    counter.increment("error")

    counts = counter.snapshot()

    expected = {
        "red": 1,
        "yellow": 1,
        "green": 1,
        "blue": 1,
        "error": 1,
    }

    if counts != expected:
        print_fail(f"Counter sai. Expected={expected}, actual={counts}")
        return False

    counter.reset()

    reset_counts = counter.snapshot()

    if any(value != 0 for value in reset_counts.values()):
        print_fail(f"Counter reset lỗi: {reset_counts}")
        return False

    print_pass("CounterService OK")
    return True


def check_camera_source() -> bool:
    from core.camera_service import CameraService
    from core.config_service import ConfigService

    config_service = ConfigService()
    config = config_service.load()

    camera_config = config.get("camera", {})
    source = camera_config.get("source", 0)

    available = CameraService.is_source_available(source)

    if available:
        print_pass(f"Camera source={source} khả dụng")
        return True

    print_warn(f"Camera source={source} không khả dụng hoặc đang bị app khác chiếm")
    return True


def main() -> None:
    print("========== SMOKE TEST START ==========")

    results = [
        check_imports(),
        check_config(),
        check_counter(),
        check_camera_source(),
    ]

    print("========== SMOKE TEST END ==========")

    if all(results):
        print_pass("Smoke test hoàn tất.")
        return

    print_fail("Smoke test có lỗi cần sửa.")
    raise SystemExit(1)


if __name__ == "__main__":
    main()