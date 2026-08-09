from __future__ import annotations

from dataclasses import dataclass
import socket


@dataclass
class NetworkConfig:
    host: str = "192.168.4.1"
    port: int = 5000
    timeout: float = 2.0


class NetworkService:
    """
    Gửi lệnh điều khiển ESP32 qua Wi-Fi TCP.

    ESP32 đang chạy SoftAP:
    - SSID: GANTRY_ESP32
    - IP mặc định: 192.168.4.1
    - TCP port: 5000

    Service này cố tình dùng giao thức giống SerialService:
    - connect()
    - disconnect()
    - send_command()
    - connected
    """

    def __init__(self, config: NetworkConfig | None = None) -> None:
        self.config = config or NetworkConfig()
        self.connected = False

    def set_host(self, host: str) -> None:
        host = host.strip()

        if not host:
            raise ValueError("Địa chỉ IP ESP32 rỗng.")

        if self.connected:
            raise RuntimeError("Không thể đổi IP khi đang kết nối Wi-Fi ESP32.")

        self.config.host = host

    def set_port(self, port: int) -> None:
        if port <= 0:
            raise ValueError("Port TCP không hợp lệ.")

        if self.connected:
            raise RuntimeError("Không thể đổi port khi đang kết nối Wi-Fi ESP32.")

        self.config.port = int(port)

    def connect(self) -> str:
        response = self._send_raw("PING")

        if not response.startswith("ACK"):
            self.connected = False
            raise RuntimeError(
                f"Wi-Fi ESP32: phản hồi không hợp lệ từ "
                f"{self.config.host}:{self.config.port} - {response}"
            )

        self.connected = True
        return (
            f"Wi-Fi ESP32: đã kết nối tới "
            f"{self.config.host}:{self.config.port}."
        )

    def disconnect(self) -> str:
        if not self.connected:
            return "Wi-Fi ESP32: hiện chưa kết nối."

        self.connected = False
        return "Wi-Fi ESP32: đã ngắt kết nối."

    def is_connection_alive(self) -> bool:
        if not self.connected:
            return False

        try:
            response = self._send_raw("PING")
            return response.startswith("ACK")
        except Exception:
            self.connected = False
            return False

    def send_command(self, command: str) -> str:
        command = command.strip()

        if not command:
            raise ValueError("Lệnh Network rỗng.")

        if not self.connected:
            raise RuntimeError("Wi-Fi ESP32 chưa kết nối.")

        try:
            response = self._send_raw(command)

            if response:
                return f"Network TX: {command} | RX: {response}"

            return f"Network TX: {command} | RX: không có phản hồi"

        except Exception as error:
            self.connected = False
            raise RuntimeError(
                f"Wi-Fi ESP32: gửi/đọc lệnh thất bại, đã ngắt kết nối - {error}"
            ) from error

    def _send_raw(self, command: str) -> str:
        with socket.create_connection(
            (self.config.host, self.config.port),
            timeout=self.config.timeout,
        ) as sock:
            payload = f"{command.strip()}\n".encode("utf-8")
            sock.sendall(payload)

            response = sock.recv(1024).decode(
                "utf-8",
                errors="ignore",
            ).strip()

        return response