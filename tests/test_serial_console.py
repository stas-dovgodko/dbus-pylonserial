import unittest
from unittest.mock import patch

from pylontech_dbus.serial_console import PylontechConsole


class FakeSerial:
    def __init__(self, response):
        self.response = bytearray(response)
        self.writes = []
        self.is_open = True

    @property
    def in_waiting(self):
        return len(self.response)

    def read(self, size):
        result = bytes(self.response[:size])
        del self.response[:size]
        return result

    def write(self, data):
        self.writes.append(data)

    def flush(self):
        pass

    def reset_input_buffer(self):
        pass

    def reset_output_buffer(self):
        pass

    def close(self):
        self.is_open = False


class PagedFakeSerial(FakeSerial):
    def __init__(self):
        super().__init__(b"first page\r\n--more--")
        self.next_page = b"\r\nsecond page\r\npylon>"

    def write(self, data):
        super().write(data)
        if data == b"\n" and self.next_page:
            self.response.extend(self.next_page)
            self.next_page = b""


class SerialConsoleSafetyTest(unittest.TestCase):
    def test_refuses_port_already_used_by_another_process(self):
        console = PylontechConsole("/dev/ttyUSB0")
        with patch(
            "pylontech_dbus.serial_console.find_serial_port_users",
            return_value=["PID 42 (existing-driver)"],
        ):
            with self.assertRaisesRegex(RuntimeError, "already open"):
                console._connection()

    def test_probe_sends_only_read_only_pwr_command(self):
        serial = FakeSerial(b"Power Volt\r\npylon>")
        console = PylontechConsole("/dev/ttyUSB0", serial_connection=serial)

        self.assertEqual(b"Power Volt\r\npylon>", console.read_pwr_response())
        self.assertEqual([b"pwr\n"], serial.writes)

    def test_rejects_commands_outside_read_only_allowlist(self):
        serial = FakeSerial(b"pylon>")
        console = PylontechConsole("/dev/ttyUSB0", serial_connection=serial)

        with self.assertRaisesRegex(ValueError, "read-only allowlist"):
            console.execute_read_only("config")

        self.assertEqual([], serial.writes)

    def test_continues_paginated_read_only_response(self):
        serial = PagedFakeSerial()
        console = PylontechConsole(
            "/dev/ttyUSB0", command_delay=0, serial_connection=serial
        )

        response = console.execute_read_only("info 1")

        self.assertIn(b"second page", response)
        self.assertEqual([b"info 1\n", b"\n"], serial.writes)


if __name__ == "__main__":
    unittest.main()
