from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def read_text(path: Path) -> tuple[str, str, bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    return text, newline, has_bom


def write_text(path: Path, text: str, newline: str, has_bom: bool) -> None:
    output = text.replace("\n", newline).encode("utf-8")
    if has_bom:
        output = b"\xef\xbb\xbf" + output
    path.write_bytes(output)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"{label}: cần đúng 1 vị trí, hiện tìm thấy {count}.")
    return text.replace(old, new, 1)


def patch_main_window(path: Path) -> None:
    text, newline, has_bom = read_text(path)

    text = replace_once(
        text,
        '''        self.mask_box.setMinimumHeight(190)
        self.mask_box.setMaximumHeight(220)
''',
        '''        self.mask_box.setMinimumHeight(240)
        self.mask_box.setMaximumHeight(275)
''',
        "Kích thước mask_box",
    )

    text = replace_once(
        text,
        '''        self.mask_view.setMinimumHeight(110)
        self.mask_view.setMaximumHeight(145)
''',
        '''        self.mask_view.setMinimumHeight(165)
        self.mask_view.setMaximumHeight(205)
''',
        "Kích thước mask_view",
    )

    marker = '''    def clear_layout(self, layout) -> None:
'''
    helper = '''    @staticmethod
    def build_soft_color_button_style(ui_color: str) -> str:
        # Tạo nền nút tối, giữ sắc màu nhưng không gây chói mắt.
        value = str(ui_color).strip().lstrip("#")

        if len(value) != 6:
            value = "64748b"

        try:
            red = int(value[0:2], 16)
            green = int(value[2:4], 16)
            blue = int(value[4:6], 16)
        except ValueError:
            red, green, blue = 100, 116, 139

        background = (
            max(24, int(red * 0.34)),
            max(24, int(green * 0.34)),
            max(24, int(blue * 0.34)),
        )
        border = (
            max(55, int(red * 0.72)),
            max(55, int(green * 0.72)),
            max(55, int(blue * 0.72)),
        )

        background_hex = "#{:02x}{:02x}{:02x}".format(*background)
        border_hex = "#{:02x}{:02x}{:02x}".format(*border)

        return (
            f"background-color: {background_hex}; "
            "color: #f8fafc; "
            f"border: 1px solid {border_hex}; "
            "font-weight: 800;"
        )

'''
    if helper not in text:
        text = replace_once(
            text,
            marker,
            helper + marker,
            "Chèn build_soft_color_button_style",
        )

    text = replace_once(
        text,
        '''            button = QPushButton(f"TEST {title}")
            button.setStyleSheet(f"background-color: {ui_color}; color: #ffffff;")
''',
        '''            button = QPushButton(title)
            button.setStyleSheet(
                self.build_soft_color_button_style(ui_color)
            )
''',
        "Nút kiểm tra bộ đếm",
    )

    write_text(path, text, newline, has_bom)


