from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QSizePolicy,
    QComboBox,
    QSpinBox,
)

from core.app_state import AppState, MachineMode, StateTransition
from core.camera_service import CameraService
from core.config_service import ConfigService
from core.color_repository import ColorRepository
from core.gantry_service import GantryService
from core.vision_processor import VisionProcessor, VisionResult
from core.serial_service import SerialConfig, SerialService
from core.product_counter_service import ProductCounterService
from desktop_app.color_calibrator_dialog import ColorCalibratorDialog
from desktop_app.roi_camera_label import ROICameraLabel

OUTER_GAP = 8
INNER_GAP = 6
BOX_MARGIN = 8
ROW_GAP = 6

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        # self.state = AppState() # tao cac trang thai he hong
        # self.selected_model_path: str | None = None # tao duong dan file
        # self.camera_running = False # camera co dang chay khong
        # self.mask_visible = True # mask co dang chay ko

        self.state = AppState()

        self.config_service = ConfigService()
        self.app_config = self.config_service.load()
        serial_config = self.app_config["serial"]
        self.serial_service = SerialService(
            config=SerialConfig(
                port=str(serial_config.get("port", "MOCK_COM")),
                baudrate=int(serial_config.get("baudrate", 115200)),
                timeout=float(serial_config.get("timeout", 1.0)),
                ),
            mock_mode=bool(serial_config.get("mock_mode", True)),
        )

        self.gantry = GantryService(serial_service=self.serial_service)
        camera_config = self.app_config["camera"]
        self.camera_service = CameraService(
            source=camera_config.get("source", 0),
            width=int(camera_config.get("width", 640)),
            height=int(camera_config.get("height", 480)),
        )

        # Kho màu HSV được lưu riêng trong config/colors.json.
        self.color_repository = ColorRepository()

        # VisionProcessor chứa toàn bộ pipeline: ROI, Sampling Box, trừ nền,
        # phân loại màu, ổn định nhiều frame, đếm một lần và điểm nối YOLO.
        self.vision_processor = VisionProcessor(
            config=self.app_config.get("vision", {}),
            color_repository=self.color_repository,
        )

        self.latest_camera_frame = None
        self.latest_mask_frame = None
        self.last_detected_color_key: str | None = None
        self.last_stable_color_key: str | None = None
        self.counter_service = ProductCounterService(
            self.color_repository.color_keys()
        )
        self.selected_model_path: str | None = None
        self.color_calibrator_dialog: ColorCalibratorDialog | None = None

        self.camera_running = False
        self.camera_stopping = False
        self.mask_visible = True

        self.active_jog_axis: str | None = None
        self.active_jog_direction = 0

        self.jog_timer = QTimer(self)
        self.jog_timer.setInterval(120)  # ms, càng nhỏ thì chạy càng nhanh
        self.jog_timer.timeout.connect(self.run_continuous_jog)

        # Kiểm tra định kỳ để phát hiện ESP32 bị rút khỏi USB.
        # Chỉ nhìn biến connected là chưa đủ vì Windows có thể giữ handle COM cũ.
        self.serial_monitor_timer = QTimer(self)
        self.serial_monitor_timer.setInterval(750)
        self.serial_monitor_timer.timeout.connect(self.check_serial_connection)

        self.setWindowTitle("Hệ thống phân loại sản phẩm tự động")
        self.resize(1280, 720)
        self.setMinimumSize(1000, 600)

        self.root = QWidget()
        self.setCentralWidget(self.root)

        self.main_layout = QVBoxLayout(self.root)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(OUTER_GAP)

        self.main_layout.addWidget(self.build_header())

        body_layout = QHBoxLayout()
        body_layout.setSpacing(OUTER_GAP)

        left_panel = self.create_scroll_area(self.build_left_panel())
        center_panel = self.build_center_panel()
        right_panel = self.create_scroll_area(self.build_right_panel())

        body_layout.addWidget(left_panel, 3)
        body_layout.addWidget(center_panel, 6)
        body_layout.addWidget(right_panel, 3)

        self.main_layout.addLayout(body_layout, 1)

        self.connect_events()
        self.apply_state_to_ui()
        self.handle_scan_com_ports()
        self.apply_config_to_ui()
        self.serial_monitor_timer.start()

        self.append_log("Đã tải cấu hình từ config/app_config.json.")
        self.append_log("Vision v0.2 đã tích hợp: ROI, Sampling Box, HSV, Stability và Counter.")

    # =========================
    # BUILD UI
    # =========================

    def build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("Card")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)

        title_area = QVBoxLayout()

        title = QLabel("HỆ THỐNG PHÂN LOẠI SẢN PHẨM TỰ ĐỘNG | Nhóm 10")
        title.setObjectName("Title")

        subtitle = QLabel("Version 0.2 | HSV + ROI + Stability + ESP32 | YOLO tùy chọn")
        subtitle.setObjectName("Subtitle")

        title_area.addWidget(title)
        title_area.addWidget(subtitle)

        layout.addLayout(title_area, 1)

        self.mode_badge = QLabel("MODE: AUTO_READY")
        self.mode_badge.setObjectName("Badge")

        self.camera_badge = QLabel("CAMERA: CHƯA GẮN")
        self.camera_badge.setObjectName("Badge")

        self.esp_badge = QLabel("ESP32: CHƯA GẮN")
        self.esp_badge.setObjectName("Badge")

        layout.addWidget(self.mode_badge)
        layout.addWidget(self.camera_badge)
        layout.addWidget(self.esp_badge)

        return frame

    def build_left_panel(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setSpacing(OUTER_GAP)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.build_operation_box())
        layout.addWidget(self.build_maintenance_box())
        layout.addWidget(self.build_log_panel(), 1)

        return wrapper

    def build_operation_box(self) -> QGroupBox: # tao bang dieu khien trung tam 
        self.operation_box = QGroupBox("CHẾ ĐỘ VẬN HÀNH")
        layout = QVBoxLayout(self.operation_box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)
        self.btn_start = QPushButton("AUTO")
        self.btn_start.setStyleSheet("background-color: #16a34a;")

        self.btn_pause = QPushButton("TẠM DỪNG")
        self.btn_pause.setStyleSheet("background-color: #d97706;")

        self.btn_estop = QPushButton("DỪNG KHẨN CẤP")
        self.btn_estop.setStyleSheet("background-color: #dc2626;")

        self.btn_reset = QPushButton("RESET")
        self.btn_reset.setStyleSheet("background-color: #334155;")

        self.operation_hint = QLabel("Điều khiển chu trình tự động của hệ thống.")
        self.operation_hint.setWordWrap(True)
        self.operation_hint.setStyleSheet("color: #94a3b8;")

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_pause)
        layout.addWidget(self.btn_estop)
        layout.addWidget(self.btn_reset)
        layout.addWidget(self.operation_hint)

        return self.operation_box

    def build_maintenance_box(self) -> QGroupBox: # tao bang dieu khien bao tri
        self.maintenance_box = QGroupBox("CHẾ ĐỘ BẢO TRÌ")
        layout = QVBoxLayout(self.maintenance_box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)

        self.chk_maintenance = QCheckBox("Bật chế độ bảo trì")
        layout.addWidget(self.chk_maintenance)

        jog_row = QHBoxLayout()
        jog_row.setSpacing(ROW_GAP)
        jog_row.setContentsMargins(0, 0, 0, 0)
        jog_label = QLabel("Bước jog (mm):")

        self.jog_step_input = QDoubleSpinBox()
        self.jog_step_input.setRange(0.1, 100.0)
        self.jog_step_input.setDecimals(1)
        self.jog_step_input.setSingleStep(0.5)
        self.jog_step_input.setValue(5.0)
        self.jog_step_input.setSuffix(" mm")
        self.jog_step_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.jog_step_input.setFixedWidth(120)

        jog_row.addWidget(jog_label)
        jog_row.addStretch()
        jog_row.addWidget(self.jog_step_input)

        layout.addLayout(jog_row)

        self.axis_controls: dict[str, dict[str, object]] = {}

        self.axis_controls["X"] = self.add_axis_control(layout, "X", "Trục X (mm)")
        self.axis_controls["Y"] = self.add_axis_control(layout, "Y", "Trục Y (mm)")
        self.axis_controls["Z"] = self.add_axis_control(layout, "Z", "Trục Z (mm)")

        vacuum_row = QHBoxLayout()
        vacuum_row.setSpacing(ROW_GAP)
        vacuum_row.setContentsMargins(0, 0, 0, 0)

        self.btn_vacuum_on = QPushButton("HÚT THỬ")
        self.btn_vacuum_off = QPushButton("NHẢ THỬ")
        
        vacuum_row.addWidget(self.btn_vacuum_on)
        vacuum_row.addWidget(self.btn_vacuum_off)

        self.btn_axis_stop = QPushButton("DỪNG TRỤC")
        self.btn_axis_stop.setStyleSheet("background-color: #7f1d1d;")

        self.btn_home = QPushButton("VỀ GỐC")
        self.btn_home.setStyleSheet("background-color: #2563eb;")

        layout.addLayout(vacuum_row)
        layout.addWidget(self.btn_axis_stop)
        layout.addWidget(self.btn_home)

        return self.maintenance_box

    def build_center_panel(self) -> QWidget:
        """Tạo vùng camera, mask và các nút thao tác cho Vision."""
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setSpacing(OUTER_GAP)
        layout.setContentsMargins(0, 0, 0, 0)

        camera_box = QGroupBox("LIVE CAMERA / VISION DETECTION")
        camera_layout = QVBoxLayout(camera_box)
        camera_layout.setSpacing(INNER_GAP)
        camera_layout.setContentsMargins(8, 8, 8, 8)

        camera_button_row = QHBoxLayout()
        camera_button_row.setSpacing(ROW_GAP)

        self.btn_camera_toggle = QPushButton("BẬT CAMERA")
        self.btn_camera_toggle.setStyleSheet("background-color: #334155;")

        self.btn_capture_background = QPushButton("LẤY NỀN")
        self.btn_capture_background.setStyleSheet("background-color: #0f766e;")

        self.btn_clear_background = QPushButton("XÓA NỀN")
        self.btn_clear_background.setStyleSheet("background-color: #7f1d1d;")

        self.btn_mask_toggle = QPushButton("ẨN MASK")
        self.btn_mask_toggle.setStyleSheet("background-color: #334155;")

        self.btn_open_calibrator = QPushButton("HIỆU CHỈNH MÀU")
        self.btn_open_calibrator.setStyleSheet("background-color: #4f46e5;")

        camera_button_row.addWidget(self.btn_camera_toggle)
        camera_button_row.addWidget(self.btn_capture_background)
        camera_button_row.addWidget(self.btn_clear_background)
        camera_button_row.addWidget(self.btn_mask_toggle)
        camera_button_row.addStretch()
        camera_button_row.addWidget(self.btn_open_calibrator)

        self.camera_view = ROICameraLabel(
            "CAMERA VIEW\n\nBật camera rồi kéo chuột để chọn ROI"
        )
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setMinimumHeight(260)
        self.camera_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.camera_view.setStyleSheet(
            "background-color: black; color: #64748b; "
            "border: 1px solid #243042; border-radius: 14px; font-size: 18px;"
        )

        camera_help = QLabel(
            "Kéo chuột: chọn ROI | LẤY NỀN khi vùng trống | "
            "Đặt sản phẩm vào khung SAMPLE"
        )
        camera_help.setWordWrap(True)
        camera_help.setStyleSheet("color: #94a3b8;")

        camera_layout.addLayout(camera_button_row)
        camera_layout.addWidget(camera_help)
        camera_layout.addWidget(self.camera_view, 1)

        self.mask_box = QGroupBox("HSV BINARY MASK")
        self.mask_box.setMinimumHeight(190)
        self.mask_box.setMaximumHeight(220)
        self.mask_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        mask_layout = QVBoxLayout(self.mask_box)
        mask_layout.setSpacing(INNER_GAP)
        mask_layout.setContentsMargins(8, 8, 8, 8)

        self.mask_view = QLabel("MASK VIEW")
        self.mask_view.setAlignment(Qt.AlignCenter)
        self.mask_view.setMinimumHeight(110)
        self.mask_view.setMaximumHeight(145)
        self.mask_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.mask_view.setStyleSheet(
            "background-color: #020617; color: #64748b; "
            "border: 1px solid #243042; border-radius: 14px; font-size: 16px;"
        )

        self.color_detect_label = QLabel("Màu phát hiện: CHƯA CÓ")
        self.color_detect_label.setWordWrap(True)
        self.color_detect_label.setStyleSheet(
            "color: #94a3b8; font-weight: 700;"
        )

        mask_layout.addWidget(self.color_detect_label)
        mask_layout.addWidget(self.mask_view)

        # Lưu layout để khôi phục tỷ lệ sau khi ẩn/hiện mask.
        self.center_vision_layout = layout
        self.camera_box = camera_box

        layout.addWidget(self.camera_box, 1)
        layout.addWidget(self.mask_box, 0)
        return wrapper

    def build_right_panel(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setSpacing(OUTER_GAP)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self.build_stats_box())
        layout.addWidget(self.build_learning_box())
        layout.addWidget(self.build_model_box())
        layout.addWidget(self.build_esp32_box())
        layout.addWidget(self.build_settings_box())
        layout.addStretch()

        return wrapper

    def build_stats_box(self) -> QGroupBox:
        """Tạo thống kê động theo danh sách màu trong colors.json."""
        box = QGroupBox("THỐNG KÊ SẢN PHẨM")
        layout = QVBoxLayout(box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)

        self.stats_grid = QGridLayout()
        self.stats_grid.setHorizontalSpacing(ROW_GAP)
        self.stats_grid.setVerticalSpacing(ROW_GAP)

        self.test_grid = QGridLayout()
        self.test_grid.setHorizontalSpacing(ROW_GAP)
        self.test_grid.setVerticalSpacing(ROW_GAP)

        self.stat_values: dict[str, QLabel] = {}
        self.test_count_buttons: list[QPushButton] = []

        self.btn_reset_counts = QPushButton("RESET ĐẾM")
        self.btn_reset_counts.setStyleSheet("background-color: #334155;")

        layout.addLayout(self.stats_grid)
        layout.addWidget(self.btn_reset_counts)
        layout.addLayout(self.test_grid)

        self.rebuild_stat_cards()
        return box

    def build_learning_box(self) -> QGroupBox:
        box = QGroupBox("QUẢN LÝ / HIỆU CHỈNH MÀU")
        layout = QVBoxLayout(box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)

        self.color_name_input = QLineEdit()
        self.color_name_input.setPlaceholderText("Tên màu mới (không bắt buộc)...")

        self.btn_learn_color = QPushButton("MỞ TRACKBAR HSV")
        self.btn_learn_color.setStyleSheet("background-color: #4f46e5;")

        note = QLabel(
            "Có thể thêm, sửa, xóa màu; thêm nhiều dải HSV và xem mask trực tiếp."
        )
        note.setStyleSheet("color: #94a3b8;")
        note.setWordWrap(True)

        layout.addWidget(self.color_name_input)
        layout.addWidget(self.btn_learn_color)
        layout.addWidget(note)
        return box

    def build_model_box(self) -> QGroupBox:
        box = QGroupBox("MODEL NHẬN DIỆN")
        layout = QVBoxLayout(box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)

        self.model_file_label = QLabel("File hiện tại: Chưa chọn")
        self.model_file_label.setWordWrap(True)
        self.model_file_label.setStyleSheet("color: #cbd5e1;")

        self.model_status_label = QLabel("Trạng thái: HSV đang chạy, YOLO đang tắt")
        self.model_status_label.setWordWrap(True)
        self.model_status_label.setStyleSheet("color: #facc15; font-weight: 700;")

        self.chk_yolo_enabled = QCheckBox("Dùng YOLO để lấy bbox PRODUCT")

        self.btn_choose_model = QPushButton("THAY FILE .PT / .ONNX")
        self.btn_choose_model.setStyleSheet("background-color: #2563eb;")

        self.btn_reload_model = QPushButton("TẢI MODEL")
        self.btn_reload_model.setStyleSheet("background-color: #475569;")

        layout.addWidget(self.model_file_label)
        layout.addWidget(self.model_status_label)
        layout.addWidget(self.chk_yolo_enabled)
        layout.addWidget(self.btn_choose_model)
        layout.addWidget(self.btn_reload_model)
        return box

    def build_esp32_box(self) -> QGroupBox:
        box = QGroupBox("KẾT NỐI ESP32")
        layout = QVBoxLayout(box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)

        port_row = QHBoxLayout()
        port_row.setSpacing(ROW_GAP)
        port_row.setContentsMargins(0, 0, 0, 0)

        self.com_port_combo = QComboBox()
        self.com_port_combo.setMinimumHeight(36)

        self.btn_scan_com = QPushButton("QUÉT COM")
        self.btn_scan_com.setStyleSheet("background-color: #334155;")

        port_row.addWidget(self.com_port_combo, 1)
        port_row.addWidget(self.btn_scan_com)

        self.btn_esp_connect = QPushButton("KẾT NỐI ESP32")
        self.btn_esp_connect.setStyleSheet("background-color: #2563eb;")

        self.esp_status_label = QLabel("Trạng thái: Chưa kết nối")
        self.esp_status_label.setStyleSheet("color: #facc15; font-weight: 700;")

        self.esp_mock_note = QLabel("Mock mode: bật. Có thể test khi chưa cắm ESP32.")
        self.esp_mock_note.setStyleSheet("color: #94a3b8;")
        self.esp_mock_note.setWordWrap(True)

        layout.addLayout(port_row)
        layout.addWidget(self.btn_esp_connect)
        layout.addWidget(self.esp_status_label)
        layout.addWidget(self.esp_mock_note)

        return box

    def build_settings_box(self) -> QGroupBox:
        box = QGroupBox("CÀI ĐẶT HỆ THỐNG")
        layout = QVBoxLayout(box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)

        camera_source_row = QHBoxLayout()
        camera_source_row.setSpacing(ROW_GAP)
        camera_source_row.setContentsMargins(0, 0, 0, 0)

        camera_source_label = QLabel("Camera source:")

        self.camera_source_input = QSpinBox()
        self.camera_source_input.setRange(0, 10)
        self.camera_source_input.setValue(0)
        self.camera_source_input.setFixedWidth(90)

        camera_source_row.addWidget(camera_source_label)
        camera_source_row.addStretch()
        camera_source_row.addWidget(self.camera_source_input)

        resolution_row = QHBoxLayout()
        resolution_row.setSpacing(ROW_GAP)
        resolution_row.setContentsMargins(0, 0, 0, 0)

        width_label = QLabel("W:")

        self.camera_width_input = QSpinBox()
        self.camera_width_input.setRange(160, 1920)
        self.camera_width_input.setSingleStep(80)
        self.camera_width_input.setValue(640)
        self.camera_width_input.setFixedWidth(90)

        height_label = QLabel("H:")

        self.camera_height_input = QSpinBox()
        self.camera_height_input.setRange(120, 1080)
        self.camera_height_input.setSingleStep(60)
        self.camera_height_input.setValue(480)
        self.camera_height_input.setFixedWidth(90)

        resolution_row.addWidget(width_label)
        resolution_row.addWidget(self.camera_width_input)
        resolution_row.addWidget(height_label)
        resolution_row.addWidget(self.camera_height_input)

        self.btn_save_settings = QPushButton("LƯU CÀI ĐẶT")
        self.btn_save_settings.setStyleSheet("background-color: #334155;")
        self.btn_health_check = QPushButton("KIỂM TRA APP")
        self.btn_health_check.setStyleSheet("background-color: #475569;")

        self.settings_status_label = QLabel("Trạng thái: Chưa thay đổi")
        self.settings_status_label.setStyleSheet("color: #94a3b8;")
        self.settings_status_label.setWordWrap(True)

        layout.addLayout(camera_source_row)
        layout.addLayout(resolution_row)
        layout.addWidget(self.btn_save_settings)
        layout.addWidget(self.btn_health_check)
        layout.addWidget(self.settings_status_label)

        return box

    def build_log_panel(self) -> QGroupBox:
        box = QGroupBox("SYSTEM LOGS")
        layout = QVBoxLayout(box)
        layout.setSpacing(INNER_GAP)
        layout.setContentsMargins(BOX_MARGIN, BOX_MARGIN, BOX_MARGIN, BOX_MARGIN)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(300)
        self.log_console.setMinimumHeight(160)

        layout.addWidget(self.log_console)

        return box

    # =========================
    # SMALL UI HELPERS
    # =========================

    def add_axis_control(self, layout: QVBoxLayout, axis_name: str, label: str) -> dict[str, object]:
        row = QHBoxLayout()
        row.setSpacing(ROW_GAP)
        row.setContentsMargins(0, 0, 0, 0)

        axis_label = QLabel(label)
        axis_label.setStyleSheet("font-weight: 700;")
        axis_label.setFixedWidth(90)

        btn_minus = QPushButton(f"{axis_name}-")
        btn_minus.setFixedWidth(52)

        position_input = QDoubleSpinBox()
        position_input.setRange(0.0, 9999.0)
        position_input.setDecimals(1)
        position_input.setSingleStep(1.0)
        position_input.setValue(0.0)
        position_input.setSuffix(" mm")
        position_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        position_input.setFixedWidth(120)

        btn_plus = QPushButton(f"{axis_name}+")
        btn_plus.setFixedWidth(52)

        row.addWidget(axis_label)
        row.addWidget(btn_minus)
        row.addWidget(position_input)
        row.addWidget(btn_plus)

        # btn_minus.clicked.connect(lambda: self.jog_axis(axis_name, direction=-1))
        # btn_plus.clicked.connect(lambda: self.jog_axis(axis_name, direction=1))
        # position_input.editingFinished.connect(lambda: self.handle_axis_input(axis_name))

        btn_minus.pressed.connect(
            lambda axis=axis_name: self.start_continuous_jog(axis, direction=-1)
        )
        btn_minus.released.connect(self.stop_continuous_jog)

        btn_plus.pressed.connect(
            lambda axis=axis_name: self.start_continuous_jog(axis, direction=1)
            )
        btn_plus.released.connect(self.stop_continuous_jog)

        position_input.editingFinished.connect(lambda: self.handle_axis_input(axis_name))

        layout.addLayout(row)

        return {
            "input": position_input,
            "minus": btn_minus,
            "plus": btn_plus,
        }

    def create_stat_card(self, key: str, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: 900;")

        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: 900;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        self.stat_values[key] = value_label

        return card

    def clear_layout(self, layout) -> None:
        """Xóa widget khỏi layout để có thể dựng lại thống kê động."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def rebuild_stat_cards(self) -> None:
        if not hasattr(self, "stats_grid"):
            return

        self.clear_layout(self.stats_grid)
        self.clear_layout(self.test_grid)
        self.stat_values.clear()
        self.test_count_buttons.clear()

        color_keys = self.color_repository.color_keys()
        self.counter_service.configure_keys(color_keys)
        keys = color_keys + ["error"]

        for index, key in enumerate(keys):
            row = index // 2
            column = index % 2

            if key == "error":
                title = "LỖI"
                ui_color = "#f97316"
            else:
                title = self.color_repository.get_display_name(key)
                ui_color = self.color_repository.get_ui_color(key)

            card = self.create_stat_card(key, title, "0", ui_color)
            self.stats_grid.addWidget(card, row, column)

            button = QPushButton(f"TEST {title}")
            button.setStyleSheet(f"background-color: {ui_color}; color: #ffffff;")
            button.clicked.connect(
                lambda checked=False, color_key=key: self.handle_test_count(color_key)
            )
            self.test_grid.addWidget(button, row, column)
            self.test_count_buttons.append(button)

        self.refresh_count_ui()

    def create_scroll_area(self, widget: QWidget) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setWidget(widget)

        return scroll_area

    # =========================
    # EVENTS
    # =========================

    def connect_events(self) -> None:
        self.btn_start.clicked.connect(self.handle_start)
        self.btn_pause.clicked.connect(self.handle_pause)
        self.btn_estop.clicked.connect(self.handle_estop)
        self.btn_reset.clicked.connect(self.handle_reset)

        self.chk_maintenance.toggled.connect(self.handle_maintenance_toggle)

        self.btn_vacuum_on.clicked.connect(self.handle_vacuum_on)
        self.btn_vacuum_off.clicked.connect(self.handle_vacuum_off)
        self.btn_axis_stop.clicked.connect(self.handle_axis_stop)
        self.btn_home.clicked.connect(self.handle_home)
        self.jog_step_input.valueChanged.connect(self.handle_jog_step_changed)

        self.btn_camera_toggle.clicked.connect(self.handle_camera_toggle)
        self.camera_service.frame_ready.connect(self.handle_camera_frame)
        self.camera_service.error_occurred.connect(self.handle_camera_error)
        self.camera_service.stopped.connect(self.handle_camera_stopped)
        
        self.btn_save_settings.clicked.connect(self.handle_save_settings)
        self.btn_health_check.clicked.connect(self.handle_health_check)
        self.btn_mask_toggle.clicked.connect(self.handle_mask_toggle)
        self.btn_reset_counts.clicked.connect(self.handle_reset_counts)
        self.btn_capture_background.clicked.connect(self.handle_capture_background)
        self.btn_clear_background.clicked.connect(self.handle_clear_background)
        self.btn_open_calibrator.clicked.connect(self.handle_learn_color)
        self.camera_view.roi_changed.connect(self.handle_roi_changed)

        self.btn_learn_color.clicked.connect(self.handle_learn_color)

        self.btn_choose_model.clicked.connect(self.handle_choose_model)
        self.btn_reload_model.clicked.connect(self.handle_reload_model)
        self.chk_yolo_enabled.toggled.connect(self.handle_yolo_toggle)
        self.btn_scan_com.clicked.connect(self.handle_scan_com_ports)
        self.btn_esp_connect.clicked.connect(self.handle_esp32_connect_toggle)

    def handle_start(self) -> None:
        if self.state.mode in (MachineMode.AUTO_READY, MachineMode.PAUSED):
            if not self.serial_service.connected:
                self.append_log("Không thể chạy AUTO: ESP32 chưa kết nối.", level="WARN")
                return

        transition = self.state.start_auto()
        self.apply_state_transition(transition)


    def handle_pause(self) -> None:
        if self.state.running and not self.serial_service.connected:
            self.append_log("Không thể PAUSE: ESP32 chưa kết nối.", level="WARN")
            return

        transition = self.state.pause()
        self.apply_state_transition(transition)

    def handle_estop(self) -> None:
        self.stop_continuous_jog()
        transition = self.state.emergency_stop()
        self.apply_state_transition(transition)

    def handle_reset(self) -> None:
        self.stop_continuous_jog()
        transition = self.state.reset()
        self.apply_state_transition(transition)

    def handle_maintenance_toggle(self, enabled: bool) -> None:
        transition = self.state.set_maintenance(enabled)
        self.apply_state_transition(transition)

    def handle_vacuum_on(self) -> None:
        message = self.gantry.vacuum_on()
        self.append_log(message)

    def handle_vacuum_off(self) -> None:
        message = self.gantry.vacuum_off()
        self.append_log(message)

    def handle_axis_stop(self) -> None:
        self.stop_continuous_jog()
        message = self.gantry.stop_jog()
        self.append_log(message, level="WARN")

    def handle_home(self) -> None:
        position, message = self.gantry.home()

        self.set_axis_value("X", position.x)
        self.set_axis_value("Y", position.y)
        self.set_axis_value("Z", position.z)

        self.save_gantry_position_to_config()
        self.append_log(message)

    def handle_jog_step_changed(self, value: float) -> None:
        self.config_service.set("gantry.default_jog_step_mm", float(value))
        self.config_service.save()

    def handle_save_settings(self) -> None:
        if self.camera_service.running:
            self.append_log(
                "Không thể lưu cài đặt camera khi camera đang bật.",
                level="WARN",
            )
            self.settings_status_label.setText(
                "Trạng thái: Hãy tắt camera trước khi lưu."
            )
            self.settings_status_label.setStyleSheet(
                "color: #facc15; font-weight: 700;"
            )
            return

        camera_source = int(self.camera_source_input.value())
        camera_width = int(self.camera_width_input.value())
        camera_height = int(self.camera_height_input.value())

        if not CameraService.is_source_available(camera_source):
            self.append_log(
                f"Camera source={camera_source} không khả dụng. Không lưu cấu hình.",
                level="WARN",
            )
            self.settings_status_label.setText(
                f"Trạng thái: Camera source={camera_source} không khả dụng."
            )
            self.settings_status_label.setStyleSheet(
                "color: #ef4444; font-weight: 700;"
            )

            saved_source = int(self.config_service.get("camera.source", 0))
            self.camera_source_input.setValue(saved_source)
            return

        self.config_service.set("camera.source", camera_source)
        self.config_service.set("camera.width", camera_width)
        self.config_service.set("camera.height", camera_height)
        self.config_service.save()

        self.camera_service.update_config(
            source=camera_source,
            width=camera_width,
            height=camera_height,
        )

        self.settings_status_label.setText("Trạng thái: Đã lưu cài đặt camera.")
        self.settings_status_label.setStyleSheet("color: #22c55e; font-weight: 700;")

        self.append_log(
            f"Đã lưu camera config: source={camera_source}, "
            f"{camera_width}x{camera_height}."
        )

    def handle_health_check(self) -> None:
        self.append_log("========== BẮT ĐẦU KIỂM TRA APP ==========")

        self.check_camera_config()
        self.check_serial_config()
        self.check_model_config()
        self.check_counter_service()
        self.check_gantry_state()

        self.append_log("========== KẾT THÚC KIỂM TRA APP ==========")

    def check_camera_config(self) -> None:
        camera_source = int(self.config_service.get("camera.source", 0))
        camera_width = int(self.config_service.get("camera.width", 640))
        camera_height = int(self.config_service.get("camera.height", 480))

        available = CameraService.is_source_available(camera_source)

        if available:
            self.append_log(
                f"CHECK CAMERA: OK source={camera_source}, "
                f"{camera_width}x{camera_height}."
            )
            return

        self.append_log(
            f"CHECK CAMERA: FAIL source={camera_source} không khả dụng.",
            level="WARN",
        )


    def check_serial_config(self) -> None:
        port = self.serial_service.config.port
        baudrate = self.serial_service.config.baudrate
        mock_mode = self.serial_service.mock_mode

        if mock_mode:
            self.append_log(
                f"CHECK SERIAL: OK mock mode, port={port}, baudrate={baudrate}."
            )
            return

        ports = self.serial_service.list_available_ports()

        if port in ports:
            self.append_log(
                f"CHECK SERIAL: OK tìm thấy {port}, baudrate={baudrate}."
            )
            return

        self.append_log(
            f"CHECK SERIAL: WARN không thấy {port} trong danh sách COM.",
            level="WARN",
        )


    def check_model_config(self) -> None:
        model_path = str(self.config_service.get("model.path", ""))

        if not model_path:
            self.append_log(
                "CHECK MODEL: WARN chưa chọn file model.",
                level="WARN",
            )
            return

        if not Path(model_path).exists():
            self.append_log(
                f"CHECK MODEL: FAIL không tìm thấy file model: {model_path}",
                level="WARN",
            )
            return

        self.append_log(f"CHECK MODEL: OK {Path(model_path).name}.")


    def check_counter_service(self) -> None:
        counts = self.counter_service.snapshot()
        required_keys = set(self.color_repository.color_keys()) | {"error"}

        if set(counts.keys()) != required_keys:
            self.append_log(
                f"CHECK COUNTER: FAIL sai keys {counts.keys()}",
                level="WARN",
            )
            return

        self.append_log(f"CHECK COUNTER: OK {counts}.")


    def check_gantry_state(self) -> None:
        x = self.get_axis_value("X")
        y = self.get_axis_value("Y")
        z = self.get_axis_value("Z")

        if x < 0 or y < 0 or z < 0:
            self.append_log(
                f"CHECK GANTRY: FAIL tọa độ âm X={x}, Y={y}, Z={z}.",
                level="WARN",
            )
            return

        self.append_log(
            f"CHECK GANTRY: OK X={x:.1f}, Y={y:.1f}, Z={z:.1f}."
        )

    def handle_camera_toggle(self) -> None:
        if self.camera_service.running:
            self.stop_camera()
            return

        self.start_camera()

    def start_camera(self) -> None:
        if self.camera_stopping:
            self.append_log(
                "Camera: đang dừng thread cũ, hãy chờ một nhịp.",
                level="WARN",
            )
            return

        started = self.camera_service.start()

        if not started:
            self.append_log(
                "Camera: camera đang bận hoặc chưa dọn thread xong.",
                level="WARN",
            )
            return

        self.camera_running = True
        self.camera_stopping = False
        self.btn_camera_toggle.setEnabled(False)
        self.btn_camera_toggle.setText("ĐANG MỞ...")
        self.camera_badge.setText("CAMERA: ĐANG MỞ")
        self._set_preview_message(
            self.camera_view,
            "CAMERA VIEW\n\nĐang mở camera...",
            point_size=12.0,
        )
        self.append_log("Camera: bắt đầu mở luồng OpenCV.")


    def stop_camera(self) -> None:
        """Dừng camera bất đồng bộ nhưng giữ event loop PySide6 hoạt động."""
        if self.camera_stopping:
            return

        self.camera_running = False
        self.camera_stopping = True
        self.btn_camera_toggle.setEnabled(False)
        self.btn_camera_toggle.setText("ĐANG TẮT...")
        self.camera_badge.setText("CAMERA: ĐANG TẮT")
        self.camera_service.stop()
        self.append_log("Camera: đang tắt luồng OpenCV.")


    def handle_camera_stopped(self) -> None:
        """Khôi phục giao diện sau khi QThread camera đã release hoàn toàn."""
        self.camera_running = False
        self.camera_stopping = False
        self.latest_camera_frame = None
        self.latest_mask_frame = None

        self.btn_camera_toggle.setEnabled(True)
        self.btn_camera_toggle.setText("BẬT CAMERA")
        self.camera_badge.setText("CAMERA: ĐÃ TẮT")

        # Không dùng QLabel.clear() ở đây. Một số theme định nghĩa font bằng px,
        # clear()+setText có thể làm Qt cố set pointSize=-1 trên một số máy.
        self._set_preview_message(
            self.camera_view,
            "CAMERA VIEW\n\nLuồng camera đã tắt.",
            point_size=12.0,
        )
        self._set_preview_message(
            self.mask_view,
            "MASK VIEW\n\nLuồng camera đã tắt.",
            point_size=11.0,
        )

        self.color_detect_label.setText("Màu phát hiện: CHƯA CÓ")
        self.color_detect_label.setStyleSheet(
            "color: #94a3b8; font-weight: 700;"
        )
        self.last_detected_color_key = None
        self.last_stable_color_key = None
        self.vision_processor.reset_tracking()

        self.append_log("Camera: đã tắt và release camera.")


    def handle_camera_error(self, message: str) -> None:
        self.camera_running = False
        self.camera_badge.setText("CAMERA: LỖI")
        self.btn_camera_toggle.setEnabled(False)
        self.btn_camera_toggle.setText("ĐANG DỪNG...")

        self.camera_stopping = True
        self._set_preview_message(
            self.camera_view,
            "CAMERA VIEW\n\nKhông mở được camera.",
            point_size=12.0,
        )
        self._set_preview_message(
            self.mask_view,
            "MASK VIEW\n\nKhông có frame camera.",
            point_size=11.0,
        )
        self.color_detect_label.setText("Màu phát hiện: CHƯA CÓ")
        self.color_detect_label.setStyleSheet("color: #94a3b8; font-weight: 700;")
        self.last_detected_color_key = None

        self.append_log(message, level="ERROR")

    def handle_camera_frame(self, frame_bgr) -> None:
        """Nhận frame từ QThread camera, chạy Vision và cập nhật giao diện."""
        # Bỏ frame cuối còn nằm trong hàng đợi sau khi người dùng bấm TẮT.
        if self.camera_stopping or not self.camera_service.running:
            return

        self.camera_running = True
        self.latest_camera_frame = frame_bgr.copy()

        if not self.btn_camera_toggle.isEnabled():
            self.btn_camera_toggle.setEnabled(True)
            self.btn_camera_toggle.setText("TẮT CAMERA")
            self.camera_badge.setText("CAMERA: ĐANG BẬT")

        result = self.vision_processor.process(frame_bgr)
        self.latest_mask_frame = result.mask

        pixmap = self.convert_bgr_frame_to_pixmap(result.annotated_frame)

        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.camera_view.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            frame_height, frame_width = frame_bgr.shape[:2]
            self.camera_view.set_camera_pixmap(
                scaled_pixmap,
                frame_width=frame_width,
                frame_height=frame_height,
            )

        self.show_mask_frame(result.mask)
        self.update_color_detect_label(result)

        if result.stable_label != self.last_stable_color_key:
            if result.stable_label is not None:
                display_name = self.color_repository.get_display_name(result.stable_label)
                self.append_log(
                    f"VISION: màu ổn định {display_name}, "
                    f"conf={result.confidence:.3f}, margin={result.margin:.3f}."
                )
            self.last_stable_color_key = result.stable_label

        if result.count_event is not None:
            self.increment_product_count(result.count_event, source="VISION")

            # Chỉ gửi lệnh phân loại khi hệ thống đang chạy AUTO.
            if self.state.running:
                self.send_serial_command(f"SORT,{result.count_event.upper()}")

    def update_hsv_detection(self, frame_bgr) -> None:
        """Giữ hàm tương thích với code cũ; pipeline chính nằm trong handle_camera_frame."""
        result = self.vision_processor.process(frame_bgr)
        self.show_mask_frame(result.mask)
        self.update_color_detect_label(result)

    def show_mask_frame(self, mask_gray) -> None:
        if not self.mask_visible or mask_gray is None:
            return

        mask_gray = mask_gray.copy()

        height, width = mask_gray.shape
        bytes_per_line = width

        image = QImage(
            mask_gray.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_Grayscale8,
        )

        pixmap = QPixmap.fromImage(image.copy())

        if pixmap.isNull():
            return

        scaled_pixmap = pixmap.scaled(
            self.mask_view.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.mask_view.setPixmap(scaled_pixmap)


    def update_color_detect_label(self, result: VisionResult) -> None:
        stable_key = result.stable_label

        if not result.counting_ready:
            self.color_detect_label.setText(
                "Màu phát hiện: CHƯA LẤY NỀN | "
                "Counter đang khóa để tránh đếm nền."
            )
            self.color_detect_label.setStyleSheet(
                "color: #facc15; font-weight: 900;"
            )
            return

        if not result.present:
            self.color_detect_label.setText(
                "Màu phát hiện: CHƯA CÓ SẢN PHẨM | "
                f"Change: {result.change_ratio:.3f}"
            )
            self.color_detect_label.setStyleSheet(
                "color: #94a3b8; font-weight: 700;"
            )
            return

        display_key = stable_key or result.instant_label

        if display_key == "unknown":
            self.color_detect_label.setText(
                "Màu phát hiện: UNKNOWN | "
                f"Conf: {result.confidence:.3f} | Margin: {result.margin:.3f}"
            )
            self.color_detect_label.setStyleSheet(
                "color: #ef4444; font-weight: 900;"
            )
            return

        display_name = self.color_repository.get_display_name(display_key)
        text_color = self.color_repository.get_ui_color(display_key)
        state_text = "ỔN ĐỊNH" if stable_key else "ĐANG XÁC NHẬN"

        self.color_detect_label.setText(
            f"Màu phát hiện: {display_name} | {state_text} | "
            f"Conf: {result.confidence:.3f} | Margin: {result.margin:.3f}"
        )
        self.color_detect_label.setStyleSheet(
            f"color: {text_color}; font-weight: 900;"
        )

    def convert_bgr_frame_to_pixmap(self, frame_bgr) -> QPixmap:
        if frame_bgr is None:
            return QPixmap()

        frame_rgb = frame_bgr[:, :, ::-1].copy()

        height, width, channels = frame_rgb.shape
        bytes_per_line = channels * width

        image = QImage(
            frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )

        return QPixmap.fromImage(image.copy())

    def handle_mask_toggle(self) -> None:
        """Ẩn/hiện nội dung mask nhưng giữ nguyên bố cục Camera-first."""
        self.mask_visible = not self.mask_visible

        if self.mask_visible:
            self.btn_mask_toggle.setText("ẨN MASK")

            if self.latest_mask_frame is not None:
                self.show_mask_frame(self.latest_mask_frame)
            else:
                self._set_preview_message(
                    self.mask_view,
                    "MASK VIEW\n\nChưa có dữ liệu mask.",
                    point_size=11.0,
                )

            self.append_log("HSV Mask: đã bật hiển thị.")
            return

        self.btn_mask_toggle.setText("HIỆN MASK")
        self._set_preview_message(
            self.mask_view,
            "MASK VIEW\n\nĐÃ ẨN HIỂN THỊ",
            point_size=11.0,
        )
        self.append_log("HSV Mask: đã ẩn nội dung, giữ nguyên bố cục.")

    def handle_reset_counts(self) -> None:
        self.counter_service.reset()
        self.refresh_count_ui()
        self.append_log("Đã reset số đếm sản phẩm về 0.")

    def handle_test_count(self, color_key: str) -> None:
        self.increment_product_count(color_key, source="TEST")


    def increment_product_count(self, color_key: str, source: str = "SYSTEM") -> None:
        new_value = self.counter_service.increment(color_key)
        self.refresh_count_ui()

        if color_key == "error":
            display_name = "LỖI"
        else:
            display_name = self.color_repository.get_display_name(color_key)

        self.append_log(
            f"{source}: ghi nhận sản phẩm {display_name}, tổng={new_value}."
        )


    def refresh_count_ui(self) -> None:
        counts = self.counter_service.snapshot()

        for key, value in counts.items():
            if key in self.stat_values:
                self.stat_values[key].setText(str(value))

    def handle_learn_color(self) -> None:
        """Mở cửa sổ trackbar HSV dùng chung camera với app."""
        suggested_name = self.color_name_input.text().strip()

        if self.latest_camera_frame is None:
            self.append_log(
                "Hãy bật camera trước khi hiệu chỉnh màu.",
                level="WARN",
            )
            return

        dialog = ColorCalibratorDialog(
            repository=self.color_repository,
            sample_provider=self.get_latest_sample_crop,
            suggested_name=suggested_name,
            parent=self,
        )
        dialog.colors_changed.connect(self.handle_colors_changed)
        self.color_calibrator_dialog = dialog
        dialog.exec()
        self.color_calibrator_dialog = None
        self.color_name_input.clear()

    def get_latest_sample_crop(self):
        """Cung cấp ảnh Sampling Box mới nhất cho hộp hiệu chỉnh HSV."""
        return self.vision_processor.get_sample_crop(self.latest_camera_frame)

    def handle_colors_changed(self) -> None:
        self.vision_processor.reload_colors()
        self.counter_service.configure_keys(self.color_repository.color_keys())
        self.rebuild_stat_cards()
        self.append_log("Đã cập nhật hồ sơ màu từ config/colors.json.")

    def handle_roi_changed(self, roi: dict) -> None:
        self.vision_processor.set_roi(roi)
        self.config_service.set("vision.roi", roi)
        self.config_service.save()
        self.append_log(
            f"Đã lưu ROI: x={roi['x']}, y={roi['y']}, "
            f"w={roi['w']}, h={roi['h']}. Hãy LẤY NỀN lại."
        )

    def handle_capture_background(self) -> None:
        if self.latest_camera_frame is None:
            self.append_log("Chưa có frame camera để lấy nền.", level="WARN")
            return

        ok, message = self.vision_processor.capture_background(
            self.latest_camera_frame
        )
        self.append_log(message, level="INFO" if ok else "WARN")

    def handle_clear_background(self) -> None:
        self.vision_processor.clear_background()
        self.append_log("Đã xóa nền tham chiếu. Vision quay về chế độ test trực tiếp.")

    def handle_choose_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file model nhận diện",
            "",
            "YOLO Model Files (*.pt *.onnx);;All Files (*)",
        )

        if not file_path:
            self.append_log("Đã hủy chọn file model.", level="WARN")
            return

        self.selected_model_path = file_path
        file_name = Path(file_path).name

        self.model_file_label.setText(f"File hiện tại: {file_name}")
        self.model_status_label.setText("Trạng thái: Đã chọn file, chưa tải model")
        self.model_status_label.setStyleSheet("color: #facc15; font-weight: 700;")

        self.append_log(f"Đã chọn file model nhận diện: {file_path}")
        self.config_service.set("model.path", file_path)
        self.config_service.save()

    def handle_reload_model(self) -> None:
        if not self.selected_model_path:
            self.append_log("Chưa chọn file model để tải.", level="WARN")
            return

        ok, message = self.vision_processor.product_detector.load_model(
            self.selected_model_path
        )

        if not ok:
            self.model_status_label.setText(f"Trạng thái: {message}")
            self.model_status_label.setStyleSheet(
                "color: #ef4444; font-weight: 700;"
            )
            self.append_log(message, level="WARN")
            return

        self.model_status_label.setText("Trạng thái: Model YOLO đã sẵn sàng")
        self.model_status_label.setStyleSheet(
            "color: #22c55e; font-weight: 700;"
        )
        self.append_log(message)

    def handle_yolo_toggle(self, enabled: bool) -> None:
        self.vision_processor.product_detector.set_enabled(enabled)
        self.config_service.set("vision.yolo.enabled", bool(enabled))
        self.config_service.save()

        if enabled:
            self.append_log(
                "Đã bật YOLO. Nếu model chưa tải, hệ thống vẫn dùng Sampling Box.",
                level="WARN",
            )
        else:
            self.append_log("Đã tắt YOLO; dùng ROI + Sampling Box.")

    def send_serial_command(self, command: str) -> bool:
        if not self.serial_service.connected:
            self.append_log(f"Serial chưa kết nối. Bỏ qua lệnh: {command}", level="WARN")
            return False

        try:
            message = self.serial_service.send_command(command)
        except Exception as error:
            self.append_log(str(error), level="ERROR")

            if not self.serial_service.connected:
                self.handle_serial_connection_lost(
                    "Mất kết nối khi gửi lệnh Serial."
                )

            return False

        self.append_log(message)
        return True

    def apply_state_transition(self, transition: StateTransition) -> None:
        self.append_log(transition.message, level=transition.level)

        if transition.allowed and transition.command:
            self.send_serial_command(transition.command)

        self.apply_state_to_ui()

    def check_serial_connection(self) -> None:
        """Được QTimer gọi định kỳ để phát hiện ESP32 bị rút khỏi USB."""
        if not self.serial_service.connected:
            return

        if self.serial_service.is_connection_alive():
            return

        self.handle_serial_connection_lost(
            f"ESP32 tại {self.serial_service.config.port} đã bị rút hoặc mất kết nối."
        )

    def handle_serial_connection_lost(self, message: str) -> None:
        """Đưa trạng thái Serial và giao diện về disconnected an toàn."""
        try:
            self.serial_service.disconnect()
        except Exception:
            pass

        self.esp_badge.setText("ESP32: MẤT KẾT NỐI")
        self.esp_status_label.setText("Trạng thái: Mất kết nối ESP32")
        self.esp_status_label.setStyleSheet(
            "color: #ef4444; font-weight: 900;"
        )
        self.btn_esp_connect.setText("KẾT NỐI ESP32")
        self.btn_esp_connect.setStyleSheet("background-color: #2563eb;")
        self.com_port_combo.setEnabled(True)
        self.btn_scan_com.setEnabled(True)

        # Không cho AUTO tiếp tục gửi lệnh vào một kết nối đã mất.
        if self.state.running:
            transition = self.state.pause()
            self.apply_state_transition(transition)

        self.append_log(message, level="ERROR")
        self.handle_scan_com_ports()

    def handle_scan_com_ports(self) -> None:
        ports = self.serial_service.list_available_ports()
        saved_port = self.serial_service.config.port

        self.com_port_combo.clear()

        if not ports:
            self.com_port_combo.addItem("Không tìm thấy COM")
            self.append_log("Không tìm thấy cổng COM nào.", level="WARN")
            return

        self.com_port_combo.addItems(ports)

        if saved_port in ports:
            self.com_port_combo.setCurrentText(saved_port)

        self.append_log(f"Đã quét COM: {', '.join(ports)}")

    def handle_esp32_connect_toggle(self) -> None:
        if self.serial_service.connected:
            self.handle_esp32_disconnect()
            return

        self.handle_esp32_connect()

    def handle_esp32_connect(self) -> None:
        selected_port = self.com_port_combo.currentText().strip()

        if not selected_port or selected_port == "Không tìm thấy COM":
            self.append_log("Chưa chọn cổng COM hợp lệ.", level="WARN")
            return

        try:
            self.serial_service.set_port(selected_port)
            message = self.serial_service.connect()
        except Exception as error:
            self.esp_badge.setText("ESP32: LỖI")
            self.esp_status_label.setText("Trạng thái: Kết nối thất bại")
            self.esp_status_label.setStyleSheet("color: #ef4444; font-weight: 700;")
            self.append_log(str(error), level="ERROR")
            return

        badge_text = (
            "ESP32: MOCK"
            if self.serial_service.using_mock_connection
            else "ESP32: ĐÃ KẾT NỐI"
        )
        self.esp_badge.setText(badge_text)
        self.esp_status_label.setText(f"Trạng thái: Đã kết nối {selected_port}")
        self.esp_status_label.setStyleSheet("color: #22c55e; font-weight: 700;")
        self.btn_esp_connect.setText("NGẮT KẾT NỐI")
        self.btn_esp_connect.setStyleSheet("background-color: #7f1d1d;")
        self.com_port_combo.setEnabled(False)
        self.btn_scan_com.setEnabled(False)

        self.append_log(message)

        self.config_service.set("serial.port", selected_port)
        self.config_service.set("serial.mock_mode", self.serial_service.mock_mode)
        self.config_service.set("serial.baudrate", self.serial_service.config.baudrate)
        self.config_service.set("serial.timeout", self.serial_service.config.timeout)
        self.config_service.save()

    def handle_esp32_disconnect(self) -> None:
        try:
            message = self.serial_service.disconnect()
        except Exception as error:
            self.append_log(str(error), level="ERROR")
            return

        self.esp_badge.setText("ESP32: CHƯA GẮN")
        self.esp_status_label.setText("Trạng thái: Chưa kết nối")
        self.esp_status_label.setStyleSheet("color: #facc15; font-weight: 700;")
        self.btn_esp_connect.setText("KẾT NỐI ESP32")
        self.btn_esp_connect.setStyleSheet("background-color: #2563eb;")
        self.com_port_combo.setEnabled(True)
        self.btn_scan_com.setEnabled(True)

        self.append_log(message)

    def apply_config_to_ui(self) -> None:
        jog_step = float(
            self.config_service.get("gantry.default_jog_step_mm", 5.0)
        )
        self.jog_step_input.setValue(jog_step)

        camera_source = int(self.config_service.get("camera.source", 0))
        camera_width = int(self.config_service.get("camera.width", 640))
        camera_height = int(self.config_service.get("camera.height", 480))

        self.camera_source_input.setValue(camera_source)
        self.camera_width_input.setValue(camera_width)
        self.camera_height_input.setValue(camera_height)

        yolo_enabled = bool(self.config_service.get("vision.yolo.enabled", False))
        self.chk_yolo_enabled.blockSignals(True)
        self.chk_yolo_enabled.setChecked(yolo_enabled)
        self.chk_yolo_enabled.blockSignals(False)
        self.vision_processor.product_detector.set_enabled(yolo_enabled)

        last_x = float(self.config_service.get("gantry.last_position.x", 0.0))
        last_y = float(self.config_service.get("gantry.last_position.y", 0.0))
        last_z = float(self.config_service.get("gantry.last_position.z", 0.0))

        self.gantry.set_position("X", last_x)
        self.gantry.set_position("Y", last_y)
        self.gantry.set_position("Z", last_z)

        self.set_axis_value("X", last_x)
        self.set_axis_value("Y", last_y)
        self.set_axis_value("Z", last_z)

        model_path = str(self.config_service.get("model.path", ""))

        if not model_path:
            return

        if not Path(model_path).exists():
            self.selected_model_path = None
            self.model_file_label.setText("File hiện tại: Không tìm thấy file đã lưu")
            self.model_status_label.setText("Trạng thái: Cần chọn lại model")
            self.model_status_label.setStyleSheet("color: #ef4444; font-weight: 700;")
            self.append_log(f"Không tìm thấy model đã lưu: {model_path}", level="WARN")
            return

        self.selected_model_path = model_path
        self.model_file_label.setText(f"File hiện tại: {Path(model_path).name}")
        self.model_status_label.setText("Trạng thái: Model đã sẵn sàng")
        self.model_status_label.setStyleSheet("color: #22c55e; font-weight: 700;")
        self.append_log(f"Đã nạp đường dẫn model từ config: {model_path}")
    # =========================
    # GANTRY CONTROL
    # =========================

    def save_gantry_position_to_config(self) -> None:
        self.config_service.set("gantry.last_position.x", self.get_axis_value("X"))
        self.config_service.set("gantry.last_position.y", self.get_axis_value("Y"))
        self.config_service.set("gantry.last_position.z", self.get_axis_value("Z"))
        self.config_service.save()

    def get_jog_step(self) -> float:
        return self.jog_step_input.value()

    def get_axis_value(self, axis_name: str) -> float:
        axis_input = self.axis_controls[axis_name]["input"]

        if not isinstance(axis_input, QDoubleSpinBox):
            return 0.0

        return axis_input.value()

    def set_axis_value(self, axis_name: str, value: float) -> None:
        axis_input = self.axis_controls[axis_name]["input"]

        if isinstance(axis_input, QDoubleSpinBox):
            axis_input.blockSignals(True)
            axis_input.setValue(value)
            axis_input.blockSignals(False)

    def apply_jog_step(self, axis_name: str, direction: int) -> None:
        try:
            next_value, _ = self.gantry.jog(
                axis=axis_name,
                step=self.get_jog_step(),
                direction=direction,
            )
        except ValueError as error:
            self.append_log(str(error), level="WARN")
            self.stop_continuous_jog()
            return

        self.set_axis_value(axis_name, next_value)

    def start_continuous_jog(self, axis_name: str, direction: int) -> None:
        self.active_jog_axis = axis_name
        self.active_jog_direction = direction

        # Chạy ngay bước đầu tiên để người dùng thấy phản hồi tức thì.
        self.apply_jog_step(axis_name, direction)

        if not self.jog_timer.isActive():
            self.jog_timer.start()

    def run_continuous_jog(self) -> None:
        if self.active_jog_axis is None or self.active_jog_direction == 0:
            return

        self.apply_jog_step(self.active_jog_axis, self.active_jog_direction)

    def stop_continuous_jog(self) -> None:
        if self.jog_timer.isActive():
            self.jog_timer.stop()

        if self.active_jog_axis is None:
            return

        final_value = self.get_axis_value(self.active_jog_axis)

        self.append_log(
            f"Manual: Jog trục {self.active_jog_axis} dừng tại {final_value:.1f} mm."
        )
        
        self.save_gantry_position_to_config()
        self.active_jog_axis = None
        self.active_jog_direction = 0

    def handle_axis_input(self, axis_name: str) -> None:
        current_value = self.get_axis_value(axis_name)

        try:
            safe_value, message = self.gantry.set_position(axis_name, current_value)
        except ValueError as error:
            self.append_log(str(error), level="WARN")
            return

        self.set_axis_value(axis_name, safe_value)
        self.save_gantry_position_to_config()
        self.append_log(message)

    # =========================
    # STATE -> UI
    # =========================

    def apply_state_to_ui(self) -> None:
        maintenance = self.state.maintenance_enabled
        is_estop = self.state.mode == MachineMode.ESTOP
        is_paused = self.state.mode == MachineMode.PAUSED

        # Đồng bộ checkbox bảo trì với state, nhưng không phát signal lặp lại.
        self.chk_maintenance.blockSignals(True)
        self.chk_maintenance.setChecked(maintenance)
        self.chk_maintenance.blockSignals(False)

        # Cập nhật badge trạng thái.
        self.mode_badge.setText(f"MODE: {self.state.mode.value}")

        # Đổi chữ nút theo mode.
        self.btn_start.setText("TIẾP TỤC" if is_paused else "AUTO")
        self.btn_reset.setText("RESET ESTOP" if is_estop else "RESET")

        # Nhóm điều khiển AUTO.
        self.btn_start.setEnabled(not maintenance and not is_estop)
        self.btn_pause.setEnabled(not maintenance and self.state.running and not is_estop)

        # RESET vẫn dùng được khi ESTOP.
        self.btn_reset.setEnabled(is_estop or not maintenance)

        # E-Stop luôn bật.
        self.btn_estop.setEnabled(True)

        # Không cho bật bảo trì khi đang ESTOP.
        self.chk_maintenance.setEnabled(not is_estop)

        # Manual chỉ mở khi đang bảo trì và không ESTOP.
        manual_enabled = maintenance and not is_estop

        manual_widgets = [
            self.jog_step_input,
            self.btn_vacuum_on,
            self.btn_vacuum_off,
            self.btn_axis_stop,
            self.btn_home,
        ]

        for axis_name in ["X", "Y", "Z"]:
            control = self.axis_controls[axis_name]
            manual_widgets.extend(
                [
                    control["input"],
                    control["minus"],
                    control["plus"],
                ]
            )

        for widget in manual_widgets:
            if isinstance(widget, QWidget):
                widget.setEnabled(manual_enabled)

        # Làm mờ/sáng từng khối theo mode.
        self.operation_box.setProperty("locked", maintenance or is_estop)
        self.maintenance_box.setProperty("locked", not manual_enabled)

        self.refresh_style(self.operation_box)
        self.refresh_style(self.maintenance_box)

    def _set_preview_message(
        self,
        label: QLabel,
        text: str,
        point_size: float = 11.0,
    ) -> None:
        """Đặt thông báo lên QLabel mà không tạo QFont pointSize=-1.

        Theme đang dùng font-size theo pixel. Trên một số bản Qt/PySide6,
        QLabel.clear() rồi setText() có thể tạo font point size không hợp lệ.
        Hàm này gán QPixmap rỗng và chuẩn hóa font trước khi đặt chữ.
        """
        label.setPixmap(QPixmap())

        font = QFont(label.font())

        if font.pointSizeF() <= 0:
            font.setPointSizeF(max(1.0, float(point_size)))
            label.setFont(font)

        label.setText(text)
        label.update()

    def closeEvent(self, event) -> None:
        self.serial_monitor_timer.stop()
        self.jog_timer.stop()
        self.camera_service.stop_and_wait()

        try:
            self.serial_service.disconnect()
        except Exception:
            pass

        self.save_gantry_position_to_config()
        super().closeEvent(event)

    def refresh_style(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    # =========================
    # LOG
    # =========================

    def append_log(self, message: str, level: str = "INFO") -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.log_console.appendPlainText(f"[{now}] [{level}] {message}")
        