import os
import sys
import tempfile
import types
import unittest

from pylontech_dbus.config import load_config
from pylontech_dbus.dbus_service import PylontechDbusService
from pylontech_dbus.parser import parse_pwr_response

from tests.test_parser import PWR_RESPONSE


class FakeVeDbusService:
    def __init__(self, name, bus=None, register=None):
        self.name = name
        self.values = {}
        self.registered = False

    def add_path(self, path, value=None, **_arguments):
        self.values[path] = value

    def register(self):
        self.registered = True

    def __setitem__(self, path, value):
        self.values[path] = value

    def __getitem__(self, path):
        return self.values[path]


class DbusServiceTest(unittest.TestCase):
    def setUp(self):
        self.original_vedbus = sys.modules.get("vedbus")
        sys.modules["vedbus"] = types.SimpleNamespace(VeDbusService=FakeVeDbusService)
        content = """[serial]
port=/dev/ttyUSB0
[battery]
expected_modules=4
module_capacity_ah=100
max_modules=4
[driver]
poll_interval=5
failure_threshold=3
device_instance=288
service_name=com.victronenergy.pylontechmonitor.rs232
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(content)
            self.path = handle.name

    def tearDown(self):
        os.unlink(self.path)
        if self.original_vedbus is None:
            sys.modules.pop("vedbus", None)
        else:
            sys.modules["vedbus"] = self.original_vedbus

    def test_publishes_monitor_values_and_clears_stale_data(self):
        config = load_config(self.path)
        service = PylontechDbusService(config)
        reading = parse_pwr_response(PWR_RESPONSE, expected_modules=4)

        service.publish(reading)
        values = service._service.values
        self.assertEqual(1, values["/Connected"])
        self.assertEqual(68.5, values["/Soc"])
        self.assertEqual(-13.08, values["/Dc/0/Current"])
        self.assertEqual(400.0, values["/InstalledCapacity"])
        self.assertEqual(274.0, values["/Capacity"])
        self.assertEqual(1, values["/Modules/4/Online"])
        self.assertFalse(any(path.startswith("/Info/") for path in values))

        service.disconnect()
        self.assertEqual(0, values["/Connected"])
        self.assertEqual(2, values["/Alarms/BmsCable"])
        self.assertIsNone(values["/Dc/0/Voltage"])
        self.assertEqual(4, values["/System/NrOfModulesOffline"])


if __name__ == "__main__":
    unittest.main()
