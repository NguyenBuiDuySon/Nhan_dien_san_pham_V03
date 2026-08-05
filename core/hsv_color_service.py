from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class HSVDetectionResult:
    color_key: str | None
    color_name: str
    area: int
    areas: dict[str, int]
    mask: np.ndarray


class HSVColorService:
    """
    Nhận diện màu cơ bản bằng HSV.

    Input:
    - frame BGR từ OpenCV

    Output:
    - mask trắng/đen
    - màu có diện tích lớn nhất
    """

    DISPLAY_NAMES = {
        "red": "ĐỎ",
        "green": "XANH LÁ",
        "blue": "XANH DƯƠNG",
    }

    DEFAULT_COLORS: dict[str, dict[str, int]] = {
        "red": {
            "h_min": 0,
            "h_max": 10,
            "s_min": 100,
            "s_max": 255,
            "v_min": 100,
            "v_max": 255,
        },
        "green": {
            "h_min": 35,
            "h_max": 85,
            "s_min": 80,
            "s_max": 255,
            "v_min": 80,
            "v_max": 255,
        },
        "blue": {
            "h_min": 100,
            "h_max": 140,
            "s_min": 90,
            "s_max": 255,
            "v_min": 90,
            "v_max": 255,
        },
    }

    def __init__(
        self,
        colors_config: dict[str, Any] | None = None,
        min_area: int = 1500,
    ) -> None:
        self.colors_config = colors_config or self.DEFAULT_COLORS
        self.min_area = min_area

    def detect(self, frame_bgr: np.ndarray) -> HSVDetectionResult:
        height, width = frame_bgr.shape[:2]

        hsv_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        combined_mask = np.zeros((height, width), dtype=np.uint8)

        areas: dict[str, int] = {}

        for color_key, color_config in self.colors_config.items():
            mask = self.create_color_mask(
                hsv_frame=hsv_frame,
                color_key=color_key,
                color_config=color_config,
            )

            mask = self.clean_mask(mask)

            area = int(cv2.countNonZero(mask))
            areas[color_key] = area

            combined_mask = cv2.bitwise_or(combined_mask, mask)

        if not areas:
            return HSVDetectionResult(
                color_key=None,
                color_name="CHƯA CÓ",
                area=0,
                areas={},
                mask=combined_mask,
            )

        best_color_key, best_area = max(
            areas.items(),
            key=lambda item: item[1],
        )

        if best_area < self.min_area:
            return HSVDetectionResult(
                color_key=None,
                color_name="CHƯA CÓ",
                area=best_area,
                areas=areas,
                mask=combined_mask,
            )

        return HSVDetectionResult(
            color_key=best_color_key,
            color_name=self.DISPLAY_NAMES.get(best_color_key, best_color_key.upper()),
            area=best_area,
            areas=areas,
            mask=combined_mask,
        )

    def create_color_mask(
        self,
        hsv_frame: np.ndarray,
        color_key: str,
        color_config: Any,
    ) -> np.ndarray:
        ranges = self.get_hsv_ranges(color_key, color_config)

        height, width = hsv_frame.shape[:2]
        result_mask = np.zeros((height, width), dtype=np.uint8)

        for hsv_range in ranges:
            lower = np.array(
                [
                    hsv_range["h_min"],
                    hsv_range["s_min"],
                    hsv_range["v_min"],
                ],
                dtype=np.uint8,
            )
            upper = np.array(
                [
                    hsv_range["h_max"],
                    hsv_range["s_max"],
                    hsv_range["v_max"],
                ],
                dtype=np.uint8,
            )

            mask = cv2.inRange(hsv_frame, lower, upper)
            result_mask = cv2.bitwise_or(result_mask, mask)

        return result_mask

    def get_hsv_ranges(
        self,
        color_key: str,
        color_config: Any,
    ) -> list[dict[str, int]]:
        if isinstance(color_config, dict) and isinstance(color_config.get("ranges"), list):
            return [
                self.normalize_hsv_range(item)
                for item in color_config["ranges"]
                if isinstance(item, dict)
            ]

        if not isinstance(color_config, dict):
            color_config = self.DEFAULT_COLORS.get(color_key, {})

        base_range = self.normalize_hsv_range(color_config)

        # Màu đỏ trong HSV bị vòng qua biên 0/179:
        # đỏ thấp: 0..10
        # đỏ cao: 170..179
        if color_key == "red":
            high_red_range = {
                "h_min": 170,
                "h_max": 179,
                "s_min": base_range["s_min"],
                "s_max": base_range["s_max"],
                "v_min": base_range["v_min"],
                "v_max": base_range["v_max"],
            }

            return [base_range, high_red_range]

        return [base_range]

    def normalize_hsv_range(self, data: dict[str, Any]) -> dict[str, int]:
        return {
            "h_min": self.clamp_int(data.get("h_min", 0), 0, 179),
            "h_max": self.clamp_int(data.get("h_max", 179), 0, 179),
            "s_min": self.clamp_int(data.get("s_min", 0), 0, 255),
            "s_max": self.clamp_int(data.get("s_max", 255), 0, 255),
            "v_min": self.clamp_int(data.get("v_min", 0), 0, 255),
            "v_max": self.clamp_int(data.get("v_max", 255), 0, 255),
        }

    def clean_mask(self, mask: np.ndarray) -> np.ndarray:
        kernel = np.ones((5, 5), dtype=np.uint8)

        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        return mask

    def clamp_int(self, value: Any, min_value: int, max_value: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = min_value

        return max(min_value, min(max_value, number))