"""Configuration loading and validation."""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass


SAFE_SERVICE_NAME_RE = re.compile(
    r"^com\.victronenergy\.(?:"
    r"pylontechmonitor\.[A-Za-z0-9_]+|"
    r"unsupported\.pylontechmonitor_[A-Za-z0-9_]+|"
    r"telemetry\.pylontechmonitor_[A-Za-z0-9_]+|"
    r"battery\.pylontechmonitor_[A-Za-z0-9_]+|"
    r"dcload\.pylontechmonitor_[A-Za-z0-9_]+)$"
)


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baudrate: int
    timeout: float
    command_delay: float = 1.2


@dataclass(frozen=True)
class BatteryConfig:
    expected_modules: int
    module_capacity_ah: float
    custom_name: str
    max_modules: int
    max_cells_per_module: int


@dataclass(frozen=True)
class DriverConfig:
    serial: SerialConfig
    battery: BatteryConfig
    poll_interval: float
    details_poll_interval: float
    failure_threshold: int
    device_instance: int
    service_name: str
    log_level: str
    # Maximum time a single serial poll may occupy the worker thread.
    poll_timeout: float = 120.0


def load_config(path: str) -> DriverConfig:
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise ValueError("Configuration file not found: {}".format(path))

    serial_section = parser["serial"]
    battery_section = parser["battery"]
    driver_section = parser["driver"]

    serial_config = SerialConfig(
        port=serial_section.get("port", "").strip(),
        baudrate=serial_section.getint("baudrate", 115200),
        timeout=serial_section.getfloat("timeout", 5.0),
        command_delay=serial_section.getfloat("command_delay", 1.2),
    )
    battery_config = BatteryConfig(
        expected_modules=battery_section.getint("expected_modules", 0),
        module_capacity_ah=battery_section.getfloat("module_capacity_ah", 0.0),
        custom_name=battery_section.get("custom_name", "Pylontech RS232").strip(),
        max_modules=battery_section.getint("max_modules", 16),
        max_cells_per_module=battery_section.getint("max_cells_per_module", 16),
    )
    config = DriverConfig(
        serial=serial_config,
        battery=battery_config,
        poll_interval=driver_section.getfloat("poll_interval", 5.0),
        details_poll_interval=driver_section.getfloat(
            "details_poll_interval", 60.0
        ),
        failure_threshold=driver_section.getint("failure_threshold", 3),
        device_instance=driver_section.getint("device_instance", 288),
        service_name=driver_section.get(
            "service_name",
            "com.victronenergy.battery.pylontechmonitor_rs232",
        ).strip(),
        log_level=driver_section.get("log_level", "INFO").strip().upper(),
        poll_timeout=driver_section.getfloat("poll_timeout", 120.0),
    )

    if not config.serial.port:
        raise ValueError("serial.port must not be empty")
    if config.serial.baudrate <= 0:
        raise ValueError("serial.baudrate must be positive")
    if config.serial.timeout <= 0:
        raise ValueError("serial.timeout must be positive")
    if config.serial.command_delay < 0:
        raise ValueError("serial.command_delay cannot be negative")
    if config.battery.expected_modules < 0:
        raise ValueError("battery.expected_modules cannot be negative")
    if config.battery.max_modules < 1:
        raise ValueError("battery.max_modules must be at least 1")
    if config.battery.max_cells_per_module < 1:
        raise ValueError("battery.max_cells_per_module must be at least 1")
    if config.battery.expected_modules > config.battery.max_modules:
        raise ValueError("battery.expected_modules exceeds battery.max_modules")
    if config.battery.module_capacity_ah < 0:
        raise ValueError("battery.module_capacity_ah cannot be negative")
    if config.poll_interval <= 0:
        raise ValueError("driver.poll_interval must be positive")
    if config.details_poll_interval < 0:
        raise ValueError("driver.details_poll_interval cannot be negative")
    if config.failure_threshold < 1:
        raise ValueError("driver.failure_threshold must be at least 1")
    if config.poll_timeout <= 0:
        raise ValueError("driver.poll_timeout must be positive")
    if config.device_instance < 0:
        raise ValueError("driver.device_instance cannot be negative")
    if not SAFE_SERVICE_NAME_RE.match(config.service_name):
        raise ValueError(
            "driver.service_name must use the isolated "
            "isolated pylontechmonitor namespace"
        )

    return config
