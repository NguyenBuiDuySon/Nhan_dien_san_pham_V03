from __future__ import annotations

from threading import Event
from typing import Any

import cv2
from PySide6.QtCore import QObject, QThread, Signal, Slot


class CameraWorker(QObject):
    """Đọc camera trong QThread riêng để không chặn giao diện."""

    frame_ready = Signal(object)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(
        self,
        source: int | str = 0,
        width: int = 640,
        height: int = 480,
    ) -> None:
        super().__init__()

        if isinstance(source, str) and source.isdigit():
            source = int(source)

        self.source = source
        self.width = width
        self.height = height

        # threading.Event an toàn hơn một biến bool khi MainWindow yêu cầu dừng
        # trong lúc worker đang đọc frame ở thread khác.
        self._stop_event = Event()
        self._capture: cv2.VideoCapture | None = None

    def open_capture(self, source: int | str) -> cv2.VideoCapture:
        if isinstance(source, str) and source.isdigit():
            source = int(source)

        if isinstance(source, int):
            return cv2.VideoCapture(source, cv2.CAP_DSHOW)

        return cv2.VideoCapture(source)

    @Slot()
    def run(self) -> None:
        self._stop_event.clear()

        try:
            self._capture = self.open_capture(self.source)

            if not self._capture.isOpened():
                self.error_occurred.emit(
                    f"Không mở được camera source={self.source}."
                )
                return

            if self.width > 0:
                self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)

            if self.height > 0:
                self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            while not self._stop_event.is_set():
                ok, frame = self._capture.read()

                if self._stop_event.is_set():
                    break

                if not ok or frame is None:
                    self.error_occurred.emit("Camera: không đọc được frame.")
                    break

                self.frame_ready.emit(frame)
                QThread.msleep(20)

        except Exception as error:
            if not self._stop_event.is_set():
                self.error_occurred.emit(f"Camera lỗi: {error}")

        finally:
            capture = self._capture
            self._capture = None

            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass

            self.finished.emit()

    def stop(self) -> None:
        """Yêu cầu worker thoát vòng đọc ở lần kiểm tra gần nhất."""
        self._stop_event.set()


class CameraService(QObject):
    """Quản lý vòng đời QThread camera."""

    frame_ready = Signal(object)
    error_occurred = Signal(str)
    stopped = Signal()

    def __init__(
        self,
        source: int | str = 0,
        width: int = 640,
        height: int = 480,
    ) -> None:
        super().__init__()

        self.source = source
        self.width = width
        self.height = height

        self.running = False
        self.stopping = False
        self._thread: QThread | None = None
        self._worker: CameraWorker | None = None

    def start(self) -> bool:
        if self.running or self.stopping or self._thread is not None:
            return False

        thread = QThread(self)
        worker = CameraWorker(
            source=self.source,
            width=self.width,
            height=self.height,
        )

        self._thread = thread
        self._worker = worker

        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        worker.frame_ready.connect(self._forward_frame)
        worker.error_occurred.connect(self._forward_error)

        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)

        thread.finished.connect(self._handle_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self.running = True
        self.stopping = False
        thread.start()
        return True

    def stop(self) -> None:
        """Yêu cầu dừng nhưng không chặn event loop của giao diện."""
        if self.stopping:
            return

        self.stopping = True
        self.running = False

        worker = self._worker

        if worker is not None:
            worker.stop()

        # Trường hợp start lỗi trước khi worker chạy xong.
        if self._thread is None:
            self._finish_without_thread()

    def stop_and_wait(self, timeout_ms: int = 3000) -> None:
        """Dừng camera khi đóng ứng dụng và chờ thread giải phóng."""
        self.stop()
        thread = self._thread

        if thread is not None and thread.isRunning():
            finished = thread.wait(timeout_ms)

            if not finished:
                # Không terminate thread vì dễ làm hỏng OpenCV/Qt.
                # Yêu cầu quit thêm một lần rồi chờ ngắn.
                thread.quit()
                thread.wait(500)

        self.running = False
        self.stopping = False
        self._worker = None
        self._thread = None

    def update_config(
        self,
        source: Any,
        width: int,
        height: int,
    ) -> None:
        if self.running or self.stopping or self._thread is not None:
            return

        self.source = source
        self.width = width
        self.height = height

    @staticmethod
    def is_source_available(source: int | str) -> bool:
        if isinstance(source, str) and source.isdigit():
            source = int(source)

        if isinstance(source, int):
            capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            capture = cv2.VideoCapture(source)

        try:
            if not capture.isOpened():
                return False

            ok, frame = capture.read()
            return ok and frame is not None

        finally:
            capture.release()

    @Slot(object)
    def _forward_frame(self, frame) -> None:
        # Có thể còn một frame đã nằm trong hàng đợi ngay sau khi bấm TẮT.
        if self.running and not self.stopping:
            self.frame_ready.emit(frame)

    @Slot(str)
    def _forward_error(self, message: str) -> None:
        if not self.stopping:
            self.error_occurred.emit(message)

    @Slot()
    def _handle_thread_finished(self) -> None:
        self.running = False
        self.stopping = False
        self._worker = None
        self._thread = None
        self.stopped.emit()

    def _finish_without_thread(self) -> None:
        self.running = False
        self.stopping = False
        self._worker = None
        self._thread = None
        self.stopped.emit()
