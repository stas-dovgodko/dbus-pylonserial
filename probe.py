#!/usr/bin/env python3
"""Read Pylontech console data without creating or accessing a D-Bus service."""

from __future__ import annotations

import argparse
import json
import sys

from pylontech_dbus.serial_console import PylontechConsole


def _arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Run the read-only Pylontech pwr command without publishing data "
            "or connecting to D-Bus"
        )
    )
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial device")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--command-delay",
        type=float,
        default=1.2,
        help="Minimum delay between console commands",
    )
    parser.add_argument(
        "--expected-modules",
        type=int,
        default=0,
        help="Expected module count; 0 enables discovery",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the unparsed console response instead of JSON",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help=(
            "Also run allowlisted info/stat/bat queries for serial numbers, "
            "cycles, SOH, and cell data"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.expected_modules < 0:
        print("--expected-modules cannot be negative", file=sys.stderr)
        return 2
    if args.command_delay < 0:
        print("--command-delay cannot be negative", file=sys.stderr)
        return 2

    console = PylontechConsole(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout,
        command_delay=args.command_delay,
        expected_modules=args.expected_modules,
    )
    try:
        if args.raw:
            response = console.read_pwr_response()
            sys.stdout.write(response.decode("latin-1", errors="replace"))
            if not response.endswith(b"\n"):
                sys.stdout.write("\n")
        else:
            reading = console.read_bank(include_details=args.details)
            print(json.dumps(reading.as_dict(), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print("Probe failed: {}".format(exc), file=sys.stderr)
        return 1
    finally:
        console.close()


if __name__ == "__main__":
    raise SystemExit(main())
