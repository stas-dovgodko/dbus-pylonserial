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


if __name__ == "__main__":
    unittest.main()
