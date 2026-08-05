"""Test lõi Vision không cần camera và không cần PySide6.

Các case bám theo lỗi thực tế đã ghi nhận:
1. Chưa lấy nền -> tuyệt đối không phát sự kiện đếm.
2. Nền trống -> không đếm.
3. Đặt vật đỏ -> đếm đúng một lần.
4. Giữ vật đứng yên -> không đếm lặp.
5. Lấy vật ra đủ frame -> sản phẩm tiếp theo được phép đếm.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from core.color_repository import ColorRepository
from core.vision_processor import VisionProcessor


def create_processor(temp_dir: Path) -> VisionProcessor:
    # Dùng file màu tạm để regression test không phụ thuộc colors.json
    # mà người dùng đã hiệu chỉnh trong app.
    repository = ColorRepository(temp_dir / "colors_test.json")
    config = {
        "roi": {"x": 100, "y": 50, "w": 200, "h": 200},
        "sample_box_ratio": 0.55,
        "classification": {
            "min_confidence": 0.25,
            "min_margin": 0.08,
            "min_color_pixels": 100,
            "kernel_size": 3,
        },
        "presence": {
            "require_background": True,
            "diff_threshold": 15,
            "enter_change_ratio": 0.05,
            "exit_change_ratio": 0.02,
            "kernel_size": 3,
        },
        "stability": {
            "window_size": 5,
            "minimum_votes": 3,
            "release_frames": 3,
        },
        "yolo": {"enabled": False},
    }

    return VisionProcessor(
        config,
        repository,
        background_path=temp_dir / "background_test.png",
    )


def main() -> None:
    with TemporaryDirectory(prefix="vision_regression_") as temp_name:
        processor = create_processor(Path(temp_name))
        run_cases(processor)


def run_cases(processor: VisionProcessor) -> None:
    processor.clear_background()

    empty_frame = np.full((300, 400, 3), 255, dtype=np.uint8)
    red_frame = empty_frame.copy()
    cv2.rectangle(red_frame, (145, 95), (255, 205), (0, 0, 255), -1)

    # Case 1: Chưa lấy nền thì counter phải bị khóa.
    no_background_events: list[str] = []

    for _ in range(8):
        result = processor.process(red_frame)

        assert result.counting_ready is False
        assert result.present is False

        if result.count_event:
            no_background_events.append(result.count_event)

    assert no_background_events == [], no_background_events
    print("[PASS] Chưa lấy nền: không phát sự kiện đếm.")

    # Lấy nền từ frame trống.
    ok, message = processor.capture_background(empty_frame)
    assert ok, message

    # Case 2: Nền trống không được tính là sản phẩm.
    empty_events: list[str] = []

    for _ in range(8):
        result = processor.process(empty_frame)

        assert result.present is False

        if result.count_event:
            empty_events.append(result.count_event)

    assert empty_events == [], empty_events
    print("[PASS] Nền trống: không bị nhận thành sản phẩm.")

    # Case 3 + 4: Vật đỏ phát đúng một event dù đứng nhiều frame.
    first_product_events: list[str] = []

    for _ in range(12):
        result = processor.process(red_frame)

        if result.count_event:
            first_product_events.append(result.count_event)

    assert first_product_events == ["red"], first_product_events
    print("[PASS] Vật RED: nhận đúng và chỉ đếm một lần.")

    # Case 5: Lấy vật ra đủ release_frames rồi đặt lại -> đếm lần thứ hai.
    for _ in range(5):
        result = processor.process(empty_frame)
        assert result.count_event is None

    second_product_events: list[str] = []

    for _ in range(8):
        result = processor.process(red_frame)

        if result.count_event:
            second_product_events.append(result.count_event)

    assert second_product_events == ["red"], second_product_events
    print("[PASS] Vật rời vùng rồi vào lại: được phép đếm lần tiếp theo.")

    processor.clear_background()
    print("[PASS] Toàn bộ Vision regression test hoàn tất.")


if __name__ == "__main__":
    main()