def patch_color_repository(path: Path) -> None:
    text, newline, has_bom = read_text(path)

    text = replace_once(
        text,
        '''import copy
import json
import re
''',
        '''import colorsys
import copy
import json
import re
''',
        "Import colorsys",
    )

    text = replace_once(
        text,
        '''            normalized: dict[str, dict[str, Any]] = {}

            for raw_key, raw_profile in raw_data.items():
''',
        '''            normalized: dict[str, dict[str, Any]] = {}
            metadata_changed = False

            for raw_key, raw_profile in raw_data.items():
''',
        "Biến metadata_changed",
    )

    text = replace_once(
        text,
        '''                profile = self._normalize_profile(key, raw_profile)

                if profile["ranges"]:
                    normalized[key] = profile
''',
        '''                profile = self._normalize_profile(key, raw_profile)

                raw_ui_color = (
                    raw_profile.get("ui_color")
                    if isinstance(raw_profile, dict)
                    else None
                )
                if raw_ui_color != profile["ui_color"]:
                    metadata_changed = True

                if profile["ranges"]:
                    normalized[key] = profile
''',
        "Phát hiện metadata màu thay đổi",
    )

    text = replace_once(
        text,
        '''            self.colors = normalized

        except (OSError, json.JSONDecodeError, ValueError, TypeError):
''',
        '''            self.colors = normalized

            if metadata_changed:
                self.save()

        except (OSError, json.JSONDecodeError, ValueError, TypeError):
''',
        "Lưu metadata đã sửa",
    )

    text = replace_once(
        text,
        '''    def get_ui_color(self, color_key: str) -> str:
        profile = self.colors.get(color_key, {})
        return str(profile.get("ui_color", "#facc15"))
''',
        '''    def get_ui_color(self, color_key: str) -> str:
        key = self.normalize_key(color_key)
        profile = self.colors.get(key, {})
        display_name = str(profile.get("display_name", key.upper()))
        ranges = profile.get("ranges", [])

        return self.resolve_ui_color(
            key,
            display_name,
            profile.get("ui_color"),
            ranges,
        )
''',
        "get_ui_color",
    )

    text = replace_once(
        text,
        '''        ui_color: str = "#facc15",
    ) -> str:
''',
        '''        ui_color: str | None = None,
    ) -> str:
''',
        "Tham số add_color",
    )

    text = replace_once(
        text,
        '''        self.colors[key] = {
            "display_name": display_name.strip().upper(),
            "ui_color": ui_color,
            "ranges": [self.normalize_range(hsv_range)],
        }
''',
        '''        normalized_range = self.normalize_range(hsv_range)
        normalized_name = display_name.strip().upper()

        self.colors[key] = {
            "display_name": normalized_name,
            "ui_color": self.resolve_ui_color(
                key,
                normalized_name,
                ui_color,
                [normalized_range],
            ),
            "ranges": [normalized_range],
        }
''',
        "Tự tạo ui_color khi thêm màu",
    )

    text = replace_once(
        text,
        '''            display_name = str(data.get("display_name", key.upper()))
            ui_color = str(data.get("ui_color", "#facc15"))
            return {
                "display_name": display_name,
                "ui_color": ui_color,
                "ranges": ranges,
            }
''',
        '''            display_name = str(data.get("display_name", key.upper()))
            ui_color = self.resolve_ui_color(
                key,
                display_name,
                data.get("ui_color"),
                ranges,
            )
            return {
                "display_name": display_name,
                "ui_color": ui_color,
                "ranges": ranges,
            }
''',
        "Chuẩn hóa profile định dạng mới",
    )

    text = replace_once(
        text,
        '''            return {
                "display_name": key.upper(),
                "ui_color": "#facc15",
                "ranges": ranges,
            }
''',
        '''            display_name = key.upper()
            return {
                "display_name": display_name,
                "ui_color": self.resolve_ui_color(
                    key,
                    display_name,
                    None,
                    ranges,
                ),
                "ranges": ranges,
            }
''',
        "Chuẩn hóa profile dạng danh sách",
    )

    text = replace_once(
        text,
        '''            return {
                "display_name": key.upper(),
                "ui_color": "#facc15",
                "ranges": [self.normalize_range(legacy_range)],
            }

        return {
            "display_name": key.upper(),
            "ui_color": "#facc15",
            "ranges": [],
        }
''',
        '''            normalized_ranges = [self.normalize_range(legacy_range)]
            display_name = key.upper()
            return {
                "display_name": display_name,
                "ui_color": self.resolve_ui_color(
                    key,
                    display_name,
                    None,
                    normalized_ranges,
                ),
                "ranges": normalized_ranges,
            }

        display_name = key.upper()
        return {
            "display_name": display_name,
            "ui_color": self.resolve_ui_color(
                key,
                display_name,
                None,
                [],
            ),
            "ranges": [],
        }
''',
        "Chuẩn hóa profile legacy",
    )

    marker = '''    @staticmethod
    def _clamp(value: Any, minimum: int, maximum: int) -> int:
'''
    helpers = '''    @classmethod
    def resolve_ui_color(
        cls,
        key: str,
        display_name: str,
        ui_color: Any,
        ranges: list[dict[str, list[int]]],
    ) -> str:
        normalized_key = cls.normalize_key(key)
        normalized_name = cls.normalize_key(display_name)
        provided = cls.normalize_hex_color(ui_color)

        is_yellow_name = any(
            token in normalized_key or token in normalized_name
            for token in ("yellow", "vang")
        )

        if provided and not (
            provided.lower() == "#facc15" and not is_yellow_name
        ):
            return provided

        return cls.derive_ui_color(
            normalized_key,
            normalized_name,
            ranges,
        )

    @staticmethod
    def normalize_hex_color(value: Any) -> str | None:
        text = str(value or "").strip()

        if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
            return text.lower()

        return None

    @classmethod
    def derive_ui_color(
        cls,
        normalized_key: str,
        normalized_name: str,
        ranges: list[dict[str, list[int]]],
    ) -> str:
        combined_name = f"{normalized_key}_{normalized_name}"

        named_colors = (
            (("black", "den"), "#cbd5e1"),
            (("white", "trang"), "#e2e8f0"),
            (("gray", "grey", "xam"), "#94a3b8"),
            (("red", "do"), "#ef4444"),
            (("yellow", "vang"), "#facc15"),
            (("green", "xanh_la"), "#22c55e"),
            (("blue", "xanh_duong"), "#38bdf8"),
            (("purple", "violet", "tim"), "#a855f7"),
            (("orange", "cam"), "#f97316"),
            (("pink", "hong"), "#ec4899"),
            (("brown", "nau"), "#b7791f"),
        )

        for aliases, color in named_colors:
            if any(alias in combined_name for alias in aliases):
                return color

        if not ranges:
            return "#94a3b8"

        hsv_range = ranges[0]
        lower = hsv_range.get("lower", [0, 0, 0])
        upper = hsv_range.get("upper", [179, 255, 255])

        hue = (float(lower[0]) + float(upper[0])) / 2.0
        saturation = (float(lower[1]) + float(upper[1])) / (2.0 * 255.0)
        value = (float(lower[2]) + float(upper[2])) / (2.0 * 255.0)

        saturation = max(0.55, min(0.88, saturation))
        value = max(0.72, min(0.90, value))

        red, green, blue = colorsys.hsv_to_rgb(
            hue / 179.0,
            saturation,
            value,
        )

        return "#{:02x}{:02x}{:02x}".format(
            int(red * 255),
            int(green * 255),
            int(blue * 255),
        )

'''
    if helpers not in text:
        text = replace_once(
            text,
            marker,
            helpers + marker,
            "Chèn bộ suy ra ui_color",
        )

    write_text(path, text, newline, has_bom)


