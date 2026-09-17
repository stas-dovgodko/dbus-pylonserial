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

        self.assertIn('SERVICE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)', run_script)
        self.assertIn("for SERVICE_PATH in /service/dbus-pylonserial.*", run_script)
        self.assertIn("SERVICE_NAME=${SERVICE_PATH##*.}", run_script)
        self.assertIn('tty*) SERIAL_PORT="/dev/$DEVICE_NAME"', run_script)
        self.assertIn('--serial-port "$SERIAL_PORT"', run_script)
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

        stop_position = installer.index("stop-tty.sh")
        cache_position = installer.index('rm -f "/data/var/lib/serial-starter/$DEVICE_NAME"')
        restart_position = installer.index("svc -t /service/serial-starter")
        start_position = installer.index("start-tty.sh")
        trigger_position = installer.index("udevadm trigger --action=add")
        self.assertLess(stop_position, cache_position)
        self.assertLess(cache_position, restart_position)
        self.assertLess(restart_position, start_position)
        self.assertIn(
            "run_tty_helper /opt/victronenergy/serial-starter/stop-tty.sh",
            installer,
        )
        self.assertIn(
            "run_tty_helper /opt/victronenergy/serial-starter/start-tty.sh",
            installer,
        )
        self.assertLess(start_position, trigger_position)
        self.assertIn("elif udevadm trigger", installer)

    def test_serial_port_override_does_not_change_other_settings(self):
        config = DriverConfig(
            serial=SerialConfig("/dev/ttyUSB0", 115200, 5.0),
            battery=BatteryConfig(5, 0.0, "Pylontech RS232", 16, 16),
            poll_interval=5.0,
            details_poll_interval=60.0,
            failure_threshold=3,
            device_instance=288,
            service_name="com.victronenergy.unsupported.pylontechmonitor_rs232",
            log_level="INFO",
        )

        updated = _override_serial_port(config, "/dev/ttyUSB7")

        self.assertEqual("/dev/ttyUSB7", updated.serial.port)
        self.assertEqual(config.battery, updated.battery)
        self.assertEqual(config.service_name, updated.service_name)

    def test_detection_failure_exits_before_dbus_start(self):
        config = DriverConfig(
            serial=SerialConfig("/dev/ttyUSB0", 115200, 5.0),
            battery=BatteryConfig(5, 0.0, "Pylontech RS232", 16, 16),
            poll_interval=5.0,
            details_poll_interval=60.0,
            failure_threshold=3,
            device_instance=288,
            service_name="com.victronenergy.unsupported.pylontechmonitor_rs232",
            log_level="INFO",
        )

        class FailingConsole:
            def __init__(self):
                self.closed = False

            def read_bank(self, include_details=False):
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
