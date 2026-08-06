from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Không tìm thấy đúng 1 vị trí cho: {label}. Số vị trí tìm thấy: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("Cách dùng: python apply_patch.py <PROJECT_ROOT>")

    project_root = Path(sys.argv[1]).resolve()
    source_file = project_root / "desktop_app" / "main_window.py"

    if not source_file.exists():
        fail(f"Không tìm thấy file: {source_file}")

    raw = source_file.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    newline = "\r\n" if b"\r\n" in raw else "\n"

    decoded = raw.decode("utf-8-sig")
    text = decoded.replace("\r\n", "\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_root / "fixed" / "backups" / f"v05_camera_first_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, backup_dir / "main_window.py")

    text = replace_once(
        text,
        '''        camera_layout.addLayout(camera_button_row)
        camera_layout.addWidget(camera_help)
        camera_layout.addWidget(self.camera_view)
''',
        '''        camera_layout.addLayout(camera_button_row)
        camera_layout.addWidget(camera_help)
        camera_layout.addWidget(self.camera_view, 1)
''',
        "camera_view stretch",
    )

    text = replace_once(
        text,
        '''        self.mask_box = QGroupBox("HSV BINARY MASK")
        mask_layout = QVBoxLayout(self.mask_box)
''',
        '''        self.mask_box = QGroupBox("HSV BINARY MASK")
        self.mask_box.setMinimumHeight(190)
        self.mask_box.setMaximumHeight(220)
        self.mask_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        mask_layout = QVBoxLayout(self.mask_box)
''',
        "mask_box camera-first sizing",
    )

    text = replace_once(
        text,
        '''        self.mask_view.setMinimumHeight(150)
        self.mask_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
''',
        '''        self.mask_view.setMinimumHeight(110)
        self.mask_view.setMaximumHeight(145)
        self.mask_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
''',
        "mask_view fixed height",
    )

    text = replace_once(
        text,
        '''        layout.addWidget(self.camera_box, 3)
        layout.addWidget(self.mask_box, 2)
''',
        '''        layout.addWidget(self.camera_box, 1)
        layout.addWidget(self.mask_box, 0)
''',
        "center layout camera-first",
    )

    pattern = re.compile(
        r'''    def handle_mask_toggle\(self\) -> None:
.*?(?=    def handle_reset_counts\(self\) -> None:)''',
        re.DOTALL,
    )

    replacement = '''    def handle_mask_toggle(self) -> None:
        """Ẩn/hiện nội dung mask nhưng giữ nguyên bố cục Camera-first."""
        self.mask_visible = not self.mask_visible

        if self.mask_visible:
            self.btn_mask_toggle.setText("ẨN MASK")

            if self.latest_mask_frame is not None:
                self.show_mask_frame(self.latest_mask_frame)
            else:
                self._set_preview_message(
                    self.mask_view,
                    "MASK VIEW\\n\\nChưa có dữ liệu mask.",
                    point_size=11.0,
                )

            self.append_log("HSV Mask: đã bật hiển thị.")
            return

        self.btn_mask_toggle.setText("HIỆN MASK")
        self._set_preview_message(
            self.mask_view,
            "MASK VIEW\\n\\nĐÃ ẨN HIỂN THỊ",
            point_size=11.0,
        )
        self.append_log("HSV Mask: đã ẩn nội dung, giữ nguyên bố cục.")

'''

    text, count = pattern.subn(lambda _match: replacement, text, count=1)
    if count != 1:
        fail(f"Không thay được handle_mask_toggle. Số vị trí: {count}")

    output = text.replace("\n", newline)
    encoded = output.encode("utf-8")
    if has_bom:
        encoded = b"\xef\xbb\xbf" + encoded

    source_file.write_bytes(encoded)

    print(f"[OK] Đã cập nhật: {source_file}")
    print(f"[OK] Backup: {backup_dir}")
    print("[OK] Camera View được ưu tiên.")
    print("[OK] Mask giữ chiều cao cố định.")
    print("[OK] Ẩn/hiện mask không thay đổi layout.")


if __name__ == "__main__":
    main()
