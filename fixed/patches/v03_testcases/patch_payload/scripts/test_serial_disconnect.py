"""Regression test cho lỗi rút ESP32 nhưng giao diện vẫn báo xanh."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import core.serial_service as serial_module
from core.serial_service import SerialConfig, SerialService


class FakeConnection:
    def __init__(self, **kwargs) -> None:
        self.port = kwargs["port"]
        self.is_open = True
        self.written: list[bytes] = []

    @property
    def in_waiting(self) -> int:
        if not self.is_open:
            raise OSError("port closed")
        return 0

    def write(self, payload: bytes) -> None:
        if not self.is_open:
            raise OSError("device removed")
        self.written.append(payload)

    def flush(self) -> None:
        if not self.is_open:
            raise OSError("device removed")

    def close(self) -> None:
        self.is_open = False


class FakeSerialPackage:
    Serial = FakeConnection


class FakePorts:
    available = ["COM3"]

    @classmethod
    def comports(cls):
        return [SimpleNamespace(device=name) for name in cls.available]


def main() -> None:
    original_serial = serial_module.serial
    original_ports = serial_module.list_ports

    try:
        serial_module.serial = FakeSerialPackage
        serial_module.list_ports = FakePorts

        service = SerialService(
            SerialConfig(port="COM3", baudrate=115200, timeout=0.2),
            mock_mode=True,
        )

        # Dù mock_mode=True, chọn COM thật phải mở kết nối thật.
        message = service.connect()
        assert service.connected is True
        assert service.using_mock_connection is False
        assert "COM3" in message
        assert service.is_connection_alive() is True
        print("[PASS] COM thật không bị biến thành kết nối mock.")

        # Mô phỏng rút USB: COM3 biến mất khỏi danh sách Windows.
        FakePorts.available = []

        assert service.is_connection_alive() is False
        assert service.connected is False
        print("[PASS] Rút COM: service tự chuyển sang disconnected.")

        # MOCK_COM vẫn dùng được để test UI không cần phần cứng.
        mock_service = SerialService(
            SerialConfig(port="MOCK_COM"),
            mock_mode=True,
        )
        mock_service.connect()
        assert mock_service.using_mock_connection is True
        assert mock_service.is_connection_alive() is True
        print("[PASS] MOCK_COM vẫn hoạt động độc lập.")

    finally:
        serial_module.serial = original_serial
        serial_module.list_ports = original_ports


if __name__ == "__main__":
    main()
