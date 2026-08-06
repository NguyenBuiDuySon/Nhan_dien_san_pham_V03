# Regression test cho bộ đếm sản xuất lưu qua lần mở app.

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
