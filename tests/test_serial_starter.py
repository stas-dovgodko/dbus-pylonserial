import pathlib
import unittest
from unittest.mock import patch

from main import _override_serial_port, _run
from pylontech_dbus.config import BatteryConfig, DriverConfig, SerialConfig


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SerialStarterTest(unittest.TestCase):
    def test_template_uses_tty_override_and_detection_mode(self):
        run_script = (
            ROOT / "serial-starter" / "service" / "run"
        ).read_text(encoding="utf-8")

        self.assertIn("--serial-port /dev/TTY", run_script)
        self.assertIn("--serial-starter", run_script)

    def test_uninstaller_preserves_application_and_config(self):
        uninstaller = (ROOT / "uninstall.sh").read_text(encoding="utf-8")

        self.assertNotIn('rm -rf "$APP_DIR"', uninstaller)
        self.assertNotIn('rm -f "$APP_DIR/config.ini"', uninstaller)
        self.assertIn("Leaving foreign symlink untouched", uninstaller)

    def test_installer_prefers_unique_serial_then_physical_path(self):
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")

        self.assertLess(installer.index("ID_SERIAL_SHORT"), installer.index("ID_PATH_VALUE"))
        self.assertIn('ENV{ID_SERIAL_SHORT}', installer)
        self.assertIn('ENV{ID_PATH}', installer)
        self.assertNotIn("platform-1c14400.usb-usb-0:1:1.0", installer)
        self.assertNotIn('ENV{ID_MODEL}==', installer)
        self.assertNotIn('rm -rf /data/var/lib/serial-starter', installer)

    def test_serial_port_override_does_not_change_other_settings(self):
        config = DriverConfig(
            serial=SerialConfig("/dev/ttyUSB0", 115200, 5.0),
            battery=BatteryConfig(5, 0.0, "Pylontech RS232", 16),
            poll_interval=5.0,
            failure_threshold=3,
            device_instance=288,
            service_name="com.victronenergy.pylontechmonitor.rs232",
            log_level="INFO",
        )

        updated = _override_serial_port(config, "/dev/ttyUSB7")

        self.assertEqual("/dev/ttyUSB7", updated.serial.port)
        self.assertEqual(config.battery, updated.battery)
        self.assertEqual(config.service_name, updated.service_name)

    def test_detection_failure_exits_before_dbus_start(self):
        config = DriverConfig(
            serial=SerialConfig("/dev/ttyUSB0", 115200, 5.0),
            battery=BatteryConfig(5, 0.0, "Pylontech RS232", 16),
            poll_interval=5.0,
            failure_threshold=3,
            device_instance=288,
            service_name="com.victronenergy.pylontechmonitor.rs232",
            log_level="INFO",
        )

        class FailingConsole:
            def __init__(self):
                self.closed = False

            def read_bank(self):
                raise TimeoutError("not a Pylontech console")

            def close(self):
                self.closed = True

        console = FailingConsole()
        with self.assertLogs("dbus-pylontech-console", level="ERROR"):
            with patch("main._console", return_value=console):
                result = _run(config, serial_starter=True)

        self.assertEqual(1, result)
        self.assertTrue(console.closed)


if __name__ == "__main__":
    unittest.main()
