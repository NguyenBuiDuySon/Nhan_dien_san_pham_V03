from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class ProductCounterService:
    """Bộ đếm động theo danh sách màu trong ``config/colors.json``."""

    counts: dict[str, int] = field(default_factory=lambda: {"error": 0})

    def __init__(self, color_keys: Iterable[str] | None = None) -> None:
        self.counts = {"error": 0}
        self.configure_keys(color_keys or ["red", "green", "blue"])

    def configure_keys(self, color_keys: Iterable[str]) -> None:
        """Đồng bộ key màu nhưng giữ lại số đếm của các màu còn tồn tại."""
        old_counts = dict(self.counts)
        new_counts: dict[str, int] = {}

        for raw_key in color_keys:
            key = str(raw_key).strip().lower()

            if key and key != "error":
                new_counts[key] = int(old_counts.get(key, 0))

        new_counts["error"] = int(old_counts.get("error", 0))
        self.counts = new_counts

    def increment(self, key: str) -> int:
        normalized = key.strip().lower()

        if normalized not in self.counts:
            normalized = "error"

        self.counts[normalized] += 1
        return self.counts[normalized]

    def reset(self) -> None:
        for key in self.counts:
            self.counts[key] = 0

    def snapshot(self) -> dict[str, int]:
        return dict(self.counts)
