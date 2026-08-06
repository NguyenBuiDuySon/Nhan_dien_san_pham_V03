from __future__ import annotations

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
