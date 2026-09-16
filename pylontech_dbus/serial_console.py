"""Serial transport for the Pylontech/Pytes console protocol."""

from __future__ import annotations

import time
from typing import Optional

from .models import BankReading
from .parser import parse_pwr_response
from .port_guard import find_serial_port_users


PROMPTS = (b"PYTES>", b"PYTES_debug>", b"pylon>", b"pylon_debug>")
PWR_COMMAND = b"pwr\n"


class ConsoleTimeout(TimeoutError):
    """Raised when the battery console does not return a complete response."""


class PylontechConsole:
    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 5.0,
        expected_modules: int = 0,
        serial_connection: Optional[object] = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.expected_modules = expected_modules
        self._serial = serial_connection

    def _connection(self):
        if self._serial is None:
            users = find_serial_port_users(self.port)
            if users:
                raise RuntimeError(
                    "Serial port {} is already open by: {}".format(
                        self.port, ", ".join(users)
                    )
                )
            try:
                import serial
            except ImportError as exc:
                raise RuntimeError(
                    "pyserial is required on the target system (import serial failed)"
                ) from exc

            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0,
                exclusive=True,
            )
        elif hasattr(self._serial, "is_open") and not self._serial.is_open:
            self._serial.open()
        return self._serial

    def close(self) -> None:
        if self._serial is not None and getattr(self._serial, "is_open", False):
            self._serial.close()

    def _read_until_prompt(self) -> bytes:
        connection = self._connection()
        deadline = time.monotonic() + self.timeout
        response = bytearray()

        while time.monotonic() < deadline:
            waiting = getattr(connection, "in_waiting", 0)
            if waiting:
                response.extend(connection.read(waiting))
                if any(prompt in response for prompt in PROMPTS):
                    return bytes(response)
                if len(response) > 65536:
                    raise ConsoleTimeout("The console response exceeded 64 KiB")
            else:
                time.sleep(0.01)

        raise ConsoleTimeout(
            "Timed out after {:.1f}s waiting for a Pylontech console prompt".format(
                self.timeout
            )
        )

    def read_pwr_response(self) -> bytes:
        """Run the read-only ``pwr`` command and return its raw response."""

        connection = self._connection()
        last_timeout = None
        for attempt in range(2):
            if hasattr(connection, "reset_input_buffer"):
                connection.reset_input_buffer()
            if hasattr(connection, "reset_output_buffer"):
                connection.reset_output_buffer()

            if attempt:
                # A blank line wakes console firmware that ignored the first command.
                connection.write(b"\n")
                connection.flush()
                time.sleep(0.2)
                if hasattr(connection, "reset_input_buffer"):
                    connection.reset_input_buffer()

            connection.write(PWR_COMMAND)
            connection.flush()
            try:
                return self._read_until_prompt()
            except ConsoleTimeout as exc:
                last_timeout = exc

        raise last_timeout or ConsoleTimeout("No complete pwr response received")

    def read_bank(self) -> BankReading:
        response = self.read_pwr_response()
        return parse_pwr_response(response, self.expected_modules)
