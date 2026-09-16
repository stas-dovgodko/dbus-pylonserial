"""Best-effort detection of processes already using a serial device."""

from __future__ import annotations

import glob
import os
from typing import Dict, List


def _process_name(process_directory: str) -> str:
    try:
        with open(os.path.join(process_directory, "cmdline"), "rb") as handle:
            command = handle.read().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        return command.strip() or "unknown"
    except OSError:
        return "unknown"


def find_serial_port_users(port: str) -> List[str]:
    """Return processes that already have ``port`` open on a procfs system."""

    if os.name != "posix" or not os.path.isdir("/proc"):
        return []

    target = os.path.realpath(port)
    users: Dict[int, str] = {}
    for process_directory in glob.glob("/proc/[0-9]*"):
        try:
            pid = int(os.path.basename(process_directory))
        except ValueError:
            continue
        if pid == os.getpid():
            continue

        for descriptor in glob.glob(os.path.join(process_directory, "fd", "*")):
            try:
                if os.path.realpath(descriptor) == target:
                    users[pid] = _process_name(process_directory)
                    break
            except OSError:
                continue

    return ["PID {} ({})".format(pid, users[pid]) for pid in sorted(users)]