def main() -> None:
    if len(sys.argv) != 2:
        fail("Cách dùng: python apply_patch.py <PROJECT_ROOT>")

    project_root = Path(sys.argv[1]).resolve()
    main_window = project_root / "desktop_app" / "main_window.py"
    color_repository = project_root / "core" / "color_repository.py"
    colors_json = project_root / "config" / "colors.json"

    for path in (main_window, color_repository):
        if not path.exists():
            fail(f"Không tìm thấy: {path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = (
        project_root
        / "fixed"
        / "backups"
        / f"v06_ui_color_final_{timestamp}"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(main_window, backup_dir / "main_window.py")
    shutil.copy2(color_repository, backup_dir / "color_repository.py")

    if colors_json.exists():
        shutil.copy2(colors_json, backup_dir / "colors.json")

    try:
        patch_main_window(main_window)
        patch_color_repository(color_repository)
    except Exception:
        shutil.copy2(backup_dir / "main_window.py", main_window)
        shutil.copy2(backup_dir / "color_repository.py", color_repository)
        raise

    print(f"[OK] Đã sửa: {main_window}")
    print(f"[OK] Đã sửa: {color_repository}")
    print(f"[OK] Backup: {backup_dir}")
    print("[OK] Mask lớn hơn nhưng layout vẫn cố định.")
    print("[OK] Đã bỏ chữ TEST.")
    print("[OK] Nút màu dùng tông tối, giảm chói.")
    print("[OK] ui_color được giữ/tự suy ra sau CRUD.")


if __name__ == "__main__":
    main()
