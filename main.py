#!/usr/bin/env python3
"""Entry point for the Pylontech console D-Bus driver."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys

from pylontech_dbus.config import DriverConfig, load_config
from pylontech_dbus.serial_console import PylontechConsole


LOGGER = logging.getLogger("dbus-pylontech-console")


def _arguments():
    parser = argparse.ArgumentParser(
        description="Publish Pylontech RS232 console readings on Victron D-Bus"
    )
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini"),
        help="Path to the INI configuration file",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Read one pwr response and print JSON without starting D-Bus",
    )
    return parser.parse_args()


def _console(config: DriverConfig) -> PylontechConsole:
    return PylontechConsole(
        port=config.serial.port,
        baudrate=config.serial.baudrate,
        timeout=config.serial.timeout,
        expected_modules=config.battery.expected_modules,
    )


def _probe(config: DriverConfig) -> int:
    console = _console(config)
    try:
        reading = console.read_bank()
        print(json.dumps(reading.as_dict(), indent=2, sort_keys=True))
        return 0
    finally:
        console.close()


def _run(config: DriverConfig) -> int:
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    from pylontech_dbus.dbus_service import PylontechDbusService

    DBusGMainLoop(set_as_default=True)
    console = _console(config)
    service = PylontechDbusService(config)
    mainloop = GLib.MainLoop()
    failures = 0

    def poll():
        nonlocal failures
        try:
            reading = console.read_bank()
            service.publish(reading)
            failures = 0
            LOGGER.info(
                "Read %d modules: %.2f V, %.2f A, %.1f%%",
                len(reading.modules),
                reading.voltage,
                reading.current,
                reading.soc,
            )
        except Exception:
            failures += 1
            LOGGER.exception(
                "Battery poll failed (%d/%d)", failures, config.failure_threshold
            )
            console.close()
            if failures >= config.failure_threshold:
                service.disconnect()
        return True

    def stop(_signum, _frame):
        LOGGER.info("Stopping")
        console.close()
        mainloop.quit()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    poll()
    GLib.timeout_add(int(config.poll_interval * 1000), poll)
    LOGGER.info("D-Bus service %s started", config.service_name)
    mainloop.run()
    return 0


def main() -> int:
    args = _arguments()
    try:
        config = load_config(args.config)
    except Exception as exc:
        print("Configuration error: {}".format(exc), file=sys.stderr)
        return 2

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return _probe(config) if args.probe else _run(config)


if __name__ == "__main__":
    raise SystemExit(main())
