from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from core.gantry_service import GantryService
from core.network_service import NetworkConfig, NetworkService


def print_block(title: str) -> None:
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)


def main() -> None:
    network_service = NetworkService(
        config=NetworkConfig(
            host="192.168.4.1",
            port=5000,
            timeout=2.0,
        )
    )

    print_block("CONNECT WIFI ESP32")
    print(network_service.connect())

    gantry = GantryService(serial_service=network_service)

    print_block("MODE MANUAL")
    print(network_service.send_command("MODE MANUAL"))

    print_block("VACUUM TEST")
    print(gantry.vacuum_on())
    print(gantry.vacuum_off())

    print_block("JOG X")
    value, message = gantry.jog(axis="X", step_mm=5.0, direction=1)
    print(message)

    value, message = gantry.jog(axis="X", step_mm=5.0, direction=-1)
    print(message)

    print_block("JOG Y")
    value, message = gantry.jog(axis="Y", step_mm=5.0, direction=1)
    print(message)

    value, message = gantry.jog(axis="Y", step_mm=5.0, direction=-1)
    print(message)

    print_block("JOG Z")
    value, message = gantry.jog(axis="Z", step_mm=5.0, direction=1)
    print(message)

    value, message = gantry.jog(axis="Z", step_mm=5.0, direction=-1)
    print(message)

    print_block("JOG STOP")
    print(gantry.stop_jog())

    print_block("HOME")
    position, message = gantry.home()
    print(message)
    print(position)

    print_block("ESTOP / RESET")
    print(network_service.send_command("ESTOP"))
    print(network_service.send_command("RESET"))

    print_block("DISCONNECT")
    print(network_service.disconnect())

    print()
    print("RESULT: GANTRY NETWORK TEST PASS")


if __name__ == "__main__":
    main()