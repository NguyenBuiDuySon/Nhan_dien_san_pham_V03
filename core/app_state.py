from dataclasses import dataclass
from enum import Enum


class MachineMode(str, Enum):
    AUTO_READY = "AUTO_READY"
    AUTO_RUNNING = "AUTO_RUNNING"
    PAUSED = "PAUSED"
    MANUAL = "MANUAL"
    ESTOP = "ESTOP"


@dataclass(frozen=True)
class StateTransition:
    allowed: bool
    message: str
    command: str | None = None
    level: str = "INFO"


@dataclass
class AppState:
    mode: MachineMode = MachineMode.AUTO_READY
    running: bool = False
    maintenance_enabled: bool = False

    def start_auto(self) -> StateTransition:
        if self.maintenance_enabled:
            return StateTransition(
                allowed=False,
                message="Không thể chạy AUTO khi đang bật chế độ bảo trì.",
                level="WARN",
            )

        if self.mode == MachineMode.ESTOP:
            return StateTransition(
                allowed=False,
                message="Hệ thống đang ESTOP. Cần RESET ESTOP trước khi chạy lại.",
                level="WARN",
            )

        if self.mode == MachineMode.AUTO_RUNNING:
            return StateTransition(
                allowed=False,
                message="Hệ thống đang chạy AUTO.",
                level="WARN",
            )

        if self.mode == MachineMode.PAUSED:
            self.mode = MachineMode.AUTO_RUNNING
            self.running = True
            return StateTransition(
                allowed=True,
                message="Tiếp tục chu trình AUTO.",
                command="AUTO RESUME",
            )

        self.mode = MachineMode.AUTO_RUNNING
        self.running = True
        return StateTransition(
            allowed=True,
            message="Bắt đầu chu trình AUTO.",
            command="AUTO START",
        )

    def pause(self) -> StateTransition:
        if self.maintenance_enabled:
            return StateTransition(
                allowed=False,
                message="Không thể PAUSE khi đang ở chế độ bảo trì.",
                level="WARN",
            )

        if self.mode == MachineMode.ESTOP:
            return StateTransition(
                allowed=False,
                message="Hệ thống đang ESTOP, không thể PAUSE.",
                level="WARN",
            )

        if not self.running:
            return StateTransition(
                allowed=False,
                message="Hệ thống chưa chạy AUTO, không cần tạm dừng.",
                level="WARN",
            )

        self.mode = MachineMode.PAUSED
        self.running = False
        return StateTransition(
            allowed=True,
            message="Tạm dừng hệ thống.",
            command="AUTO PAUSE",
        )

    def emergency_stop(self) -> StateTransition:
        self.mode = MachineMode.ESTOP
        self.running = False
        self.maintenance_enabled = False

        return StateTransition(
            allowed=True,
            message="DỪNG KHẨN CẤP. Khóa hệ thống, chờ RESET ESTOP.",
            command="ESTOP",
            level="ERROR",
        )

    def reset(self) -> StateTransition:
        was_estop = self.mode == MachineMode.ESTOP

        self.mode = MachineMode.AUTO_READY
        self.running = False
        self.maintenance_enabled = False

        if was_estop:
            return StateTransition(
                allowed=True,
                message="RESET ESTOP. Hệ thống trở về trạng thái sẵn sàng.",
                command="RESET",
            )

        return StateTransition(
            allowed=True,
            message="Reset hệ thống về trạng thái ban đầu.",
            command="RESET",
        )

    def set_maintenance(self, enabled: bool) -> StateTransition:
        if self.mode == MachineMode.ESTOP:
            return StateTransition(
                allowed=False,
                message="Không thể bật bảo trì khi hệ thống đang ESTOP.",
                level="WARN",
            )

        if enabled and self.running:
            return StateTransition(
                allowed=False,
                message="Không thể bật bảo trì khi AUTO đang chạy. Hãy PAUSE hoặc RESET trước.",
                level="WARN",
            )

        self.maintenance_enabled = enabled

        if enabled:
            self.mode = MachineMode.MANUAL
            self.running = False
            return StateTransition(
                allowed=True,
                message="Đã bật chế độ bảo trì. Khóa AUTO, mở điều khiển tay.",
                command="MODE MANUAL",
            )

        self.mode = MachineMode.AUTO_READY
        self.running = False
        return StateTransition(
            allowed=True,
            message="Đã tắt chế độ bảo trì. Khóa điều khiển tay, mở vận hành AUTO.",
            command="MODE AUTO_READY",
        )