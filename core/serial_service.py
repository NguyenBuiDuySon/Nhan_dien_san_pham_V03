from __future__ import annotations

from dataclasses import dataclass
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


@dataclass
class SerialConfig:
    port: str = "MOCK_COM"
    baudrate: int = 115200
    timeout: float = 1.0


class SerialService:
    """Quản lý giao tiếp Serial với ESP32.

    Quy ước mock:
    - Chỉ dùng mock khi mock_mode=True và port là MOCK_COM.
    - Nếu người dùng chọn COM thật, service sẽ mở cổng thật.
    - Sau mỗi lệnh thật, service đọc phản hồi ACK/ERR từ ESP32 để app biết
      ESP32 đã nhận lệnh.
    """

    MOCK_PORT = "MOCK_COM"

    def __init__(
        self,
        config: SerialConfig | None = None,
        mock_mode: bool = True,
    ) -> None:
        self.config = config or SerialConfig()
        self.mock_mode = bool(mock_mode)

        self.connection = None
        self.connected = False
        self.sent_commands: list[str] = []

    @property
    def using_mock_connection(self) -> bool:
        """True khi phiên kết nối hiện tại là kết nối giả lập."""
        return (
            self.mock_mode
            and self.config.port.strip().upper() == self.MOCK_PORT
        )

    def set_port(self, port: str) -> None:
        port = port.strip()

        if not port:
            raise ValueError("Tên cổng COM rỗng.")

        if self.connected:
            raise RuntimeError("Không thể đổi cổng COM khi đang kết nối.")

        self.config.port = port

    def list_available_ports(self) -> list[str]:
        ports: list[str] = []

        if list_ports is not None:
            ports = [port.device for port in list_ports.comports()]

        if self.mock_mode and self.MOCK_PORT not in ports:
            ports.insert(0, self.MOCK_PORT)

        return ports

    def connect(self) -> str:
        if self.connected:
            return f"Serial: đã kết nối sẵn tại {self.config.port}."

        if self.using_mock_connection:
            self.connected = True
            return "Serial mock: đã kết nối giả lập tại MOCK_COM."

        if serial is None:
            raise RuntimeError("Chưa cài pyserial. Hãy chạy: pip install pyserial")

        physical_ports = self._physical_ports()

        if self.config.port not in physical_ports:
            raise RuntimeError(
                f"Serial: không tìm thấy cổng {self.config.port}. "
                "Hãy quét COM, kiểm tra Device Manager và cắm lại ESP32."
            )

        try:
            self.connection = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )

            # ESP32 thường reset khi mở COM qua USB. Chờ ngắn để firmware sẵn sàng.
            time.sleep(1.2)
            self._clear_input_buffer()

            self.connected = True
            return f"Serial: đã kết nối ESP32 tại {self.config.port}."
        except Exception as error:
            self._mark_disconnected()
            raise RuntimeError(f"Serial: kết nối thất bại - {error}") from error

    def disconnect(self) -> str:
        if not self.connected and self.connection is None:
            return "Serial: hiện chưa kết nối."

        was_mock = self.using_mock_connection
        self._mark_disconnected()

        if was_mock:
            return "Serial mock: đã ngắt kết nối giả lập."

        return "Serial: đã ngắt kết nối ESP32."

    def is_connection_alive(self) -> bool:
        """Kiểm tra thiết bị còn thực sự tồn tại hay không."""

        if not self.connected:
            return False

        if self.using_mock_connection:
            return True

        if self.connection is None:
            self._mark_disconnected()
            return False

        try:
            if not self.connection.is_open:
                self._mark_disconnected()
                return False

            if self.config.port not in self._physical_ports():
                self._mark_disconnected()
                return False

            _ = self.connection.in_waiting
            return True
        except Exception:
            self._mark_disconnected()
            return False

    def send_command(self, command: str) -> str:
        command = command.strip()

        if not command:
            raise ValueError("Lệnh Serial rỗng.")

        if not self.is_connection_alive():
            raise RuntimeError("Serial chưa kết nối hoặc ESP32 đã bị rút.")

        if self.using_mock_connection:
            self.sent_commands.append(command)
            return f"Serial mock TX: {command}"

        try:
            assert self.connection is not None

            self._clear_input_buffer()

            payload = f"{command}\n".encode("utf-8")
            self.connection.write(payload)
            self.connection.flush()

            response = self._read_response()

            if response:
                return f"Serial TX: {command} | RX: {response}"

            return f"Serial TX: {command} | RX: không có phản hồi"
        except Exception as error:
            self._mark_disconnected()
            raise RuntimeError(
                f"Serial: gửi/đọc lệnh thất bại, đã chuyển sang mất kết nối - {error}"
            ) from error

    def read_line(self) -> str:
        if self.using_mock_connection:
            return "MOCK_OK"

        if not self.is_connection_alive() or self.connection is None:
            raise RuntimeError("Serial chưa kết nối hoặc ESP32 đã bị rút.")

        try:
            data = self.connection.readline()
            return data.decode("utf-8", errors="ignore").strip()
        except Exception as error:
            self._mark_disconnected()
            raise RuntimeError(
                f"Serial: đọc phản hồi thất bại, đã ngắt kết nối - {error}"
            ) from error

    def _read_response(self) -> str:
        """Đọc ACK/ERR từ ESP32 sau một lệnh.

        Hỗ trợ cả 2 kiểu firmware:
        - Trả 1 dòng: ACK HOME
        - Trả 2 dòng: RX: HOME rồi ACK HOME
        """

        if self.connection is None:
            return ""

        lines: list[str] = []
        old_timeout = self.connection.timeout

        try:
            # Đọc từng dòng ngắn để UI không bị treo quá lâu.
            self.connection.timeout = min(float(self.config.timeout), 0.25)
            deadline = time.monotonic() + max(float(self.config.timeout), 0.8)

            while time.monotonic() < deadline:
                raw = self.connection.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                lines.append(line)

                upper_line = line.upper()
                if upper_line.startswith("ACK") or upper_line.startswith("ERR"):
                    break

            return " ; ".join(lines)
        finally:
            self.connection.timeout = old_timeout

    def _clear_input_buffer(self) -> None:
        if self.connection is None:
            return

        try:
            self.connection.reset_input_buffer()
        except Exception:
            pass

    def _physical_ports(self) -> list[str]:
        if list_ports is None:
            return []

        return [port.device for port in list_ports.comports()]

    def _mark_disconnected(self) -> None:
        connection = self.connection
        self.connection = None
        self.connected = False

        if connection is None:
            return

        try:
            if connection.is_open:
                connection.close()
        except Exception:
            pass