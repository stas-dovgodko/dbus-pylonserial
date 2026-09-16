"""Isolated Victron D-Bus telemetry service."""

from __future__ import annotations

import os
import platform
import sys
from typing import Dict, Optional

from . import __version__
from .config import DriverConfig
from .models import BankReading, ModuleReading


def _load_vedbus():
    velib_path = os.environ.get(
        "VELIB_PYTHON", "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python"
    )
    if velib_path not in sys.path:
        sys.path.insert(0, velib_path)
    try:
        from vedbus import VeDbusService
    except ImportError as exc:
        raise RuntimeError(
            "Unable to import Victron velib_python from {}".format(velib_path)
        ) from exc
    return VeDbusService


def _format_value(unit: str, decimals: int):
    def formatter(_path, value):
        if value is None:
            return ""
        return ("{:0." + str(decimals) + "f}{}").format(value, unit)

    return formatter


def _is_normal(value: str) -> bool:
    return value.strip().lower() in {"normal", "ok", "none"}


class PylontechDbusService:
    def __init__(self, config: DriverConfig, bus=None) -> None:
        VeDbusService = _load_vedbus()
        self.config = config
        self._service = VeDbusService(config.service_name, bus=bus, register=False)
        self._last_module_count = 0
        self._setup_paths()
        self._service.register()

    def _add(self, path: str, value=None, formatter=None) -> None:
        arguments = {}
        if formatter is not None:
            arguments["gettextcallback"] = formatter
        self._service.add_path(path, value, **arguments)

    def _setup_paths(self) -> None:
        serial_port = self.config.serial.port
        self._add("/Mgmt/ProcessName", "dbus-pylontech-console")
        self._add("/Mgmt/ProcessVersion", "Python {}".format(platform.python_version()))
        self._add("/Mgmt/Connection", "RS232 {}".format(serial_port))
        self._add("/DeviceInstance", self.config.device_instance)
        self._add("/ProductId", 0, lambda _path, value: "0x{:04x}".format(value))
        self._add("/ProductName", "Pylontech Console Battery Monitor")
        self._add("/FirmwareVersion", __version__)
        self._add("/Connected", 0)
        self._add("/CustomName", self.config.battery.custom_name)
        self._add("/Serial", "console:{}".format(serial_port))
        self._add("/Manufacturer", "Pylontech")

        self._add("/Soc", None, _format_value("%", 1))
        self._add("/Dc/0/Voltage", None, _format_value("V", 2))
        self._add("/Dc/0/Current", None, _format_value("A", 2))
        self._add("/Dc/0/Power", None, _format_value("W", 0))
        self._add("/Dc/0/Temperature", None, _format_value("C", 1))
        self._add("/InstalledCapacity", None, _format_value("Ah", 1))
        self._add("/Capacity", None, _format_value("Ah", 1))
        self._add("/System/NrOfModulesOnline", 0)
        self._add(
            "/System/NrOfModulesOffline", self.config.battery.expected_modules
        )
        self._add("/Settings/HasTemperature", 1)

        for path in (
            "/Alarms/HighVoltage",
            "/Alarms/LowVoltage",
            "/Alarms/HighChargeCurrent",
            "/Alarms/HighDischargeCurrent",
            "/Alarms/HighTemperature",
            "/Alarms/LowTemperature",
            "/Alarms/InternalFailure",
            "/Alarms/BmsCable",
        ):
            self._add(path, 0)

        for number in range(1, self.config.battery.max_modules + 1):
            base = "/Modules/{}".format(number)
            self._add(base + "/Online", 0)
            self._add(base + "/Soc", None, _format_value("%", 0))
            self._add(base + "/Voltage", None, _format_value("V", 2))
            self._add(base + "/Current", None, _format_value("A", 2))
            self._add(base + "/Temperature", None, _format_value("C", 1))
            self._add(base + "/State", None)

    def _set(self, path: str, value) -> None:
        self._service[path] = value

    def _clear_module(self, number: int) -> None:
        base = "/Modules/{}".format(number)
        self._set(base + "/Online", 0)
        for field in ("Soc", "Voltage", "Current", "Temperature", "State"):
            self._set(base + "/" + field, None)

    def _publish_module(self, module: ModuleReading) -> None:
        if module.number > self.config.battery.max_modules:
            return
        base = "/Modules/{}".format(module.number)
        self._set(base + "/Online", 1)
        self._set(base + "/Soc", module.soc)
        self._set(base + "/Voltage", module.voltage)
        self._set(base + "/Current", module.current)
        self._set(base + "/Temperature", module.temperature)
        self._set(base + "/State", module.base_state)

    @staticmethod
    def _alarms(reading: BankReading) -> Dict[str, int]:
        alarms = {
            "HighVoltage": 0,
            "LowVoltage": 0,
            "HighChargeCurrent": 0,
            "HighDischargeCurrent": 0,
            "HighTemperature": 0,
            "LowTemperature": 0,
            "InternalFailure": 0,
        }
        for module in reading.modules:
            voltage = module.voltage_state.lower()
            current = module.current_state.lower()
            temperature = module.temperature_state.lower()

            if not _is_normal(module.voltage_state):
                if "low" in voltage or "under" in voltage:
                    alarms["LowVoltage"] = 2
                elif "high" in voltage or "over" in voltage:
                    alarms["HighVoltage"] = 2
                else:
                    alarms["InternalFailure"] = 2

            if not _is_normal(module.current_state):
                if module.current >= 0:
                    alarms["HighChargeCurrent"] = 2
                else:
                    alarms["HighDischargeCurrent"] = 2

            if not _is_normal(module.temperature_state):
                if "low" in temperature or "under" in temperature:
                    alarms["LowTemperature"] = 2
                elif "high" in temperature or "over" in temperature:
                    alarms["HighTemperature"] = 2
                else:
                    alarms["InternalFailure"] = 2

            state = module.base_state.strip().lower()
            if state not in {
                "charge",
                "charging",
                "chg",
                "dischg",
                "discharge",
                "discharging",
                "idle",
                "standby",
            }:
                alarms["InternalFailure"] = 2
        return alarms

    def publish(self, reading: BankReading) -> None:
        module_count = len(reading.modules)
        self._last_module_count = module_count
        expected = self.config.battery.expected_modules or module_count
        capacity_per_module = self.config.battery.module_capacity_ah
        installed_capacity: Optional[float] = None
        remaining_capacity: Optional[float] = None
        if capacity_per_module > 0:
            installed_capacity = round(capacity_per_module * expected, 2)
            remaining_capacity = round(installed_capacity * reading.soc / 100.0, 2)

        self._set("/Connected", 1)
        self._set("/Alarms/BmsCable", 0)
        self._set("/Soc", reading.soc)
        self._set("/Dc/0/Voltage", reading.voltage)
        self._set("/Dc/0/Current", reading.current)
        self._set("/Dc/0/Power", reading.power)
        self._set("/Dc/0/Temperature", reading.temperature)
        self._set("/InstalledCapacity", installed_capacity)
        self._set("/Capacity", remaining_capacity)
        self._set("/System/NrOfModulesOnline", module_count)
        self._set("/System/NrOfModulesOffline", max(0, expected - module_count))

        online_numbers = {item.number for item in reading.modules}
        for number in range(1, self.config.battery.max_modules + 1):
            if number in online_numbers:
                module = next(item for item in reading.modules if item.number == number)
                self._publish_module(module)
            else:
                self._clear_module(number)

        for alarm, value in self._alarms(reading).items():
            self._set("/Alarms/" + alarm, value)

    def disconnect(self) -> None:
        expected = self.config.battery.expected_modules or self._last_module_count
        self._set("/Connected", 0)
        self._set("/Alarms/BmsCable", 2)
        self._set("/System/NrOfModulesOnline", 0)
        self._set("/System/NrOfModulesOffline", expected)
        for path in (
            "/Soc",
            "/Dc/0/Voltage",
            "/Dc/0/Current",
            "/Dc/0/Power",
            "/Dc/0/Temperature",
            "/Capacity",
        ):
            self._set(path, None)
        for number in range(1, self.config.battery.max_modules + 1):
            self._clear_module(number)
