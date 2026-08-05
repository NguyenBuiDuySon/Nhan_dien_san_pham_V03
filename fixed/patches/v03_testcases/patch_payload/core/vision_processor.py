from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.color_repository import ColorRepository
from core.product_detector import ProductDetection, ProductDetector
from core.stability_filter import ColorStabilityFilter, ProductEventLatch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKGROUND_PATH = PROJECT_ROOT / "config" / "background_reference.png"


@dataclass(frozen=True)
class ColorClassification:
    label: str
    best_match: str | None
    confidence: float
    margin: float
    scores: dict[str, float]
    pixel_counts: dict[str, int]
    valid_pixel_count: int
    mask: np.ndarray


@dataclass(frozen=True)
class VisionResult:
    annotated_frame: np.ndarray
    mask: np.ndarray
    instant_label: str
    stable_label: str | None
    confidence: float
    margin: float
    scores: dict[str, float]
    present: bool
    change_ratio: float
    count_event: str | None
    roi_box: tuple[int, int, int, int]
    sample_box: tuple[int, int, int, int]
    yolo_detection: ProductDetection | None

    # counting_ready=False nghĩa là app chỉ đang xem trước màu.
    # Counter và lệnh SORT bị khóa cho đến khi đã lấy nền hoặc YOLO thấy PRODUCT.
    counting_ready: bool
    status_message: str


