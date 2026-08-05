from __future__ import annotations

import copy
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COLOR_PATH = PROJECT_ROOT / "config" / "colors.json"


DEFAULT_COLORS: dict[str, dict[str, Any]] = {
    "red": {
        "display_name": "ĐỎ",
        "ui_color": "#ef4444",
        "ranges": [
            {"lower": [0, 90, 70], "upper": [10, 255, 255]},
            {"lower": [170, 90, 70], "upper": [179, 255, 255]},
        ],
    },
    "yellow": {
        "display_name": "VÀNG",
        "ui_color": "#facc15",
        "ranges": [
            {"lower": [18, 80, 80], "upper": [38, 255, 255]},
        ],
    },
    "green": {
        "display_name": "XANH LÁ",
        "ui_color": "#22c55e",
        "ranges": [
            {"lower": [35, 60, 60], "upper": [90, 255, 255]},
        ],
    },
    "blue": {
        "display_name": "XANH DƯƠNG",
        "ui_color": "#38bdf8",
        "ranges": [
            {"lower": [90, 70, 60], "upper": [135, 255, 255]},
        ],
    },
}


class ColorRepository:
    """Đọc, lưu, thêm, sửa và xóa các hồ sơ màu HSV.

    File màu được tách khỏi ``app_config.json`` để người dùng có thể
    hiệu chỉnh màu mà không ảnh hưởng tới cấu hình camera, ESP32 hoặc gantry.

    Cấu trúc một màu::

        "blue": {
            "display_name": "XANH DƯƠNG",
            "ui_color": "#38bdf8",
            "ranges": [
                {"lower": [90, 70, 60], "upper": [135, 255, 255]}
            ]
        }
    """

    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or DEFAULT_COLOR_PATH
        self.colors: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> dict[str, dict[str, Any]]:
        """Đọc file màu; tự tạo file mặc định nếu file thiếu hoặc lỗi."""
        if not self.file_path.exists():
            self.colors = copy.deepcopy(DEFAULT_COLORS)
            self.save()
            return self.colors

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)

            if not isinstance(raw_data, dict):
                raise ValueError("colors.json phải là một JSON object")

            normalized: dict[str, dict[str, Any]] = {}

            for raw_key, raw_profile in raw_data.items():
                key = self.normalize_key(str(raw_key))

                if not key:
                    continue

                profile = self._normalize_profile(key, raw_profile)

                if profile["ranges"]:
                    normalized[key] = profile

            if not normalized:
                raise ValueError("colors.json không có hồ sơ màu hợp lệ")

            self.colors = normalized

        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            self.colors = copy.deepcopy(DEFAULT_COLORS)
            self.save()

        return self.colors

    def save(self) -> None:
        """Ghi toàn bộ hồ sơ màu xuống file JSON."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        with self.file_path.open("w", encoding="utf-8") as file:
            json.dump(
                self.colors,
                file,
                ensure_ascii=False,
                indent=2,
            )

    def color_keys(self) -> list[str]:
        return list(self.colors.keys())

    def get_profile(self, color_key: str) -> dict[str, Any]:
        key = self.normalize_key(color_key)

        if key not in self.colors:
            raise KeyError(f"Không tồn tại màu: {color_key}")

        return copy.deepcopy(self.colors[key])

    def get_display_name(self, color_key: str) -> str:
        profile = self.colors.get(color_key, {})
        return str(profile.get("display_name", color_key.upper()))

    def get_ui_color(self, color_key: str) -> str:
        profile = self.colors.get(color_key, {})
        return str(profile.get("ui_color", "#facc15"))

    def get_detection_config(self) -> dict[str, list[dict[str, list[int]]]]:
        """Trả cấu hình gọn chỉ gồm các khoảng HSV cho ColorEngine."""
        return {
            color_key: copy.deepcopy(profile.get("ranges", []))
            for color_key, profile in self.colors.items()
        }

    def add_color(
        self,
        display_name: str,
        hsv_range: dict[str, list[int]],
        ui_color: str = "#facc15",
    ) -> str:
        """Thêm màu mới và trả về key đã chuẩn hóa."""
        key = self.normalize_key(display_name)

        if not key:
            raise ValueError("Tên màu không hợp lệ")

        if key in self.colors:
            raise ValueError(f"Màu '{display_name}' đã tồn tại")

        self.colors[key] = {
            "display_name": display_name.strip().upper(),
            "ui_color": ui_color,
            "ranges": [self.normalize_range(hsv_range)],
        }
        self.save()
        return key

    def add_range(self, color_key: str, hsv_range: dict[str, list[int]]) -> int:
        """Thêm một khoảng HSV mới cho màu và trả về chỉ số khoảng."""
        key = self.normalize_key(color_key)
        profile = self.colors.get(key)

        if profile is None:
            raise KeyError(f"Không tồn tại màu: {color_key}")

        profile["ranges"].append(self.normalize_range(hsv_range))
        self.save()
        return len(profile["ranges"]) - 1

    def update_range(
        self,
        color_key: str,
        range_index: int,
        hsv_range: dict[str, list[int]],
    ) -> None:
        """Cập nhật một khoảng HSV đã có."""
        key = self.normalize_key(color_key)
        profile = self.colors.get(key)

        if profile is None:
            raise KeyError(f"Không tồn tại màu: {color_key}")

        ranges = profile["ranges"]

        if range_index < 0 or range_index >= len(ranges):
            raise IndexError("Chỉ số khoảng HSV không hợp lệ")

        ranges[range_index] = self.normalize_range(hsv_range)
        self.save()

    def delete_range(self, color_key: str, range_index: int) -> None:
        """Xóa một khoảng HSV; không cho xóa khoảng cuối cùng của màu."""
        key = self.normalize_key(color_key)
        profile = self.colors.get(key)

        if profile is None:
            raise KeyError(f"Không tồn tại màu: {color_key}")

        ranges = profile["ranges"]

        if len(ranges) <= 1:
            raise ValueError("Mỗi màu phải còn ít nhất một khoảng HSV")

        if range_index < 0 or range_index >= len(ranges):
            raise IndexError("Chỉ số khoảng HSV không hợp lệ")

        ranges.pop(range_index)
        self.save()

    def delete_color(self, color_key: str) -> None:
        key = self.normalize_key(color_key)

        if key not in self.colors:
            raise KeyError(f"Không tồn tại màu: {color_key}")

        del self.colors[key]
        self.save()

    def update_metadata(
        self,
        color_key: str,
        display_name: str | None = None,
        ui_color: str | None = None,
    ) -> None:
        key = self.normalize_key(color_key)
        profile = self.colors.get(key)

        if profile is None:
            raise KeyError(f"Không tồn tại màu: {color_key}")

        if display_name is not None and display_name.strip():
            profile["display_name"] = display_name.strip().upper()

        if ui_color is not None and ui_color.strip():
            profile["ui_color"] = ui_color.strip()

        self.save()

    @staticmethod
    def normalize_key(name: str) -> str:
        """Đổi tên hiển thị thành key an toàn, ví dụ 'Xanh tím' -> 'xanh_tim'."""
        normalized = unicodedata.normalize("NFD", name.strip().lower())
        ascii_text = "".join(
            character
            for character in normalized
            if unicodedata.category(character) != "Mn"
        )
        ascii_text = ascii_text.replace("đ", "d")
        ascii_text = re.sub(r"[^a-z0-9]+", "_", ascii_text)
        return ascii_text.strip("_")

    @classmethod
    def normalize_range(cls, data: dict[str, Any]) -> dict[str, list[int]]:
        lower = data.get("lower", [0, 0, 0])
        upper = data.get("upper", [179, 255, 255])

        if not isinstance(lower, (list, tuple)) or len(lower) != 3:
            lower = [0, 0, 0]

        if not isinstance(upper, (list, tuple)) or len(upper) != 3:
            upper = [179, 255, 255]

        low_h = cls._clamp(lower[0], 0, 179)
        low_s = cls._clamp(lower[1], 0, 255)
        low_v = cls._clamp(lower[2], 0, 255)
        high_h = cls._clamp(upper[0], 0, 179)
        high_s = cls._clamp(upper[1], 0, 255)
        high_v = cls._clamp(upper[2], 0, 255)

        # Low không được lớn hơn High trong một khoảng đơn.
        return {
            "lower": [min(low_h, high_h), min(low_s, high_s), min(low_v, high_v)],
            "upper": [max(low_h, high_h), max(low_s, high_s), max(low_v, high_v)],
        }

    def _normalize_profile(self, key: str, data: Any) -> dict[str, Any]:
        # Hỗ trợ cả định dạng mới (ranges) và định dạng cũ h_min/h_max.
        if isinstance(data, dict) and isinstance(data.get("ranges"), list):
            ranges = [
                self.normalize_range(item)
                for item in data["ranges"]
                if isinstance(item, dict)
            ]
            display_name = str(data.get("display_name", key.upper()))
            ui_color = str(data.get("ui_color", "#facc15"))
            return {
                "display_name": display_name,
                "ui_color": ui_color,
                "ranges": ranges,
            }

        if isinstance(data, list):
            ranges = [
                self.normalize_range(item)
                for item in data
                if isinstance(item, dict)
            ]
            return {
                "display_name": key.upper(),
                "ui_color": "#facc15",
                "ranges": ranges,
            }

        if isinstance(data, dict):
            legacy_range = {
                "lower": [
                    data.get("h_min", 0),
                    data.get("s_min", 0),
                    data.get("v_min", 0),
                ],
                "upper": [
                    data.get("h_max", 179),
                    data.get("s_max", 255),
                    data.get("v_max", 255),
                ],
            }
            return {
                "display_name": key.upper(),
                "ui_color": "#facc15",
                "ranges": [self.normalize_range(legacy_range)],
            }

        return {
            "display_name": key.upper(),
            "ui_color": "#facc15",
            "ranges": [],
        }

    @staticmethod
    def _clamp(value: Any, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = minimum

        return max(minimum, min(maximum, number))
