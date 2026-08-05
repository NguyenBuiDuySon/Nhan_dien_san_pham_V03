from __future__ import annotations

from typing import Callable

import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.color_repository import ColorRepository


class ColorCalibratorDialog(QDialog):
    """Cửa sổ thêm/sửa/xóa màu bằng sáu thanh trượt HSV.

    ``sample_provider`` trả về ảnh Sampling Box mới nhất từ camera. Nhờ vậy
    người dùng vừa kéo ROI ở màn hình chính, vừa quan sát mask trực tiếp trong
    hộp hiệu chỉnh mà không phải mở thêm camera lần thứ hai.
    """

    colors_changed = Signal()

    def __init__(
        self,
        repository: ColorRepository,
        sample_provider: Callable[[], np.ndarray | None],
        suggested_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.sample_provider = sample_provider
        self.suggested_name = suggested_name.strip()

        self.setWindowTitle("Hiệu chỉnh màu HSV")
        self.resize(940, 620)

        self.sliders: dict[str, QSlider] = {}
        self.spin_boxes: dict[str, QSpinBox] = {}

        root_layout = QHBoxLayout(self)
        control_panel = self._build_control_panel()
        preview_panel = self._build_preview_panel()

        root_layout.addWidget(control_panel, 2)
        root_layout.addWidget(preview_panel, 3)

        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(100)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.preview_timer.start()

        self.reload_color_list()

        if self.suggested_name:
            suggested_key = self.repository.normalize_key(self.suggested_name)
            index = self.color_combo.findData(suggested_key)

            if index >= 0:
                self.color_combo.setCurrentIndex(index)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel("Màu đang chỉnh:"))
        self.color_combo = QComboBox()
        self.color_combo.currentIndexChanged.connect(self.handle_color_changed)
        layout.addWidget(self.color_combo)

        layout.addWidget(QLabel("Khoảng HSV:"))
        self.range_combo = QComboBox()
        self.range_combo.currentIndexChanged.connect(self.load_selected_range)
        layout.addWidget(self.range_combo)

        slider_grid = QGridLayout()
        self._add_slider(slider_grid, 0, "low_h", "Low H", 0, 179)
        self._add_slider(slider_grid, 1, "high_h", "High H", 0, 179)
        self._add_slider(slider_grid, 2, "low_s", "Low S", 0, 255)
        self._add_slider(slider_grid, 3, "high_s", "High S", 0, 255)
        self._add_slider(slider_grid, 4, "low_v", "Low V", 0, 255)
        self._add_slider(slider_grid, 5, "high_v", "High V", 0, 255)
        layout.addLayout(slider_grid)

        self.status_label = QLabel("Đặt sản phẩm vào Sampling Box rồi điều chỉnh HSV.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #94a3b8;")
        layout.addWidget(self.status_label)

        button_grid = QGridLayout()

        self.btn_auto_sample = QPushButton("LẤY DẢI TỪ MẪU")
        self.btn_save_range = QPushButton("LƯU DẢI HIỆN TẠI")
        self.btn_new_color = QPushButton("THÊM MÀU MỚI")
        self.btn_add_range = QPushButton("THÊM DẢI HSV")
        self.btn_delete_range = QPushButton("XÓA DẢI")
        self.btn_delete_color = QPushButton("XÓA MÀU")
        self.btn_reload = QPushButton("ĐỌC LẠI FILE")
        self.btn_close = QPushButton("ĐÓNG")

        button_grid.addWidget(self.btn_auto_sample, 0, 0, 1, 2)
        button_grid.addWidget(self.btn_save_range, 1, 0, 1, 2)
        button_grid.addWidget(self.btn_new_color, 2, 0)
        button_grid.addWidget(self.btn_add_range, 2, 1)
        button_grid.addWidget(self.btn_delete_range, 3, 0)
        button_grid.addWidget(self.btn_delete_color, 3, 1)
        button_grid.addWidget(self.btn_reload, 4, 0)
        button_grid.addWidget(self.btn_close, 4, 1)
        layout.addLayout(button_grid)
        layout.addStretch()

        self.btn_auto_sample.clicked.connect(self.estimate_range_from_sample)
        self.btn_save_range.clicked.connect(self.save_current_range)
        self.btn_new_color.clicked.connect(self.add_new_color)
        self.btn_add_range.clicked.connect(self.add_new_range)
        self.btn_delete_range.clicked.connect(self.delete_current_range)
        self.btn_delete_color.clicked.connect(self.delete_current_color)
        self.btn_reload.clicked.connect(self.reload_repository)
        self.btn_close.clicked.connect(self.accept)

        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.original_preview = self._create_preview_label("ẢNH MẪU")
        self.mask_preview = self._create_preview_label("MASK")
        self.result_preview = self._create_preview_label("KẾT QUẢ LỌC MÀU")

        layout.addWidget(self.original_preview, 1)
        layout.addWidget(self.mask_preview, 1)
        layout.addWidget(self.result_preview, 1)
        return panel

    @staticmethod
    def _create_preview_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumHeight(150)
        label.setStyleSheet(
            "background-color: #020617; color: #64748b; "
            "border: 1px solid #334155; border-radius: 8px;"
        )
        return label

    def _add_slider(
        self,
        layout: QGridLayout,
        row: int,
        key: str,
        title: str,
        minimum: int,
        maximum: int,
    ) -> None:
        label = QLabel(title)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        spin_box = QSpinBox()
        spin_box.setRange(minimum, maximum)
        spin_box.setFixedWidth(72)

        slider.valueChanged.connect(spin_box.setValue)
        spin_box.valueChanged.connect(slider.setValue)

        self.sliders[key] = slider
        self.spin_boxes[key] = spin_box

        layout.addWidget(label, row, 0)
        layout.addWidget(slider, row, 1)
        layout.addWidget(spin_box, row, 2)

    def reload_color_list(self, selected_key: str | None = None) -> None:
        self.color_combo.blockSignals(True)
        self.color_combo.clear()

        for color_key in self.repository.color_keys():
            self.color_combo.addItem(
                self.repository.get_display_name(color_key),
                color_key,
            )

        self.color_combo.blockSignals(False)

        if selected_key:
            index = self.color_combo.findData(selected_key)
            self.color_combo.setCurrentIndex(max(0, index))
        elif self.color_combo.count() > 0:
            self.color_combo.setCurrentIndex(0)

        self.handle_color_changed()

    def handle_color_changed(self) -> None:
        color_key = self.current_color_key()
        self.range_combo.blockSignals(True)
        self.range_combo.clear()

        if color_key:
            profile = self.repository.get_profile(color_key)

            for index, _ in enumerate(profile["ranges"]):
                self.range_combo.addItem(f"Dải {index + 1}", index)

        self.range_combo.blockSignals(False)

        if self.range_combo.count() > 0:
            self.range_combo.setCurrentIndex(0)
            self.load_selected_range()

    def load_selected_range(self) -> None:
        color_key = self.current_color_key()
        range_index = self.current_range_index()

        if color_key is None or range_index is None:
            return

        profile = self.repository.get_profile(color_key)
        hsv_range = profile["ranges"][range_index]
        lower = hsv_range["lower"]
        upper = hsv_range["upper"]

        values = {
            "low_h": lower[0],
            "low_s": lower[1],
            "low_v": lower[2],
            "high_h": upper[0],
            "high_s": upper[1],
            "high_v": upper[2],
        }

        for key, value in values.items():
            self.sliders[key].setValue(int(value))

    def current_color_key(self) -> str | None:
        data = self.color_combo.currentData()
        return str(data) if data else None

    def current_range_index(self) -> int | None:
        data = self.range_combo.currentData()
        return int(data) if data is not None else None

    def current_hsv_range(self) -> dict[str, list[int]]:
        return {
            "lower": [
                self.sliders["low_h"].value(),
                self.sliders["low_s"].value(),
                self.sliders["low_v"].value(),
            ],
            "upper": [
                self.sliders["high_h"].value(),
                self.sliders["high_s"].value(),
                self.sliders["high_v"].value(),
            ],
        }

    def estimate_range_from_sample(self) -> None:
        sample = self.sample_provider()

        if sample is None or sample.size == 0:
            self._set_status("Chưa có ảnh mẫu. Hãy bật camera và đặt vật vào Sampling Box.", error=True)
            return

        hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
        pixels = hsv.reshape(-1, 3)

        # Bỏ pixel quá xám hoặc quá tối vì chúng không đại diện tốt cho màu vật.
        valid = pixels[(pixels[:, 1] >= 35) & (pixels[:, 2] >= 35)]

        if len(valid) < 20:
            self._set_status("Không đủ pixel màu hợp lệ trong Sampling Box.", error=True)
            return

        low = np.percentile(valid, 3, axis=0)
        high = np.percentile(valid, 97, axis=0)
        hue_median = float(np.median(valid[:, 0]))

        low_h = int(max(0, low[0] - 4))
        high_h = int(min(179, high[0] + 4))

        # Hue đỏ nằm sát biên 0/179. Dải tự động chỉ lấy một phía;
        # người dùng có thể bấm THÊM DẢI HSV để thêm phía còn lại.
        if hue_median <= 15:
            low_h = 0
            high_h = min(25, high_h)
        elif hue_median >= 165:
            low_h = max(155, low_h)
            high_h = 179

        estimated = {
            "low_h": low_h,
            "high_h": high_h,
            "low_s": int(max(0, low[1] - 25)),
            "high_s": int(min(255, high[1] + 15)),
            "low_v": int(max(0, low[2] - 30)),
            "high_v": int(min(255, high[2] + 20)),
        }

        for key, value in estimated.items():
            self.sliders[key].setValue(value)

        self._set_status("Đã ước lượng dải HSV. Kiểm tra mask rồi bấm LƯU DẢI.")

    def save_current_range(self) -> None:
        color_key = self.current_color_key()
        range_index = self.current_range_index()

        if color_key is None or range_index is None:
            return

        try:
            self.repository.update_range(
                color_key,
                range_index,
                self.current_hsv_range(),
            )
        except Exception as error:
            self._set_status(str(error), error=True)
            return

        self.colors_changed.emit()
        self._set_status("Đã lưu dải HSV hiện tại.")

    def add_new_color(self) -> None:
        default_name = self.suggested_name or ""
        display_name, accepted = QInputDialog.getText(
            self,
            "Thêm màu mới",
            "Tên màu:",
            text=default_name,
        )

        if not accepted or not display_name.strip():
            return

        try:
            color_key = self.repository.add_color(
                display_name,
                self.current_hsv_range(),
            )
        except Exception as error:
            self._set_status(str(error), error=True)
            return

        self.reload_color_list(selected_key=color_key)
        self.colors_changed.emit()
        self._set_status(f"Đã thêm màu {display_name.strip().upper()}.")

    def add_new_range(self) -> None:
        color_key = self.current_color_key()

        if color_key is None:
            return

        try:
            new_index = self.repository.add_range(
                color_key,
                self.current_hsv_range(),
            )
        except Exception as error:
            self._set_status(str(error), error=True)
            return

        self.handle_color_changed()
        self.range_combo.setCurrentIndex(new_index)
        self.colors_changed.emit()
        self._set_status("Đã thêm một dải HSV mới cho màu.")

    def delete_current_range(self) -> None:
        color_key = self.current_color_key()
        range_index = self.current_range_index()

        if color_key is None or range_index is None:
            return

        answer = QMessageBox.question(
            self,
            "Xóa dải HSV",
            "Xóa dải HSV đang chọn?",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.repository.delete_range(color_key, range_index)
        except Exception as error:
            self._set_status(str(error), error=True)
            return

        self.handle_color_changed()
        self.colors_changed.emit()
        self._set_status("Đã xóa dải HSV.")

    def delete_current_color(self) -> None:
        color_key = self.current_color_key()

        if color_key is None:
            return

        display_name = self.repository.get_display_name(color_key)
        answer = QMessageBox.question(
            self,
            "Xóa màu",
            f"Xóa toàn bộ màu {display_name}?",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.repository.delete_color(color_key)
        except Exception as error:
            self._set_status(str(error), error=True)
            return

        self.reload_color_list()
        self.colors_changed.emit()
        self._set_status(f"Đã xóa màu {display_name}.")

    def reload_repository(self) -> None:
        self.repository.load()
        self.reload_color_list()
        self.colors_changed.emit()
        self._set_status("Đã đọc lại config/colors.json.")

    def refresh_preview(self) -> None:
        sample = self.sample_provider()

        if sample is None or sample.size == 0:
            return

        hsv = cv2.cvtColor(sample, cv2.COLOR_BGR2HSV)
        current_range = self.current_hsv_range()
        lower = np.array(current_range["lower"], dtype=np.uint8)
        upper = np.array(current_range["upper"], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        kernel = np.ones((3, 3), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        result = cv2.bitwise_and(sample, sample, mask=mask)

        self._show_bgr(self.original_preview, sample)
        self._show_gray(self.mask_preview, mask)
        self._show_bgr(self.result_preview, result)

    def _show_bgr(self, label: QLabel, image_bgr: np.ndarray) -> None:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        qimage = QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        )
        self._set_scaled_pixmap(label, QPixmap.fromImage(qimage.copy()))

    def _show_gray(self, label: QLabel, image_gray: np.ndarray) -> None:
        height, width = image_gray.shape
        qimage = QImage(
            image_gray.data,
            width,
            height,
            width,
            QImage.Format.Format_Grayscale8,
        )
        self._set_scaled_pixmap(label, QPixmap.fromImage(qimage.copy()))

    @staticmethod
    def _set_scaled_pixmap(label: QLabel, pixmap: QPixmap) -> None:
        label.setPixmap(
            pixmap.scaled(
                label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _set_status(self, message: str, error: bool = False) -> None:
        color = "#ef4444" if error else "#22c55e"
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: 700;")
