#!/usr/bin/env python3
"""Entry point for the Pylontech console D-Bus driver."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
import signal
import sys
import time
from dataclasses import replace

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
    parser.add_argument(
        "--serial-port",
        help="Override serial.port (used by the Venus OS serial-starter template)",
    )
    parser.add_argument(
        "--serial-starter",
        action="store_true",
        help="Exit when device detection or communication fails",
    )
    return parser.parse_args()


def _console(config: DriverConfig) -> PylontechConsole:
    return PylontechConsole(
        port=config.serial.port,
        baudrate=config.serial.baudrate,
        timeout=config.serial.timeout,
        command_delay=config.serial.command_delay,
        expected_modules=config.battery.expected_modules,
    )


def _override_serial_port(config: DriverConfig, port: str) -> DriverConfig:
    return replace(config, serial=replace(config.serial, port=port))


def _probe(config: DriverConfig) -> int:
    console = _console(config)
    try:
        reading = console.read_bank(
            include_details=config.details_poll_interval > 0
        )
        print(json.dumps(reading.as_dict(), indent=2, sort_keys=True))
        return 0
    finally:
        console.close()


def _run(config: DriverConfig, serial_starter: bool = False) -> int:
    if config.service_name.startswith("com.victronenergy.battery."):
        LOGGER.warning(
            "Battery namespace selected; keep this service out of "
            "the active ESS/DVCC battery selection."
        )
    # Register the D-Bus object before probing the serial adapter. A slow or
    # temporarily unavailable adapter must not hide the device from Venus OS.
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    from pylontech_dbus.dbus_service import PylontechModuleServices

    DBusGMainLoop(set_as_default=True)
    service = PylontechModuleServices(config)
    LOGGER.info(
        "D-Bus service %s registered; probing %s",
        config.service_name,
        config.serial.port,
    )
    mainloop = GLib.MainLoop()
    console = _console(config)
    executor = ThreadPoolExecutor(max_workers=1)
    failures = 0
    exit_code = 0
    next_details_poll = (
        time.monotonic() + config.details_poll_interval
        if config.details_poll_interval > 0
        else 0.0
    )
    poll_in_flight = False
    stopping = False

    def publish(reading):
        service.publish(reading)
        LOGGER.info(
            "Read %d modules: %.2f V, %.2f A, %.1f%%",
            len(reading.modules),
            reading.voltage,
            reading.current,
            reading.soc,
        )

    def read_bank(include_details):
        return include_details, console.read_bank(include_details=include_details)

    def complete(future):
        nonlocal exit_code, failures, next_details_poll, poll_in_flight
        poll_in_flight = False
        try:
            include_details, reading = future.result()
            if include_details:
                next_details_poll = time.monotonic() + config.details_poll_interval
            publish(reading)
            failures = 0
        except Exception:
            failures += 1
            LOGGER.exception(
                "Battery poll failed (%d/%d)", failures, config.failure_threshold
            )
            console.close()
            if failures >= config.failure_threshold:
                service.disconnect()
                if serial_starter:
                    exit_code = 1
                    mainloop.quit()
                    return False
        return False

    def poll():
        nonlocal poll_in_flight, next_details_poll
        if stopping or poll_in_flight:
            return True
        include_details = (
            config.details_poll_interval > 0
            and time.monotonic() >= next_details_poll
        )
        if include_details:
            next_details_poll = time.monotonic() + config.details_poll_interval
        poll_in_flight = True
        future = executor.submit(read_bank, include_details)
        future.add_done_callback(
            lambda completed: GLib.idle_add(complete, completed)
        )
        return True

    def stop(_signum, _frame):
        nonlocal stopping
        if stopping:
            return
        stopping = True
        LOGGER.info("Stopping")
        console.close()
        mainloop.quit()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # Start the first poll once. A repeating zero-delay GLib timeout would
    # create a busy-loop while the worker is in flight.
    poll()
    GLib.timeout_add(int(config.poll_interval * 1000), poll)
    LOGGER.info("D-Bus service %s started", config.service_name)
    mainloop.run()
    executor.shutdown(wait=True)
    return exit_code


def main() -> int:
    args = _arguments()
    try:
        config = load_config(args.config)
    except Exception as exc:
        print("Configuration error: {}".format(exc), file=sys.stderr)
        return 2

    if args.serial_port:
        config = _override_serial_port(config, args.serial_port)

    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return _probe(config) if args.probe else _run(config, args.serial_starter)


if __name__ == "__main__":
    raise SystemExit(main())
