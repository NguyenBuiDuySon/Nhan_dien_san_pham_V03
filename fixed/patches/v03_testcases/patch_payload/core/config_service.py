from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


DEFAULT_CONFIG: dict[str, Any] = {
    "serial": {
        "port": "MOCK_COM",
        "baudrate": 115200,
        "timeout": 1.0,
        "mock_mode": True,
    },
    "model": {
        "path": "",
    },
    "camera": {
        "source": 0,
        "width": 640,
        "height": 480,
    },
    "gantry": {
        "default_jog_step_mm": 5.0,
         "last_position": {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        },
        "home": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        },
        "limits": {
            "x_min": 0.0,
            "x_max": 9999.0,
            "y_min": 0.0,
            "y_max": 9999.0,
            "z_min": 0.0,
            "z_max": 9999.0,
        },
    },
    "vision": {
        "roi": {"x": 180, "y": 100, "w": 280, "h": 280},
        "sample_box_ratio": 0.55,
        "classification": {
            "min_confidence": 0.25,
            "min_margin": 0.08,
            "min_color_pixels": 250,
            "kernel_size": 3,
            "blur_kernel_size": 1
        },
        "presence": {
            # Bắt buộc lấy nền trước khi cho phép Stability/Counter chạy.
            "require_background": True,
            "diff_threshold": 25,
            "enter_change_ratio": 0.08,
            "exit_change_ratio": 0.04,
            "kernel_size": 5
        },
        "stability": {
            "window_size": 7,
            "minimum_votes": 5,
            "release_frames": 5
        },
        "yolo": {
            "enabled": False,
            "confidence": 0.50
        }
    },
    "colors": {
        "red": {
            "h_min": 0,
            "h_max": 10,
            "s_min": 100,
            "v_min": 100,
        },
        "green": {
            "h_min": 35,
            "h_max": 85,
            "s_min": 80,
            "v_min": 80,
        },
        "blue": {
            "h_min": 100,
            "h_max": 140,
            "s_min": 90,
            "v_min": 90,
        },
    },
}


class ConfigService:
    """
    Quản lý file cấu hình app.

    File mặc định:
    - config/app_config.json

    Nhiệm vụ:
    - Tạo config nếu chưa có
    - Đọc config khi mở app
    - Lưu lại COM/model/jog/color sau này
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or PROJECT_ROOT / "config" / "app_config.json"
        self.data: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)

    def load(self) -> dict[str, Any]:
        if not self.config_path.exists():
            self.save()
            return self.data

        try:
            with self.config_path.open("r", encoding="utf-8") as file:
                loaded_data = json.load(file)

            if not isinstance(loaded_data, dict):
                raise ValueError("Config file không phải object JSON.")

        except (OSError, json.JSONDecodeError, ValueError):
            self.data = copy.deepcopy(DEFAULT_CONFIG)
            self.save()
            return self.data

        self.data = self._deep_merge(
            copy.deepcopy(DEFAULT_CONFIG),
            loaded_data,
        )
        self.save()
        return self.data

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(
                self.data,
                file,
                ensure_ascii=False,
                indent=2,
            )

    def get(self, dotted_path: str, default: Any = None) -> Any:
        current: Any = self.data

        for key in dotted_path.split("."):
            if not isinstance(current, dict) or key not in current:
                return default

            current = current[key]

        return current

    def set(self, dotted_path: str, value: Any) -> None:
        keys = dotted_path.split(".")
        current = self.data

        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}

            current = current[key]

        current[keys[-1]] = value

    def _deep_merge(
        self,
        default_data: dict[str, Any],
        loaded_data: dict[str, Any],
    ) -> dict[str, Any]:
        for key, value in loaded_data.items():
            if (
                key in default_data
                and isinstance(default_data[key], dict)
                and isinstance(value, dict)
            ):
                default_data[key] = self._deep_merge(default_data[key], value)
            else:
                default_data[key] = value

        return default_data