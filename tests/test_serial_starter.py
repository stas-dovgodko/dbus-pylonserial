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
        self.assertIn("RUN_DIR=$(pwd)", run_script)
        self.assertIn('for CANDIDATE in "${SERIAL_PORT:-}" "${TTY:-}"', run_script)
        self.assertIn('tty*) SERIAL_PORT="/dev/$DEVICE_NAME"', run_script)
        self.assertIn("Unable to resolve the serial TTY", run_script)
        self.assertIn("TEMPLATE_TARGET=$(readlink -f \"$SERVICE_DIR\"", run_script)
        self.assertIn("Multiple dbus-pylonserial services", run_script)
        self.assertIn('--serial-port "$SERIAL_PORT"', run_script)
        self.assertIn("--serial-starter", run_script)

        log_script = (ROOT / "serial-starter" / "service" / "log" / "run").read_text(
            encoding="utf-8"
        )
        self.assertIn('SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)', log_script)
        self.assertIn('SERVICE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)', log_script)
        self.assertIn("RUN_SERVICE_DIR=${RUN_DIR%/log}", log_script)
        self.assertIn('for CANDIDATE in "${SERIAL_PORT:-}" "${TTY:-}"', log_script)
        self.assertIn("RUN_DIR=$(pwd)", log_script)
        self.assertIn('LOG_DIR="/data/log/dbus-pylonserial.$DEVICE_NAME"', log_script)
        self.assertIn("Unable to resolve the serial TTY", log_script)
        self.assertIn("TEMPLATE_TARGET=$(readlink -f \"$SERVICE_DIR\"", log_script)
        self.assertIn('exec multilog t s25000 n4 "$LOG_DIR"', log_script)

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
        self.assertIn('/var/volatile/services/*', installer)

        stop_position = installer.index("stop-tty.sh")
        clear_link_position = installer.index('rm -f "/dev/serial-starter/$DEVICE_NAME"')
        cache_position = installer.index('rm -f "/data/var/lib/serial-starter/$DEVICE_NAME"')
        restart_position = installer.index("svc -t /service/serial-starter")
        start_position = installer.index("start-tty.sh")
        trigger_position = installer.index("udevadm trigger --action=add")
        self.assertLess(stop_position, clear_link_position)
        self.assertLess(clear_link_position, start_position)
        self.assertLess(stop_position, cache_position)
        self.assertLess(cache_position, restart_position)
        self.assertLess(start_position, restart_position)
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
