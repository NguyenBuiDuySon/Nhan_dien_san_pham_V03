from __future__ import annotations

from dataclasses import dataclass

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
    - Chỉ dùng mock khi ``mock_mode=True`` và port là ``MOCK_COM``.
    - Nếu người dùng chọn COM thật, service luôn mở cổng thật. Cách này tránh
      tình trạng giao diện báo xanh giả dù ESP32 chưa thực sự được mở.

    Service cũng có ``is_connection_alive()`` để app kiểm tra cổng định kỳ.
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

        # Không cho kết nối vào tên COM đã biến mất khỏi Windows.
        physical_ports = self._physical_ports()

        if self.config.port not in physical_ports:
            raise RuntimeError(
                f"Serial: không tìm thấy cổng {self.config.port}. "
                "Hãy quét COM và cắm lại ESP32."
            )

        try:
            self.connection = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout,
                write_timeout=self.config.timeout,
            )
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
        """Kiểm tra thiết bị còn thực sự tồn tại hay không.

        Với COM thật, chỉ ``connection.is_open`` chưa đủ vì Windows đôi khi vẫn
        giữ handle mở một lúc sau khi rút USB. Vì vậy service kiểm tra thêm:
        1. Tên COM còn nằm trong danh sách cổng của hệ điều hành.
        2. Thuộc tính ``in_waiting`` còn đọc được mà không phát sinh lỗi.
        """

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

            # Truy cập driver để phát hiện USB đã bị rút.
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

        payload = f"{command}\n"

        if self.using_mock_connection:
            self.sent_commands.append(command)
            return f"Serial mock TX: {command}"

        try:
            assert self.connection is not None
            self.connection.write(payload.encode("utf-8"))
            self.connection.flush()
            return f"Serial TX: {command}"
        except Exception as error:
            self._mark_disconnected()
            raise RuntimeError(
                f"Serial: gửi lệnh thất bại, đã chuyển sang mất kết nối - {error}"
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
            # Khi USB bị rút, close() cũng có thể ném lỗi. Trạng thái nội bộ
            # vẫn phải được đưa về disconnected.
            pass
