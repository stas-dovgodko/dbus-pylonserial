import os
import tempfile
import unittest

from pylontech_dbus.config import load_config


class ConfigTest(unittest.TestCase):
    def test_loads_valid_config(self):
        content = """[serial]
port=/dev/ttyUSB0
[battery]
expected_modules=4
module_capacity_ah=100
max_modules=8
[driver]
poll_interval=5
failure_threshold=3
device_instance=288
service_name=com.victronenergy.pylontechmonitor.rs232
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(content)
            path = handle.name
        try:
            config = load_config(path)
        finally:
            os.unlink(path)

        self.assertEqual("/dev/ttyUSB0", config.serial.port)
        self.assertEqual(4, config.battery.expected_modules)
        self.assertEqual(100.0, config.battery.module_capacity_ah)

    def test_rejects_victron_battery_namespace(self):
        content = """[serial]
port=/dev/ttyUSB0
[battery]
[driver]
service_name=com.victronenergy.battery.pylontech_console
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(content)
            path = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "isolated"):
                load_config(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