class ColorEngine:
    """Phân loại màu chiếm ưu thế trong một vùng ảnh BGR."""

    UNKNOWN = "unknown"

    def __init__(
        self,
        min_confidence: float = 0.25,
        min_margin: float = 0.08,
        min_color_pixels: int = 300,
        kernel_size: int = 3,
        blur_kernel_size: int = 1,
    ) -> None:
        self.min_confidence = float(min_confidence)
        self.min_margin = float(min_margin)
        self.min_color_pixels = max(1, int(min_color_pixels))
        self.kernel_size = self._odd_size(kernel_size)
        self.blur_kernel_size = self._odd_size(blur_kernel_size)

    def classify(
        self,
        crop_bgr: np.ndarray,
        colors: dict[str, list[dict[str, list[int]]]],
        valid_mask: np.ndarray | None = None,
    ) -> ColorClassification:
        if crop_bgr is None or crop_bgr.size == 0:
            return self._unknown((1, 1))

        processed = crop_bgr

        if self.blur_kernel_size > 1:
            processed = cv2.GaussianBlur(
                crop_bgr,
                (self.blur_kernel_size, self.blur_kernel_size),
                0,
            )

        hsv_image = cv2.cvtColor(processed, cv2.COLOR_BGR2HSV)
        normalized_valid_mask = self._normalize_valid_mask(hsv_image, valid_mask)
        valid_pixel_count = cv2.countNonZero(normalized_valid_mask)

        if valid_pixel_count <= 0:
            return self._unknown(hsv_image.shape[:2])

        kernel = np.ones(
            (self.kernel_size, self.kernel_size),
            dtype=np.uint8,
        )

        scores: dict[str, float] = {}
        pixel_counts: dict[str, int] = {}
        masks: dict[str, np.ndarray] = {}

        for color_key, ranges in colors.items():
            mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)

            for hsv_range in ranges:
                lower = np.array(hsv_range["lower"], dtype=np.uint8)
                upper = np.array(hsv_range["upper"], dtype=np.uint8)
                mask = cv2.bitwise_or(mask, cv2.inRange(hsv_image, lower, upper))

            if self.kernel_size > 1:
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

            # Chỉ đếm pixel thuộc vùng sản phẩm. Khi có ảnh nền tham chiếu,
            # valid_mask chính là các pixel đã thay đổi so với nền.
            mask = cv2.bitwise_and(mask, normalized_valid_mask)
            pixel_count = cv2.countNonZero(mask)

            pixel_counts[color_key] = pixel_count
            scores[color_key] = pixel_count / valid_pixel_count
            masks[color_key] = mask

        if not scores:
            return self._unknown(hsv_image.shape[:2])

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_match, confidence = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = confidence - second_score

        accepted = (
            pixel_counts[best_match] >= self.min_color_pixels
            and confidence >= self.min_confidence
            and margin >= self.min_margin
        )

        return ColorClassification(
            label=best_match if accepted else self.UNKNOWN,
            best_match=best_match,
            confidence=confidence,
            margin=margin,
            scores=scores,
            pixel_counts=pixel_counts,
            valid_pixel_count=valid_pixel_count,
            mask=masks[best_match],
        )

    @staticmethod
    def _normalize_valid_mask(
        hsv_image: np.ndarray,
        valid_mask: np.ndarray | None,
    ) -> np.ndarray:
        if valid_mask is None:
            return np.full(hsv_image.shape[:2], 255, dtype=np.uint8)

        if valid_mask.shape[:2] != hsv_image.shape[:2]:
            valid_mask = cv2.resize(
                valid_mask,
                (hsv_image.shape[1], hsv_image.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        if valid_mask.ndim == 3:
            valid_mask = cv2.cvtColor(valid_mask, cv2.COLOR_BGR2GRAY)

        _, binary = cv2.threshold(valid_mask, 0, 255, cv2.THRESH_BINARY)
        return binary

    def _unknown(self, shape: tuple[int, int]) -> ColorClassification:
        return ColorClassification(
            label=self.UNKNOWN,
            best_match=None,
            confidence=0.0,
            margin=0.0,
            scores={},
            pixel_counts={},
            valid_pixel_count=0,
            mask=np.zeros(shape, dtype=np.uint8),
        )

    @staticmethod
    def _odd_size(value: Any) -> int:
        try:
            size = max(1, int(value))
        except (TypeError, ValueError):
            size = 1

        if size % 2 == 0:
            size += 1

        return size


class VisionProcessor:
    """Pipeline nhận diện dùng chung cho app.

    Chế độ hiện tại (chưa có YOLO):
        ROI kéo chuột -> Sampling Box -> trừ nền -> HSV -> Stability -> Counter.

    Chế độ sau khi train:
        YOLO product bbox -> HSV -> Stability -> Counter.
    """

    def __init__(
        self,
        config: dict[str, Any],
        color_repository: ColorRepository,
        background_path: Path | None = None,
    ) -> None:
        self.config = config
        self.color_repository = color_repository
        self.background_path = background_path or DEFAULT_BACKGROUND_PATH

        classification = config.get("classification", {})
        self.color_engine = ColorEngine(
            min_confidence=classification.get("min_confidence", 0.25),
            min_margin=classification.get("min_margin", 0.08),
            min_color_pixels=classification.get("min_color_pixels", 300),
            kernel_size=classification.get("kernel_size", 3),
            blur_kernel_size=classification.get("blur_kernel_size", 1),
        )

        stability = config.get("stability", {})
        self.stability_filter = ColorStabilityFilter(
            window_size=stability.get("window_size", 7),
            minimum_votes=stability.get("minimum_votes", 5),
        )
        self.event_latch = ProductEventLatch(
            release_frames=stability.get("release_frames", 5),
        )

        yolo = config.get("yolo", {})
        self.product_detector = ProductDetector(
            enabled=yolo.get("enabled", False),
            confidence=yolo.get("confidence", 0.50),
        )

        self.roi = dict(config.get("roi", {"x": 200, "y": 120, "w": 240, "h": 240}))
        self.sample_ratio = float(config.get("sample_box_ratio", 0.55))

        presence = config.get("presence", {})
        self.background_diff_threshold = int(presence.get("diff_threshold", 25))

        # Ngưỡng vào và ngưỡng rời khác nhau tạo hysteresis:
        # vật đã vào thì không bị nhấp nháy chỉ vì change_ratio dao động nhẹ.
        self.enter_change_ratio = float(
            presence.get(
                "enter_change_ratio",
                presence.get("min_change_ratio", 0.08),
            )
        )
        self.exit_change_ratio = float(
            presence.get(
                "exit_change_ratio",
                max(0.0, self.enter_change_ratio * 0.50),
            )
        )
        self.require_background = bool(presence.get("require_background", True))
        self.presence_kernel_size = max(1, int(presence.get("kernel_size", 5)))

        if self.presence_kernel_size % 2 == 0:
            self.presence_kernel_size += 1

        self.background_reference: np.ndarray | None = None
        self._presence_latched = False
        self.load_background_reference()

    def reload_colors(self) -> None:
        self.color_repository.load()
        self.reset_tracking()

    def set_roi(self, roi: dict[str, int]) -> None:
        self.roi = {
            "x": int(roi.get("x", 0)),
            "y": int(roi.get("y", 0)),
            "w": max(20, int(roi.get("w", 20))),
            "h": max(20, int(roi.get("h", 20))),
        }

        # ROI thay đổi làm kích thước Sampling Box thay đổi, vì vậy ảnh nền cũ
        # không còn cùng tọa độ. Người dùng cần bấm LẤY NỀN lại.
        self.background_reference = None
        self.reset_tracking()

    def get_roi(self) -> dict[str, int]:
        return dict(self.roi)

    def reset_tracking(self) -> None:
        self.stability_filter.reset()
        self.event_latch.reset()
        self._presence_latched = False

    def get_sample_crop(self, frame_bgr: np.ndarray | None) -> np.ndarray | None:
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        _, sample_box = self._resolve_boxes(frame_bgr, None)
        x1, y1, x2, y2 = sample_box
        return frame_bgr[y1:y2, x1:x2].copy()

    def capture_background(self, frame_bgr: np.ndarray) -> tuple[bool, str]:
        sample_crop = self.get_sample_crop(frame_bgr)

        if sample_crop is None or sample_crop.size == 0:
            return False, "Không lấy được Sampling Box để lưu nền."

        self.background_reference = sample_crop.copy()
        self.background_path.parent.mkdir(parents=True, exist_ok=True)

        saved = cv2.imwrite(str(self.background_path), self.background_reference)

        if not saved:
            return False, "Không lưu được ảnh nền tham chiếu."

        self.reset_tracking()
        return True, "Đã lưu nền tham chiếu. Hãy đặt sản phẩm vào vùng giữa ROI."

    def clear_background(self) -> None:
        self.background_reference = None

        try:
            self.background_path.unlink(missing_ok=True)
        except OSError:
            pass

        self.reset_tracking()

    def load_background_reference(self) -> None:
        if not self.background_path.exists():
            return

        image = cv2.imread(str(self.background_path))

        if image is not None and image.size > 0:
            self.background_reference = image

    def process(self, frame_bgr: np.ndarray) -> VisionResult:
        annotated = frame_bgr.copy()
        roi_box = self._clamp_roi(frame_bgr)
        yolo_detection = self._select_yolo_detection(frame_bgr, roi_box)
        analysis_box, sample_box = self._resolve_boxes(frame_bgr, yolo_detection)

        sx1, sy1, sx2, sy2 = sample_box
        sample_crop = frame_bgr[sy1:sy2, sx1:sx2]

        foreground_mask, background_present, change_ratio = self._build_foreground_mask(
            sample_crop
        )

        # Khi YOLO đã phát hiện PRODUCT thì bbox chính là bằng chứng có sản phẩm.
        # Khi chưa có YOLO, nền tham chiếu là cổng bắt buộc để tránh đếm mặt bàn
        # hoặc băng tải thành một màu hợp lệ.
        yolo_present = yolo_detection is not None
        background_ready = self.background_reference is not None
        counting_ready = yolo_present or background_ready or not self.require_background

        if yolo_present:
            present = True
            valid_mask = None
            status_message = "YOLO PRODUCT"
        elif background_ready:
            present = background_present
            valid_mask = foreground_mask
            status_message = "PRODUCT PRESENT" if present else "WAITING"
        elif self.require_background:
            present = False
            valid_mask = None
            status_message = "BACKGROUND REQUIRED"
        else:
            # Chế độ kỹ thuật: cho phép xem trước màu khi chưa lấy nền,
            # nhưng chỉ nên dùng để hiệu chỉnh, không dùng cho vận hành thật.
            present = False
            valid_mask = None
            status_message = "PREVIEW ONLY"

        classification = self.color_engine.classify(
            sample_crop,
            self.color_repository.get_detection_config(),
            valid_mask=valid_mask,
        )

        if counting_ready and present:
            instant_label = classification.label
            stable_label = self.stability_filter.update(instant_label)
            count_event = self.event_latch.update(True, stable_label)
        else:
            # Không có sản phẩm hoặc hệ thống chưa sẵn sàng:
            # xóa lịch sử để nền không thể tích lũy phiếu rồi phát sinh sự kiện đếm.
            instant_label = ColorEngine.UNKNOWN
            stable_label = None
            count_event = self.event_latch.update(False, None)
            self.stability_filter.reset()

        self._draw_overlay(
            annotated,
            roi_box=roi_box,
            analysis_box=analysis_box,
            sample_box=sample_box,
            classification=classification,
            stable_label=stable_label,
            present=present,
            change_ratio=change_ratio,
            yolo_detection=yolo_detection,
            counting_ready=counting_ready,
            status_message=status_message,
        )

        return VisionResult(
            annotated_frame=annotated,
            mask=classification.mask,
            instant_label=instant_label,
            stable_label=stable_label,
            confidence=classification.confidence,
            margin=classification.margin,
            scores=classification.scores,
            present=present,
            change_ratio=change_ratio,
            count_event=count_event,
            roi_box=roi_box,
            sample_box=sample_box,
            yolo_detection=yolo_detection,
            counting_ready=counting_ready,
            status_message=status_message,
        )

    def _build_foreground_mask(
        self,
        sample_crop: np.ndarray,
    ) -> tuple[np.ndarray, bool, float]:
        shape = sample_crop.shape[:2]

        if self.background_reference is None:
            return np.full(shape, 255, dtype=np.uint8), False, 0.0

        reference = self.background_reference

        if reference.shape[:2] != sample_crop.shape[:2]:
            # Tránh resize nền vì có thể tạo sai lệch giả. Yêu cầu lấy nền lại.
            self.background_reference = None
            return np.full(shape, 255, dtype=np.uint8), False, 0.0

        current_blur = cv2.GaussianBlur(sample_crop, (5, 5), 0)
        reference_blur = cv2.GaussianBlur(reference, (5, 5), 0)
        difference = cv2.absdiff(current_blur, reference_blur)
        difference_gray = cv2.cvtColor(difference, cv2.COLOR_BGR2GRAY)

        _, foreground = cv2.threshold(
            difference_gray,
            self.background_diff_threshold,
            255,
            cv2.THRESH_BINARY,
        )

        kernel = np.ones(
            (self.presence_kernel_size, self.presence_kernel_size),
            dtype=np.uint8,
        )
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel)
        foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel)

        changed_pixels = cv2.countNonZero(foreground)
        total_pixels = max(1, foreground.shape[0] * foreground.shape[1])
        change_ratio = changed_pixels / total_pixels

        # Hysteresis hiện diện:
        # - Khi đang trống, phải vượt ngưỡng vào.
        # - Khi đã có vật, chỉ nhả trạng thái khi xuống dưới ngưỡng rời.
        if self._presence_latched:
            if change_ratio <= self.exit_change_ratio:
                self._presence_latched = False
        elif change_ratio >= self.enter_change_ratio:
            self._presence_latched = True

        return foreground, self._presence_latched, change_ratio

    def _select_yolo_detection(
        self,
        frame_bgr: np.ndarray,
        roi_box: tuple[int, int, int, int],
    ) -> ProductDetection | None:
        if not self.product_detector.enabled or not self.product_detector.ready:
            return None

        detections = self.product_detector.detect(frame_bgr)
        rx1, ry1, rx2, ry2 = roi_box
        candidates: list[ProductDetection] = []

        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2

            if rx1 <= center_x <= rx2 and ry1 <= center_y <= ry2:
                candidates.append(detection)

        if not candidates:
            return None

        return max(candidates, key=lambda item: item.confidence)

    def _resolve_boxes(
        self,
        frame_bgr: np.ndarray,
        yolo_detection: ProductDetection | None,
    ) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        if yolo_detection is not None:
            analysis_box = self._clamp_box(frame_bgr, yolo_detection.bbox)
            sample_box = self._inner_box(analysis_box, ratio=0.80)
            return analysis_box, sample_box

        analysis_box = self._clamp_roi(frame_bgr)
        sample_box = self._inner_box(analysis_box, ratio=self.sample_ratio)
        return analysis_box, sample_box

    def _clamp_roi(self, frame_bgr: np.ndarray) -> tuple[int, int, int, int]:
        x = int(self.roi.get("x", 0))
        y = int(self.roi.get("y", 0))
        width = int(self.roi.get("w", 100))
        height = int(self.roi.get("h", 100))
        return self._clamp_box(frame_bgr, (x, y, x + width, y + height))

    @staticmethod
    def _clamp_box(
        frame_bgr: np.ndarray,
        box: tuple[int, int, int, int],
    ) -> tuple[int, int, int, int]:
        frame_height, frame_width = frame_bgr.shape[:2]
        x1, y1, x2, y2 = box

        x1 = max(0, min(int(x1), frame_width - 2))
        y1 = max(0, min(int(y1), frame_height - 2))
        x2 = max(x1 + 2, min(int(x2), frame_width))
        y2 = max(y1 + 2, min(int(y2), frame_height))

        return x1, y1, x2, y2

    @staticmethod
    def _inner_box(
        box: tuple[int, int, int, int],
        ratio: float,
    ) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = box
        width = x2 - x1
        height = y2 - y1
        safe_ratio = min(max(float(ratio), 0.10), 1.0)

        inner_width = max(10, int(width * safe_ratio))
        inner_height = max(10, int(height * safe_ratio))
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2

        sx1 = center_x - inner_width // 2
        sy1 = center_y - inner_height // 2
        sx2 = sx1 + inner_width
        sy2 = sy1 + inner_height

        return sx1, sy1, sx2, sy2

    def _draw_overlay(
        self,
        frame: np.ndarray,
        roi_box: tuple[int, int, int, int],
        analysis_box: tuple[int, int, int, int],
        sample_box: tuple[int, int, int, int],
        classification: ColorClassification,
        stable_label: str | None,
        present: bool,
        change_ratio: float,
        yolo_detection: ProductDetection | None,
        counting_ready: bool,
        status_message: str,
    ) -> None:
        rx1, ry1, rx2, ry2 = roi_box
        ax1, ay1, ax2, ay2 = analysis_box
        sx1, sy1, sx2, sy2 = sample_box

        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (0, 255, 255), 2)
        cv2.putText(
            frame,
            "ROI",
            (rx1, max(20, ry1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 255),
            2,
        )

        if yolo_detection is not None:
            cv2.rectangle(frame, (ax1, ay1), (ax2, ay2), (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"PRODUCT {yolo_detection.confidence:.2f}",
                (ax1, max(20, ay1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (0, 255, 0),
                2,
            )

        sample_color = (255, 0, 0) if present else (0, 0, 255)
        cv2.rectangle(frame, (sx1, sy1), (sx2, sy2), sample_color, 2)
        cv2.putText(
            frame,
            "SAMPLE",
            (sx1, max(20, sy1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            sample_color,
            2,
        )

        if not counting_ready:
            instant_text = "UNKNOWN"
            stable_text = status_message
        elif not present:
            instant_text = "UNKNOWN"
            stable_text = "WAITING"
        else:
            instant_text = classification.label.upper()
            stable_text = stable_label.upper() if stable_label else "WAITING"

        cv2.putText(
            frame,
            f"COLOR: {instant_text} | STABLE: {stable_text}",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0) if instant_text != "UNKNOWN" else (0, 0, 255),
            2,
        )
        cv2.putText(
            frame,
            (
                f"conf={classification.confidence:.3f} "
                f"margin={classification.margin:.3f} "
                f"change={change_ratio:.3f}"
            ),
            (15, 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1,
        )
