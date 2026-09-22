"""Serial transport for the Pylontech/Pytes console protocol."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import replace
from typing import Optional

from .models import BankReading
from .parser import (
    parse_bat_response,
    parse_info_response,
    parse_pwr_response,
    parse_stat_response,
)
from .port_guard import find_serial_port_users


PROMPTS = (b"PYTES>", b"PYTES_debug>", b"pylon>", b"pylon_debug>")
PAGING_MARKERS = (b"[enter]", b"--more--", b"-- more --", b"continued")
READ_ONLY_COMMAND = re.compile(
    r"^(?:pwr|info|stat|(?:bat|info|stat) [1-9][0-9]*)$"
)
LOGGER = logging.getLogger(__name__)


class ConsoleTimeout(TimeoutError):
    """Raised when the battery console does not return a complete response."""


class PylontechConsole:
    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 5.0,
        command_delay: float = 1.2,
        expected_modules: int = 0,
        serial_connection: Optional[object] = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.command_delay = command_delay
        self.expected_modules = expected_modules
        self._serial = serial_connection
        self._metadata = {}
        self._statistics = {}
        self._cells = {}
        self._last_command_at = None
        self._reported_detail_failures = set()

    def _report_detail_failure(self, command: str, error: Exception) -> None:
        if command not in self._reported_detail_failures:
            LOGGER.warning("%s is unavailable: %s", command, error)
            self._reported_detail_failures.add(command)
        else:
            LOGGER.debug("%s is unavailable: %s", command, error)

    def _detail_succeeded(self, command: str) -> None:
        self._reported_detail_failures.discard(command)

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
                write_timeout=self.timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
                exclusive=True,
            )
            self._serial.dtr = False
            self._serial.rts = False
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
        paging_scan_from = 0

        while time.monotonic() < deadline:
            waiting = getattr(connection, "in_waiting", 0)
            if waiting:
                response.extend(connection.read(waiting))
                if any(prompt in response for prompt in PROMPTS):
                    return bytes(response)
                new_data = bytes(response[paging_scan_from:]).lower()
                if any(marker in new_data for marker in PAGING_MARKERS):
                    connection.write(b"\n")
                    connection.flush()
                    paging_scan_from = len(response)
                    deadline = time.monotonic() + self.timeout
                if len(response) > 65536:
                    raise ConsoleTimeout("The console response exceeded 64 KiB")
            else:
                time.sleep(0.01)

        raise ConsoleTimeout(
            "Timed out after {:.1f}s waiting for a Pylontech console prompt".format(
                self.timeout
            )
        )

    def execute_read_only(self, command: str) -> bytes:
        """Execute one explicitly allowlisted, read-only console command."""

        if not READ_ONLY_COMMAND.fullmatch(command):
            raise ValueError("Console command is not in the read-only allowlist")
        connection = self._connection()
        if self._last_command_at is not None:
            remaining = self.command_delay - (
                time.monotonic() - self._last_command_at
            )
            if remaining > 0:
                time.sleep(remaining)
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

            connection.write((command + "\n").encode("ascii"))
            connection.flush()
            self._last_command_at = time.monotonic()
            try:
                return self._read_until_prompt()
            except ConsoleTimeout as exc:
                last_timeout = exc

        raise last_timeout or ConsoleTimeout(
            "No complete response received for {}".format(command)
        )

    def read_pwr_response(self) -> bytes:
        """Run the read-only ``pwr`` command and return its raw response."""

        return self.execute_read_only("pwr")

    def _read_module_details(self, reading: BankReading) -> None:
        for module in reading.modules:
            number = module.number
            if number not in self._metadata:
                try:
                    self._metadata[number] = parse_info_response(
                        self.execute_read_only("info {}".format(number)), number
                    )
                    self._detail_succeeded("info {}".format(number))
                except Exception as exc:
                    LOGGER.debug("info %d is unavailable: %s", number, exc)
                    if number == 1:
                        try:
                            self._metadata[number] = parse_info_response(
                                self.execute_read_only("info"), number
                            )
                            self._detail_succeeded("info")
                        except Exception as fallback_exc:
                            self._report_detail_failure("info", fallback_exc)
                    else:
                        self._report_detail_failure(
                            "info {}".format(number), exc
                        )

            try:
                self._statistics[number] = parse_stat_response(
                    self.execute_read_only("stat {}".format(number)), number
                )
                self._detail_succeeded("stat {}".format(number))
            except Exception as exc:
                LOGGER.debug("stat %d is unavailable: %s", number, exc)
                if number == 1:
                    try:
                        self._statistics[number] = parse_stat_response(
                            self.execute_read_only("stat"), number
                        )
                        self._detail_succeeded("stat")
                    except Exception as fallback_exc:
                        self._report_detail_failure("stat", fallback_exc)
                else:
                    self._report_detail_failure("stat {}".format(number), exc)

            metadata = self._metadata.get(number)
            try:
                cells = parse_bat_response(
                    self.execute_read_only("bat {}".format(number))
                )
                self._detail_succeeded("bat {}".format(number))
                self._cells[number] = cells
                if (
                    metadata
                    and metadata.cell_count
                    and len(cells) != metadata.cell_count
                ):
                    LOGGER.warning(
                        "Module %d reports %d cells in info but bat returned %d",
                        number,
                        metadata.cell_count,
                        len(cells),
                    )
            except Exception as exc:
                self._report_detail_failure("bat {}".format(number), exc)

    def _merge_details(self, reading: BankReading) -> BankReading:
        return BankReading.from_modules(
            replace(
                module,
                metadata=self._metadata.get(module.number),
                statistics=self._statistics.get(module.number),
                cells=self._cells.get(module.number, ()),
            )
            for module in reading.modules
        )

    def read_bank(self, include_details: bool = False) -> BankReading:
        response = self.read_pwr_response()
        reading = parse_pwr_response(response, self.expected_modules)
        if include_details:
            self._read_module_details(reading)
        return self._merge_details(reading)
