from dataclasses import dataclass

from core.serial_service import SerialService


@dataclass
class GantryPosition:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class GantryService:
    """
    Quản lý trạng thái gantry 3 trục vít me.

    Stage hiện tại:
    - Xử lý logic tọa độ trong app.
    - Gửi lệnh manual xuống ESP32 nếu SerialService đang kết nối.
    """

    VALID_AXES = {"X", "Y", "Z"}

    def __init__(self, serial_service: SerialService | None = None) -> None:
        self.position = GantryPosition()
        self.vacuum_enabled = False
        self.serial_service = serial_service

    def get_position(self, axis: str) -> float:
        axis = self._normalize_axis(axis)

        if axis == "X":
            return self.position.x

        if axis == "Y":
            return self.position.y

        return self.position.z

    def set_position(self, axis: str, value: float) -> tuple[float, str]:
        axis = self._normalize_axis(axis)
        safe_value = max(0.0, float(value))

        if axis == "X":
            self.position.x = safe_value
        elif axis == "Y":
            self.position.y = safe_value
        else:
            self.position.z = safe_value

        return safe_value, f"Manual: đặt trục {axis} = {safe_value:.1f} mm."

    def jog(self, axis: str, step: float, direction: int) -> tuple[float, str]:
        axis = self._normalize_axis(axis)

        if step <= 0:
            raise ValueError("Bước jog phải lớn hơn 0.")

        if direction not in (-1, 1):
            raise ValueError("Chiều jog không hợp lệ.")

        current_value = self.get_position(axis)
        next_value = current_value + direction * step
        next_value = max(0.0, next_value)

        self.set_position(axis, next_value)

        direction_text = "+" if direction > 0 else "-"
        serial_message = self._send_serial_command(f"JOG {axis} {direction_text} {step:.1f}")

        message = f"Manual: Jog trục {axis}{direction_text} tới {next_value:.1f} mm."
        return next_value, self._join_serial_message(message, serial_message)

    def home(self) -> tuple[GantryPosition, str]:
        self.position = GantryPosition(x=0.0, y=0.0, z=0.0)
        serial_message = self._send_serial_command("HOME")
        message = "Manual: VỀ HOME, đưa X/Y/Z về gốc an toàn."
        return self.position, self._join_serial_message(message, serial_message)

    def vacuum_on(self) -> str:
        self.vacuum_enabled = True
        serial_message = self._send_serial_command("VACUUM ON")
        return self._join_serial_message(
            "Manual: bật hút chân không.",
            serial_message,
        )

    def vacuum_off(self) -> str:
        self.vacuum_enabled = False
        serial_message = self._send_serial_command("VACUUM OFF")
        return self._join_serial_message(
            "Manual: nhả chân không.",
            serial_message,
        )

    def stop_jog(self) -> str:
        serial_message = self._send_serial_command("JOG STOP")
        return self._join_serial_message(
            "Manual: dừng trục JOG.",
            serial_message,
        )

    def snapshot(self) -> dict[str, float | bool]:
        return {
            "x": self.position.x,
            "y": self.position.y,
            "z": self.position.z,
            "vacuum_enabled": self.vacuum_enabled,
        }

    def _normalize_axis(self, axis: str) -> str:
        axis = axis.upper().strip()

        if axis not in self.VALID_AXES:
            raise ValueError(f"Trục không hợp lệ: {axis}")

        return axis

    def _send_serial_command(self, command: str) -> str | None:
        if self.serial_service is None:
            return None

        if not self.serial_service.connected:
            return None

        try:
            return self.serial_service.send_command(command)
        except Exception as error:
            return f"Serial ERROR: {error}"

    def _join_serial_message(self, base_message: str, serial_message: str | None) -> str:
        if not serial_message:
            return base_message

        return f"{base_message}\n{serial_message}"