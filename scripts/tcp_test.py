from __future__ import annotations

import socket
import time


ESP32_HOST = "192.168.4.1"
ESP32_PORT = 5000
TIMEOUT = 2.0


def send_command(command: str) -> bool:
    try:
        with socket.create_connection(
            (ESP32_HOST, ESP32_PORT),
            timeout=TIMEOUT,
        ) as sock:
            payload = f"{command.strip()}\n".encode("utf-8")
            sock.sendall(payload)

            response = sock.recv(1024).decode(
                "utf-8",
                errors="ignore",
            ).strip()

        print(f"TX: {command} | RX: {response}")
        return response.startswith("ACK")

    except Exception as error:
        print(f"TX: {command} | ERROR: {error}")
        return False


def main() -> None:
    commands = [
        "PING",
        "MODE MANUAL",
        "VACUUM ON",
        "VACUUM OFF",
        "JOG X + 5.0",
        "JOG X - 5.0",
        "JOG Y + 5.0",
        "JOG Y - 5.0",
        "JOG Z + 5.0",
        "JOG Z - 5.0",
        "JOG STOP",
        "HOME",
        "AUTO START",
        "AUTO PAUSE",
        "AUTO RESUME",
        "ESTOP",
        "RESET",
    ]

    passed = 0

    for command in commands:
        if send_command(command):
            passed += 1

        time.sleep(0.15)

    total = len(commands)

    print()
    print(f"RESULT: {passed}/{total} PASS")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()