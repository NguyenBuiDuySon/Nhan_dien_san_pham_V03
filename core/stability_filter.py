from __future__ import annotations

from collections import Counter, deque


class ColorStabilityFilter:
    """Xác nhận màu bằng bỏ phiếu trên nhiều frame gần nhất.

    Ví dụ cửa sổ 7 frame, cần 5 phiếu:
    RED, RED, UNKNOWN, RED, RED, YELLOW, RED -> ổn định RED.
    """

    def __init__(self, window_size: int = 7, minimum_votes: int = 5) -> None:
        self.window_size = max(1, int(window_size))
        self.minimum_votes = max(1, min(int(minimum_votes), self.window_size))
        self.history: deque[str] = deque(maxlen=self.window_size)

    def update(self, label: str | None) -> str | None:
        normalized = (label or "unknown").strip().lower()
        self.history.append(normalized)

        valid_labels = [item for item in self.history if item != "unknown"]

        if not valid_labels:
            return None

        label_counts = Counter(valid_labels)
        best_label, votes = label_counts.most_common(1)[0]

        if votes < self.minimum_votes:
            return None

        return best_label

    def reset(self) -> None:
        self.history.clear()


class ProductEventLatch:
    """Bảo đảm một sản phẩm chỉ được đếm đúng một lần.

    Sau khi đã đếm, hệ thống phải thấy vùng kiểm tra trống liên tiếp một số
    frame thì mới mở khóa cho sản phẩm tiếp theo.
    """

    def __init__(self, release_frames: int = 5) -> None:
        self.release_frames = max(1, int(release_frames))
        self.latched = False
        self.absent_frames = 0

    def update(self, present: bool, stable_label: str | None) -> str | None:
        if not present:
            self.absent_frames += 1

            if self.absent_frames >= self.release_frames:
                self.latched = False

            return None

        self.absent_frames = 0

        if self.latched or stable_label is None:
            return None

        self.latched = True
        return stable_label

    def reset(self) -> None:
        self.latched = False
        self.absent_frames = 0
