from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ProductDetection:
    bbox: tuple[int, int, int, int]
    confidence: float
    class_name: str = "product"


class ProductDetector:
    """Điểm nối YOLO tùy chọn.

    Hiện tại hệ thống vẫn chạy HSV + Sampling Box khi ``enabled=False``.
    Sau khi có ``product.pt``, cài Ultralytics và bật YOLO trong app. Toàn bộ
    phần phân loại màu phía sau không phải viết lại.
    """

    def __init__(self, enabled: bool = False, confidence: float = 0.50) -> None:
        self.enabled = bool(enabled)
        self.confidence = float(confidence)
        self.model_path = ""
        self.model: Any = None
        self.last_error = ""

    @property
    def ready(self) -> bool:
        return self.model is not None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def load_model(self, model_path: str) -> tuple[bool, str]:
        path = Path(model_path)

        if not path.exists():
            self.model = None
            self.last_error = f"Không tìm thấy model: {model_path}"
            return False, self.last_error

        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError:
            self.model = None
            self.last_error = (
                "Chưa cài ultralytics. HSV vẫn chạy bình thường; "
                "cài ultralytics khi bắt đầu train/inference YOLO."
            )
            return False, self.last_error

        try:
            self.model = YOLO(str(path))
            self.model_path = str(path)
            self.last_error = ""
            return True, f"Đã tải model YOLO: {path.name}"
        except Exception as error:
            self.model = None
            self.last_error = f"Không tải được model YOLO: {error}"
            return False, self.last_error

    def unload(self) -> None:
        self.model = None
        self.model_path = ""

    def detect(self, frame_bgr: np.ndarray) -> list[ProductDetection]:
        if not self.enabled or self.model is None:
            return []

        try:
            predictions = self.model.predict(
                source=frame_bgr,
                conf=self.confidence,
                verbose=False,
            )
        except Exception as error:
            self.last_error = f"YOLO inference lỗi: {error}"
            return []

        detections: list[ProductDetection] = []

        for prediction in predictions:
            boxes = getattr(prediction, "boxes", None)

            if boxes is None:
                continue

            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                confidence = float(box.conf[0])
                class_index = int(box.cls[0])
                names = getattr(prediction, "names", {})
                class_name = str(names.get(class_index, "product"))

                x1, y1, x2, y2 = [int(round(value)) for value in xyxy]
                detections.append(
                    ProductDetection(
                        bbox=(x1, y1, x2, y2),
                        confidence=confidence,
                        class_name=class_name,
                    )
                )

        return detections
