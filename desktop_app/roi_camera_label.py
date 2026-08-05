from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel


class ROICameraLabel(QLabel):
    """QLabel hiển thị camera và cho phép kéo ROI trực tiếp bằng chuột."""

    roi_changed = Signal(dict)

    def __init__(self, text: str = "") -> None:
        super().__init__(text)
        self.setMouseTracking(True)

        self._frame_width = 0
        self._frame_height = 0
        self._dragging = False
        self._drag_start = QPoint()
        self._drag_current = QPoint()

    def set_camera_pixmap(
        self,
        pixmap: QPixmap,
        frame_width: int,
        frame_height: int,
    ) -> None:
        self._frame_width = int(frame_width)
        self._frame_height = int(frame_height)
        self.setPixmap(pixmap)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        if self.pixmap() is None or self.pixmap().isNull():
            return

        self._dragging = True
        self._drag_start = event.position().toPoint()
        self._drag_current = self._drag_start
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging:
            super().mouseMoveEvent(event)
            return

        self._drag_current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._dragging or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return

        self._dragging = False
        self._drag_current = event.position().toPoint()

        first = self._map_widget_to_frame(self._drag_start)
        second = self._map_widget_to_frame(self._drag_current)

        if first is None or second is None:
            self.update()
            return

        x1 = min(first.x(), second.x())
        y1 = min(first.y(), second.y())
        x2 = max(first.x(), second.x())
        y2 = max(first.y(), second.y())

        if x2 - x1 >= 20 and y2 - y1 >= 20:
            self.roi_changed.emit(
                {
                    "x": x1,
                    "y": y1,
                    "w": x2 - x1,
                    "h": y2 - y1,
                }
            )

        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        if not self._dragging:
            return

        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.cyan, 2, Qt.PenStyle.SolidLine))
        painter.drawRect(QRect(self._drag_start, self._drag_current).normalized())

    def _map_widget_to_frame(self, point: QPoint) -> QPoint | None:
        if self._frame_width <= 0 or self._frame_height <= 0:
            return None

        label_width = max(1, self.contentsRect().width())
        label_height = max(1, self.contentsRect().height())
        frame_ratio = self._frame_width / self._frame_height
        label_ratio = label_width / label_height

        if label_ratio > frame_ratio:
            shown_height = label_height
            shown_width = int(shown_height * frame_ratio)
            offset_x = (label_width - shown_width) // 2
            offset_y = 0
        else:
            shown_width = label_width
            shown_height = int(shown_width / frame_ratio)
            offset_x = 0
            offset_y = (label_height - shown_height) // 2

        local_x = point.x() - offset_x
        local_y = point.y() - offset_y

        if local_x < 0 or local_y < 0 or local_x >= shown_width or local_y >= shown_height:
            return None

        frame_x = int(local_x * self._frame_width / shown_width)
        frame_y = int(local_y * self._frame_height / shown_height)

        frame_x = max(0, min(self._frame_width - 1, frame_x))
        frame_y = max(0, min(self._frame_height - 1, frame_y))
        return QPoint(frame_x, frame_y)
