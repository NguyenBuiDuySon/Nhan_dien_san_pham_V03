from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "vision_config.json"
COLORS_PATH = PROJECT_DIR / "colors.json"

WINDOW_NAME = "Vision V2 - Color Detection"
MASK_WINDOW_NAME = "Vision V2 - Best Mask"

dragging = False
drag_start = (0, 0)
drag_current = (0, 0)
roi_config: dict[str, int] = {}


def load_json(file_path: Path) -> dict:
    """Đọc file JSON và trả về dictionary."""
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(file_path: Path, data: dict) -> None:
    """Lưu dictionary vào file JSON."""
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def handle_mouse(event: int, x: int, y: int, flags: int, param) -> None:
    """Cập nhật ROI khi kéo chuột trái."""
    global dragging, drag_start, drag_current, roi_config

    if event == cv2.EVENT_LBUTTONDOWN:
        dragging = True
        drag_start = (x, y)
        drag_current = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE and dragging:
        drag_current = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False
        drag_current = (x, y)

        x1 = min(drag_start[0], drag_current[0])
        y1 = min(drag_start[1], drag_current[1])
        x2 = max(drag_start[0], drag_current[0])
        y2 = max(drag_start[1], drag_current[1])

        width = x2 - x1
        height = y2 - y1

        if width < 20 or height < 20:
            return

        roi_config["x"] = x1
        roi_config["y"] = y1
        roi_config["w"] = width
        roi_config["h"] = height

        print("ROI mới:", roi_config)


def clamp_roi(frame: np.ndarray) -> tuple[int, int, int, int]:
    """Giữ ROI nằm bên trong frame."""
    frame_height, frame_width = frame.shape[:2]

    x = max(0, int(roi_config.get("x", 0)))
    y = max(0, int(roi_config.get("y", 0)))
    width = max(20, int(roi_config.get("w", 100)))
    height = max(20, int(roi_config.get("h", 100)))

    x = min(x, frame_width - 20)
    y = min(y, frame_height - 20)

    x2 = min(x + width, frame_width)
    y2 = min(y + height, frame_height)

    return x, y, x2, y2


def create_color_mask(
    hsv_image: np.ndarray,
    ranges: list[dict],
    kernel: np.ndarray,
) -> np.ndarray:
    """Tạo mask chung từ các khoảng HSV của một màu."""
    total_mask = np.zeros(hsv_image.shape[:2], dtype=np.uint8)

    for color_range in ranges:
        lower = np.array(color_range["lower"], dtype=np.uint8)
        upper = np.array(color_range["upper"], dtype=np.uint8)

        range_mask = cv2.inRange(hsv_image, lower, upper)
        total_mask = cv2.bitwise_or(total_mask, range_mask)

    total_mask = cv2.morphologyEx(
        total_mask,
        cv2.MORPH_OPEN,
        kernel,
    )

    total_mask = cv2.morphologyEx(
        total_mask,
        cv2.MORPH_CLOSE,
        kernel,
    )

    return total_mask


def classify_color(
    product_crop: np.ndarray,
    colors: dict,
    classification_config: dict,
) -> dict:
    """Xác định màu chiếm ưu thế trong vùng ảnh sản phẩm."""
    if product_crop is None or product_crop.size == 0:
        return {
            "label": "unknown",
            "best_match": None,
            "confidence": 0.0,
            "margin": 0.0,
            "scores": {},
            "best_mask": None,
        }

    hsv_image = cv2.cvtColor(product_crop, cv2.COLOR_BGR2HSV)

    kernel_size = max(
        1,
        int(classification_config.get("kernel_size", 3)),
    )

    if kernel_size % 2 == 0:
        kernel_size += 1

    kernel = np.ones(
        (kernel_size, kernel_size),
        dtype=np.uint8,
    )

    total_pixels = product_crop.shape[0] * product_crop.shape[1]

    scores: dict[str, float] = {}
    masks: dict[str, np.ndarray] = {}
    pixel_counts: dict[str, int] = {}

    for color_name, ranges in colors.items():
        mask = create_color_mask(
            hsv_image,
            ranges,
            kernel,
        )

        pixel_count = cv2.countNonZero(mask)
        score = pixel_count / total_pixels

        scores[color_name] = score
        masks[color_name] = mask
        pixel_counts[color_name] = pixel_count

    ranked_colors = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_match, confidence = ranked_colors[0]
    second_score = ranked_colors[1][1] if len(ranked_colors) > 1 else 0.0
    margin = confidence - second_score

    min_confidence = float(
        classification_config.get("min_confidence", 0.25)
    )
    min_margin = float(
        classification_config.get("min_margin", 0.08)
    )
    min_color_pixels = int(
        classification_config.get("min_color_pixels", 300)
    )

    accepted = (
        confidence >= min_confidence
        and margin >= min_margin
        and pixel_counts[best_match] >= min_color_pixels
    )

    return {
        "label": best_match if accepted else "unknown",
        "best_match": best_match,
        "confidence": confidence,
        "margin": margin,
        "scores": scores,
        "best_mask": masks[best_match],
    }


