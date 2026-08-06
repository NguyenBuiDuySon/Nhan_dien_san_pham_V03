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


COUNTER_SERVICE_SOURCE = r'''from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


class ProductCounterService:
    # Bộ đếm sản xuất lưu bền vững vào config/counters.json.

    DEFAULT_STORAGE_PATH = (
        Path(__file__).resolve().parents[1] / "config" / "counters.json"
    )

    def __init__(
        self,
        color_keys: Iterable[str] | None = None,
        storage_path: str | Path | None = None,
        autosave: bool = True,
    ) -> None:
        self.storage_path = Path(
            storage_path or self.DEFAULT_STORAGE_PATH
        ).resolve()
        self.autosave = bool(autosave)
        self.counts: dict[str, int] = {"error": 0}
        self.last_load_error: str | None = None

        self.load()
        self.configure_keys(
            color_keys or ["red", "green", "blue"],
            save=False,
        )

        if self.autosave:
            self.save()

    @staticmethod
    def normalize_key(key: Any) -> str:
        return str(key).strip().lower()

    @staticmethod
    def normalize_count(value: Any) -> int:
        try:
            count = int(value)
        except (TypeError, ValueError):
            return 0

        return max(0, count)

    def load(self) -> dict[str, int]:
        # File lỗi không được làm app bị văng.
        self.last_load_error = None

        if not self.storage_path.exists():
            self.counts = {"error": 0}
            return self.snapshot()

        try:
            raw_data = json.loads(
                self.storage_path.read_text(encoding="utf-8-sig")
            )

            if not isinstance(raw_data, dict):
                raise ValueError("Nội dung counters.json phải là object JSON.")

            raw_counts = raw_data.get("counts", raw_data)

            if not isinstance(raw_counts, dict):
                raise ValueError("Trường counts phải là object JSON.")

            loaded: dict[str, int] = {}

            for raw_key, raw_value in raw_counts.items():
                key = self.normalize_key(raw_key)

                if key:
                    loaded[key] = self.normalize_count(raw_value)

            loaded["error"] = self.normalize_count(
                loaded.get("error", 0)
            )
            self.counts = loaded
            return self.snapshot()

        except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
            self.last_load_error = str(error)
            self.counts = {"error": 0}
            return self.snapshot()

    def save(self) -> None:
        # Ghi file tạm rồi thay thế file chính để giảm nguy cơ hỏng JSON.
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "counts": self.snapshot(),
        }

        temporary_path = self.storage_path.with_suffix(
            self.storage_path.suffix + ".tmp"
        )

        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.storage_path)

    def configure_keys(
        self,
        color_keys: Iterable[str],
        save: bool = True,
    ) -> None:
        # Đồng bộ colors.json và giữ số của màu còn tồn tại.
        old_counts = dict(self.counts)
        new_counts: dict[str, int] = {}

        for raw_key in color_keys:
            key = self.normalize_key(raw_key)

            if key and key != "error":
                new_counts[key] = self.normalize_count(
                    old_counts.get(key, 0)
                )

        new_counts["error"] = self.normalize_count(
            old_counts.get("error", 0)
        )
        self.counts = new_counts

        if save and self.autosave:
            self.save()

    def increment(self, key: str) -> int:
        normalized = self.normalize_key(key)

        if normalized not in self.counts:
            normalized = "error"

        self.counts[normalized] += 1

        if self.autosave:
            self.save()

        return self.counts[normalized]

    def reset(self) -> None:
        for key in self.counts:
            self.counts[key] = 0

        if self.autosave:
            self.save()

    def snapshot(self) -> dict[str, int]:
        return dict(self.counts)
'''


COUNTER_TEST_SOURCE = r'''# Regression test cho bộ đếm sản xuất lưu qua lần mở app.

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from core.product_counter_service import ProductCounterService


def main() -> None:
    with TemporaryDirectory(prefix="counter_regression_") as temp_name:
        storage_path = Path(temp_name) / "counters.json"

        first = ProductCounterService(
            ["red", "blue"],
            storage_path=storage_path,
        )
        assert first.snapshot() == {
            "red": 0,
            "blue": 0,
            "error": 0,
        }

        first.increment("red")
        first.increment("red")
        first.increment("blue")
        first.increment("khong_ton_tai")

        assert first.snapshot() == {
            "red": 2,
            "blue": 1,
            "error": 1,
        }

        reopened = ProductCounterService(
            ["red", "blue"],
            storage_path=storage_path,
        )
        assert reopened.snapshot() == {
            "red": 2,
            "blue": 1,
            "error": 1,
        }
        print("[PASS] Mở lại app: giữ nguyên số đếm sản xuất.")

        reopened.configure_keys(["red", "black"])
        assert reopened.snapshot() == {
            "red": 2,
            "black": 0,
            "error": 1,
        }

        reopened_again = ProductCounterService(
            ["red", "black"],
            storage_path=storage_path,
        )
        assert reopened_again.snapshot() == {
            "red": 2,
            "black": 0,
            "error": 1,
        }
        print("[PASS] CRUD màu: đồng bộ key và giữ số đếm hợp lệ.")

        reopened_again.reset()

        after_reset = ProductCounterService(
            ["red", "black"],
            storage_path=storage_path,
        )
        assert after_reset.snapshot() == {
            "red": 0,
            "black": 0,
            "error": 0,
        }
        print("[PASS] RESET: lưu trạng thái 0 qua lần mở app tiếp theo.")


if __name__ == "__main__":
    main()
'''


