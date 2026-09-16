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
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.expected_modules < 0:
        print("--expected-modules cannot be negative", file=sys.stderr)
        return 2

    console = PylontechConsole(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout,
        expected_modules=args.expected_modules,
    )
    try:
        response = console.read_pwr_response()
        if args.raw:
            sys.stdout.write(response.decode("latin-1", errors="replace"))
            if not response.endswith(b"\n"):
                sys.stdout.write("\n")
        else:
            from pylontech_dbus.parser import parse_pwr_response

            reading = parse_pwr_response(response, args.expected_modules)
            print(json.dumps(reading.as_dict(), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print("Probe failed: {}".format(exc), file=sys.stderr)
        return 1
    finally:
        console.close()


if __name__ == "__main__":
    raise SystemExit(main())