def draw_result(
    frame: np.ndarray,
    roi_box: tuple[int, int, int, int],
    result: dict,
    debug_mode: bool,
) -> None:
    """Vẽ ROI và kết quả lên frame."""
    x1, y1, x2, y2 = roi_box

    is_unknown = result["label"] == "unknown"
    box_color = (0, 0, 255) if is_unknown else (0, 255, 0)

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        box_color,
        2,
    )

    cv2.putText(
        frame,
        f"COLOR: {result['label'].upper()}",
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        box_color,
        2,
    )

    cv2.putText(
        frame,
        f"conf={result['confidence']:.3f}  margin={result['margin']:.3f}",
        (20, 65),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
    )

    if debug_mode:
        ranked_scores = sorted(
            result["scores"].items(),
            key=lambda item: item[1],
            reverse=True,
        )

        for index, (color_name, score) in enumerate(ranked_scores):
            cv2.putText(
                frame,
                f"{color_name.upper()}: {score:.3f}",
                (20, 95 + index * 22),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.50,
                (255, 255, 255),
                1,
            )

        cv2.putText(
            frame,
            "Drag ROI | P: save | R: reload | T: debug | Q: quit",
            (10, frame.shape[0] - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1,
        )

    if dragging:
        cv2.rectangle(
            frame,
            drag_start,
            drag_current,
            (255, 0, 0),
            2,
        )


def main() -> None:
    global roi_config

    config = load_json(CONFIG_PATH)
    colors = load_json(COLORS_PATH)

    camera_config = config["camera"]
    roi_config = config["roi"]
    classification_config = config["classification"]
    ui_config = config.setdefault("ui", {"debug": True})

    camera_id = int(camera_config.get("id", 0))
    frame_width = int(camera_config.get("width", 640))
    frame_height = int(camera_config.get("height", 480))

    camera = cv2.VideoCapture(camera_id)

    if not camera.isOpened():
        raise RuntimeError(
            f"Không thể mở camera có ID = {camera_id}"
        )

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, handle_mouse)

    print("Vision V2 đã chạy")
    print("Kéo chuột: chọn ROI")
    print("P: lưu ROI")
    print("R: reload colors.json")
    print("T: bật/tắt debug")
    print("Q: thoát")

    try:
        while True:
            success, frame = camera.read()

            if not success or frame is None:
                raise RuntimeError(
                    "Không thể đọc frame từ camera"
                )

            frame = cv2.resize(
                frame,
                (frame_width, frame_height),
                interpolation=cv2.INTER_AREA,
            )

            x1, y1, x2, y2 = clamp_roi(frame)

            # Hiện tại ROI kéo bằng chuột đóng vai trò product_crop.
            # Khi thêm YOLO, chỉ thay bằng bbox do model trả về.
            product_crop = frame[y1:y2, x1:x2]

            result = classify_color(
                product_crop,
                colors,
                classification_config,
            )

            debug_mode = bool(ui_config.get("debug", True))

            draw_result(
                frame,
                (x1, y1, x2, y2),
                result,
                debug_mode,
            )

            cv2.imshow(WINDOW_NAME, frame)

            if debug_mode and result["best_mask"] is not None:
                cv2.imshow(
                    MASK_WINDOW_NAME,
                    result["best_mask"],
                )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("p"):
                config["roi"] = roi_config
                save_json(CONFIG_PATH, config)
                print("Đã lưu ROI:", roi_config)

            elif key == ord("r"):
                colors = load_json(COLORS_PATH)
                print("Đã reload colors.json")

            elif key == ord("t"):
                ui_config["debug"] = not debug_mode
                mode_name = "DEBUG" if ui_config["debug"] else "OPERATOR"
                print("Chế độ:", mode_name)

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Đã đóng camera")


if __name__ == "__main__":
    main()