def patch_main_window(path: Path) -> None:
    text, newline, has_bom = read_text(path)

    text = replace_once(
        text,
        '''    QLabel,
    QLineEdit,
''',
        '''    QLabel,
    QLineEdit,
    QMessageBox,
''',
        "Import QMessageBox",
    )

    text = replace_once(
        text,
        '''        box = QGroupBox("THỐNG KÊ SẢN PHẨM")
''',
        '''        box = QGroupBox("BỘ ĐẾM SẢN XUẤT")
''',
        "Tên khối bộ đếm",
    )

    text = replace_once(
        text,
        '''        self.test_grid = QGridLayout()
        self.test_grid.setHorizontalSpacing(ROW_GAP)
        self.test_grid.setVerticalSpacing(ROW_GAP)

        self.stat_values: dict[str, QLabel] = {}
        self.test_count_buttons: list[QPushButton] = []

        self.btn_reset_counts = QPushButton("RESET ĐẾM")
        self.btn_reset_counts.setStyleSheet("background-color: #334155;")

        layout.addLayout(self.stats_grid)
        layout.addWidget(self.btn_reset_counts)
        layout.addLayout(self.test_grid)
''',
        '''        self.stat_values: dict[str, QLabel] = {}

        self.btn_reset_counts = QPushButton("RESET BỘ ĐẾM")
        self.btn_reset_counts.setStyleSheet(
            "background-color: #4c2630; "
            "border: 1px solid #7f3b46; "
            "color: #f8fafc;"
        )
        self.btn_reset_counts.setToolTip(
            "Đặt toàn bộ bộ đếm sản xuất về 0."
        )

        layout.addLayout(self.stats_grid)
        layout.addWidget(self.btn_reset_counts)
''',
        "Loại bỏ test_grid và nút cộng thử",
    )

    text = replace_once(
        text,
        '''        self.clear_layout(self.stats_grid)
        self.clear_layout(self.test_grid)
        self.stat_values.clear()
        self.test_count_buttons.clear()
''',
        '''        self.clear_layout(self.stats_grid)
        self.stat_values.clear()
''',
        "Dọn layout thống kê",
    )

    text = replace_once(
        text,
        '''            button = QPushButton(title)
            button.setStyleSheet(
                self.build_soft_color_button_style(ui_color)
            )
            button.clicked.connect(
                lambda checked=False, color_key=key: self.handle_test_count(color_key)
            )
            self.test_grid.addWidget(button, row, column)
            self.test_count_buttons.append(button)

''',
        '',
        "Xóa khối tạo nút cộng thử",
    )

    text = replace_once(
        text,
        '''        self.append_log("Đã tải cấu hình từ config/app_config.json.")
        self.append_log("Vision v0.2 đã tích hợp: ROI, Sampling Box, HSV, Stability và Counter.")
''',
        '''        self.append_log("Đã tải cấu hình từ config/app_config.json.")
        self.append_log("Vision v0.2 đã tích hợp: ROI, Sampling Box, HSV, Stability và Counter.")
        self.append_log(
            "Đã khôi phục bộ đếm sản xuất: "
            f"{self.counter_service.snapshot()}"
        )

        if self.counter_service.last_load_error:
            self.append_log(
                "Không đọc được counters.json cũ; đã tạo bộ đếm mới. "
                f"Chi tiết: {self.counter_service.last_load_error}",
                level="WARN",
            )
''',
        "Log khôi phục bộ đếm",
    )

    text = replace_once(
        text,
        '''    def handle_reset_counts(self) -> None:
        self.counter_service.reset()
        self.refresh_count_ui()
        self.append_log("Đã reset số đếm sản phẩm về 0.")

    def handle_test_count(self, color_key: str) -> None:
        self.increment_product_count(color_key, source="TEST")


''',
        '''    def handle_reset_counts(self) -> None:
        answer = QMessageBox.question(
            self,
            "Xác nhận reset bộ đếm",
            "Toàn bộ bộ đếm sản xuất sẽ về 0 và được lưu ngay.\\n"
            "Bạn có chắc muốn tiếp tục?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            self.append_log("Đã hủy reset bộ đếm sản xuất.")
            return

        self.counter_service.reset()
        self.refresh_count_ui()
        self.append_log(
            "Đã reset và lưu bộ đếm sản xuất về 0.",
            level="WARN",
        )


''',
        "Reset có xác nhận và xóa handle_test_count",
    )

    text = replace_once(
        text,
        '''        self.save_gantry_position_to_config()
        super().closeEvent(event)
''',
        '''        self.counter_service.save()
        self.save_gantry_position_to_config()
        super().closeEvent(event)
''',
        "Lưu counter khi đóng app",
    )

    write_text(path, text, newline, has_bom)


def patch_regression_script(path: Path) -> None:
    text, newline, has_bom = read_text(path)

    marker = '''Write-Host "=== SERIAL DISCONNECT ===" -ForegroundColor Cyan
'''
    addition = '''Write-Host "=== PRODUCTION COUNTER ===" -ForegroundColor Cyan
& $PythonExe .\\scripts\\test_product_counter_persistence.py

'''

    if addition not in text:
        text = replace_once(
            text,
            marker,
            addition + marker,
            "Thêm regression test bộ đếm",
        )

    write_text(path, text, newline, has_bom)


def patch_gitignore(path: Path) -> None:
    text, newline, has_bom = read_text(path)

    if "config/counters.json" not in text.splitlines():
        if text and not text.endswith("\n"):
            text += "\n"

        text += (
            "\n# Runtime production counters - do not commit machine data.\n"
            "config/counters.json\n"
            "config/counters.json.tmp\n"
        )

    write_text(path, text, newline, has_bom)


def main() -> None:
    if len(sys.argv) != 2:
        fail("Cách dùng: python apply_patch.py <PROJECT_ROOT>")

    project_root = Path(sys.argv[1]).resolve()

    main_window = project_root / "desktop_app" / "main_window.py"
    counter_service = project_root / "core" / "product_counter_service.py"
    regression_script = project_root / "run_regression_tests.ps1"
    gitignore = project_root / ".gitignore"
    counter_test = (
        project_root / "scripts" / "test_product_counter_persistence.py"
    )
    counters_json = project_root / "config" / "counters.json"

    for path in (
        main_window,
        counter_service,
        regression_script,
        gitignore,
    ):
        if not path.exists():
            fail(f"Không tìm thấy: {path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = (
        project_root
        / "fixed"
        / "backups"
        / f"v07_production_counter_{timestamp}"
    )
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_pairs = [
        (main_window, backup_dir / "main_window.py"),
        (
            counter_service,
            backup_dir / "product_counter_service.py",
        ),
        (
            regression_script,
            backup_dir / "run_regression_tests.ps1",
        ),
        (gitignore, backup_dir / ".gitignore"),
    ]

    if counter_test.exists():
        backup_pairs.append(
            (
                counter_test,
                backup_dir / "test_product_counter_persistence.py",
            )
        )

    if counters_json.exists():
        backup_pairs.append(
            (counters_json, backup_dir / "counters.json")
        )

    for source, destination in backup_pairs:
        shutil.copy2(source, destination)

    try:
        patch_main_window(main_window)
        counter_service.write_text(
            COUNTER_SERVICE_SOURCE,
            encoding="utf-8",
        )
        counter_test.parent.mkdir(parents=True, exist_ok=True)
        counter_test.write_text(
            COUNTER_TEST_SOURCE,
            encoding="utf-8",
        )
        patch_regression_script(regression_script)
        patch_gitignore(gitignore)

    except Exception:
        shutil.copy2(
            backup_dir / "main_window.py",
            main_window,
        )
        shutil.copy2(
            backup_dir / "product_counter_service.py",
            counter_service,
        )
        shutil.copy2(
            backup_dir / "run_regression_tests.ps1",
            regression_script,
        )
        shutil.copy2(
            backup_dir / ".gitignore",
            gitignore,
        )
        raise

    print(f"[OK] Đã sửa: {main_window}")
    print(f"[OK] Đã sửa: {counter_service}")
    print(f"[OK] Đã tạo: {counter_test}")
    print(f"[OK] Đã sửa: {regression_script}")
    print(f"[OK] Đã sửa: {gitignore}")
    print(f"[OK] Backup: {backup_dir}")
    print("[OK] Đã xóa toàn bộ nút cộng thử.")
    print("[OK] Bộ đếm tự lưu vào config/counters.json.")
    print("[OK] RESET có hộp xác nhận.")


if __name__ == "__main__":
    main()
