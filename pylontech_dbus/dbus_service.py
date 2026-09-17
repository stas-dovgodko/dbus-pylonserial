"""Read-only Victron D-Bus services for Pylontech telemetry."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import replace
from typing import Dict, Optional

from . import __version__
from .config import DriverConfig
from .models import BankReading, ModuleReading


STATISTIC_COUNTER_PATHS = {
    "data items": "DataItems",
    "hisdata items": "HistoryItems",
    "charge cnt": "ChargeCount",
    "discharge cnt": "DischargeCount",
    "charge times": "ChargeTimes",
    "status cnt": "StatusCount",
    "idle times": "IdleTimes",
    "coc times": "CocTimes",
    "coc2 times": "Coc2Times",
    "doc times": "DocTimes",
    "doc2 times": "Doc2Times",
    "coca times": "CocaTimes",
    "doca times": "DocaTimes",
    "sc times": "ShortCircuitTimes",
    "bat ov times": "BatteryOverVoltageTimes",
    "bat hv times": "HighVoltageCount",
    "bat lv times": "LowVoltageCount",
    "bat uv times": "BatteryUnderVoltageTimes",
    "bat slp times": "BatterySleepTimes",
    "pwr ov times": "PowerOverVoltageTimes",
    "pwr hv times": "PowerHighVoltageTimes",
    "pwr lv times": "PowerLowVoltageTimes",
    "pwr uv times": "PowerUnderVoltageTimes",
    "pwr slp times": "PowerSleepTimes",
    "cot times": "ChargeOverTemperatureTimes",
    "cut times": "ChargeUnderTemperatureTimes",
    "dot times": "DischargeOverTemperatureTimes",
    "dut times": "DischargeUnderTemperatureTimes",
    "cht times": "ChargeHighTemperatureTimes",
    "clt times": "ChargeLowTemperatureTimes",
    "dht times": "DischargeHighTemperatureTimes",
    "dlt times": "DischargeLowTemperatureTimes",
    "shut times": "ShutdownCount",
    "reset times": "ResetCount",
    "rv times": "ReverseVoltageTimes",
    "input ov times": "InputOverVoltageTimes",
    "soh times": "SohTimes",
    "bmicerr times": "BmicErrorCount",
    "cycle times": "Cycles",
    "soh": "Soh",
    "pwr percent": "Soc",
    "pwr coulomb": "PowerCoulombRaw",
    "dsg cap": "DischargeCapacityRaw",
    "ht@0 5c cnt": "HighTemperatureHalfCCount",
    "lt@0 5c cnt": "LowTemperatureHalfCCount",
    "ht cnt": "HighTemperatureCount",
    "lt cnt": "LowTemperatureCount",
    "lv cnt": "LowVoltageCountRaw",
    "lifewarn times": "LifeWarningCount",
    "lifealarm times": "LifeAlarmCount",
}


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
        if bus is None:
            # Venus services must publish on the system bus. velib_python
            # otherwise prefers SessionBus when DBUS_SESSION_BUS_ADDRESS is set.
            try:
                import dbus
            except ImportError:
                pass
            else:
                try:
                    bus = dbus.SystemBus()
                except Exception:
                    # Offline test environments may not have a running system bus.
                    pass
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
        self._add(
            "/ProductId", 0xF0A1, lambda _path, value: "0x{:04x}".format(value)
        )
        self._add("/ProductName", self.config.battery.custom_name)
        self._add("/FirmwareVersion", __version__)
        self._add("/Connected", 0)
        self._add("/CustomName", self.config.battery.custom_name)
        self._add("/Serial", "console:{}".format(serial_port))
        self._add("/Manufacturer", "Pylontech")
        self._add("/Reason", "Waiting for Pylontech data")

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
        self._add("/System/Soh", None, _format_value("%", 1))
        self._add("/System/MinCellVoltage", None, _format_value("V", 3))
        self._add("/System/MaxCellVoltage", None, _format_value("V", 3))
        self._add("/System/CellVoltageDiff", None, _format_value("V", 3))

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
            self._add(base + "/VoltageState", None)
            self._add(base + "/CurrentState", None)
            self._add(base + "/TemperatureState", None)
            self._add(base + "/BatteryVoltageState", None)
            self._add(base + "/BatteryTemperatureState", None)
            self._add(base + "/MosTemperatureState", None)
            self._add(base + "/SystemAlarmState", None)
            self._add(base + "/Timestamp", None)
            self._add(base + "/Manufacturer", None)
            self._add(base + "/Serial", None)
            self._add(base + "/Model", None)
            self._add(base + "/FirmwareVersion", None)
            self._add(base + "/SoftwareVersion", None)
            self._add(base + "/BootVersion", None)
            self._add(base + "/CommunicationVersion", None)
            self._add(base + "/HardwareVersion", None)
            self._add(base + "/ReleaseDate", None)
            self._add(base + "/Specification", None)
            self._add(base + "/EponPortRate", None)
            self._add(base + "/ConsolePortRate", None)
            self._add(
                base + "/MaxChargeCurrent", None, _format_value("A", 1)
            )
            self._add(
                base + "/MaxDischargeCurrent", None, _format_value("A", 1)
            )
            self._add(base + "/Cycles", None)
            self._add(base + "/Soh", None, _format_value("%", 1))
            self._add(base + "/RemainingCapacity", None, _format_value("Ah", 2))
            self._add(base + "/CellCount", None)
            self._add(base + "/MinCellVoltage", None, _format_value("V", 3))
            self._add(base + "/MinCellId", None)
            self._add(base + "/MaxCellVoltage", None, _format_value("V", 3))
            self._add(base + "/MaxCellId", None)
            self._add(base + "/CellVoltageDiff", None, _format_value("V", 3))
            self._add(base + "/MinTemperature", None, _format_value("C", 1))
            self._add(base + "/MinTemperatureSensor", None)
            self._add(base + "/MaxTemperature", None, _format_value("C", 1))
            self._add(base + "/MaxTemperatureSensor", None)
            self._add(base + "/MosTemperature", None, _format_value("C", 1))
            for statistic_path in sorted(set(STATISTIC_COUNTER_PATHS.values())):
                formatter = None
                if statistic_path in {"Soc", "Soh"}:
                    formatter = _format_value("%", 1)
                self._add(
                    base + "/Statistics/" + statistic_path,
                    None,
                    formatter,
                )
            for cell in range(1, self.config.battery.max_cells_per_module + 1):
                cell_base = base + "/Cells/{}".format(cell)
                self._add(cell_base + "/Voltage", None, _format_value("V", 3))
                self._add(cell_base + "/Current", None, _format_value("A", 3))
                self._add(cell_base + "/Temperature", None, _format_value("C", 1))
                self._add(cell_base + "/Soc", None, _format_value("%", 1))
                self._add(
                    cell_base + "/RemainingCapacity",
                    None,
                    _format_value("Ah", 2),
                )
                self._add(cell_base + "/Balancing", None)
                self._add(cell_base + "/State", None)
                self._add(cell_base + "/VoltageState", None)
                self._add(cell_base + "/CurrentState", None)
                self._add(cell_base + "/TemperatureState", None)

    def _set(self, path: str, value) -> None:
        self._service[path] = value

    def set_identity(self, product_name: str, custom_name: str) -> None:
        """Update the visible product and custom names after module details arrive."""

        self._set("/ProductName", product_name)
        self._set("/CustomName", custom_name)

    def _clear_module(self, number: int) -> None:
        base = "/Modules/{}".format(number)
        self._set(base + "/Online", 0)
        for field in (
            "Soc",
            "Voltage",
            "Current",
            "Temperature",
            "State",
            "VoltageState",
            "CurrentState",
            "TemperatureState",
            "BatteryVoltageState",
            "BatteryTemperatureState",
            "MosTemperatureState",
            "SystemAlarmState",
            "Timestamp",
            "Manufacturer",
            "Serial",
            "Model",
            "FirmwareVersion",
            "SoftwareVersion",
            "BootVersion",
            "CommunicationVersion",
            "HardwareVersion",
            "ReleaseDate",
            "Specification",
            "EponPortRate",
            "ConsolePortRate",
            "MaxChargeCurrent",
            "MaxDischargeCurrent",
            "Cycles",
            "Soh",
            "RemainingCapacity",
            "CellCount",
            "MinCellVoltage",
            "MinCellId",
            "MaxCellVoltage",
            "MaxCellId",
            "CellVoltageDiff",
            "MinTemperature",
            "MinTemperatureSensor",
            "MaxTemperature",
            "MaxTemperatureSensor",
            "MosTemperature",
        ):
            self._set(base + "/" + field, None)
        for field in set(STATISTIC_COUNTER_PATHS.values()):
            self._set(base + "/Statistics/" + field, None)
        for cell in range(1, self.config.battery.max_cells_per_module + 1):
            cell_base = base + "/Cells/{}".format(cell)
            for field in (
                "Voltage",
                "Current",
                "Temperature",
                "Soc",
                "RemainingCapacity",
                "Balancing",
                "State",
                "VoltageState",
                "CurrentState",
                "TemperatureState",
            ):
                self._set(cell_base + "/" + field, None)

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
        self._set(base + "/VoltageState", module.voltage_state)
        self._set(base + "/CurrentState", module.current_state)
        self._set(base + "/TemperatureState", module.temperature_state)
        self._set(base + "/BatteryVoltageState", module.battery_voltage_state)
        self._set(
            base + "/BatteryTemperatureState", module.battery_temperature_state
        )
        self._set(base + "/MosTemperatureState", module.mos_temperature_state)
        self._set(base + "/SystemAlarmState", module.system_alarm_state)
        self._set(base + "/Timestamp", module.timestamp)
        self._set(base + "/MinCellVoltage", module.cell_voltage_low)
        self._set(base + "/MinCellId", module.cell_voltage_low_id)
        self._set(base + "/MaxCellVoltage", module.cell_voltage_high)
        self._set(base + "/MaxCellId", module.cell_voltage_high_id)
        if module.cell_voltage_low is not None and module.cell_voltage_high is not None:
            cell_delta = round(
                module.cell_voltage_high - module.cell_voltage_low, 3
            )
        else:
            cell_delta = None
        self._set(base + "/CellVoltageDiff", cell_delta)
        self._set(base + "/MinTemperature", module.temperature_low)
        self._set(base + "/MinTemperatureSensor", module.temperature_low_sensor)
        self._set(base + "/MaxTemperature", module.temperature_high)
        self._set(base + "/MaxTemperatureSensor", module.temperature_high_sensor)
        self._set(base + "/MosTemperature", module.mos_temperature)

        metadata = module.metadata
        self._set(base + "/Manufacturer", metadata.manufacturer if metadata else None)
        self._set(base + "/Serial", metadata.serial_number if metadata else None)
        self._set(base + "/Model", metadata.model if metadata else None)
        self._set(
            base + "/FirmwareVersion",
            metadata.main_firmware_version if metadata else None,
        )
        self._set(
            base + "/SoftwareVersion",
            metadata.software_version if metadata else None,
        )
        self._set(base + "/BootVersion", metadata.boot_version if metadata else None)
        self._set(
            base + "/CommunicationVersion",
            metadata.communication_version if metadata else None,
        )
        self._set(
            base + "/HardwareVersion",
            metadata.board_version if metadata else None,
        )
        self._set(base + "/ReleaseDate", metadata.release_date if metadata else None)
        self._set(
            base + "/Specification", metadata.specification if metadata else None
        )
        self._set(
            base + "/EponPortRate", metadata.epon_port_rate if metadata else None
        )
        self._set(
            base + "/ConsolePortRate",
            metadata.console_port_rate if metadata else None,
        )
        self._set(
            base + "/MaxChargeCurrent",
            metadata.max_charge_current if metadata else None,
        )
        self._set(
            base + "/MaxDischargeCurrent",
            metadata.max_discharge_current if metadata else None,
        )
        self._set(base + "/CellCount", metadata.cell_count if metadata else None)

        statistics = module.statistics
        self._set(base + "/Cycles", statistics.cycles if statistics else None)
        self._set(base + "/Soh", statistics.soh if statistics else None)
        statistic_values = dict(statistics.raw_counters) if statistics else {}
        if statistics:
            fallbacks = {
                "charge cnt": statistics.charge_count,
                "discharge cnt": statistics.discharge_count,
                "bat hv times": statistics.high_voltage_count,
                "bat lv times": statistics.low_voltage_count,
                "reset times": statistics.reset_count,
                "shut times": statistics.shutdown_count,
                "bmicerr times": statistics.bmic_error_count,
                "lifewarn times": statistics.life_warning_count,
                "lifealarm times": statistics.life_alarm_count,
                "cycle times": statistics.cycles,
                "soh": statistics.soh,
                "pwr percent": statistics.soc,
            }
            for key, value in fallbacks.items():
                if value is not None:
                    statistic_values.setdefault(key, value)
        for key, path in STATISTIC_COUNTER_PATHS.items():
            self._set(base + "/Statistics/" + path, statistic_values.get(key))

        cells = {cell.number: cell for cell in module.cells}
        remaining_capacity = None
        if cells:
            remaining_capacity = min(
                cell.remaining_capacity_ah for cell in cells.values()
            )
        self._set(base + "/RemainingCapacity", remaining_capacity)
        for number in range(1, self.config.battery.max_cells_per_module + 1):
            cell_base = base + "/Cells/{}".format(number)
            cell = cells.get(number)
            self._set(cell_base + "/Voltage", cell.voltage if cell else None)
            self._set(cell_base + "/Current", cell.current if cell else None)
            self._set(
                cell_base + "/Temperature", cell.temperature if cell else None
            )
            self._set(cell_base + "/Soc", cell.soc if cell else None)
            self._set(
                cell_base + "/RemainingCapacity",
                cell.remaining_capacity_ah if cell else None,
            )
            self._set(
                cell_base + "/Balancing",
                int(cell.balancing)
                if cell and cell.balancing is not None
                else None,
            )
            self._set(cell_base + "/State", cell.base_state if cell else None)
            self._set(
                cell_base + "/VoltageState", cell.voltage_state if cell else None
            )
            self._set(
                cell_base + "/CurrentState", cell.current_state if cell else None
            )
            self._set(
                cell_base + "/TemperatureState",
                cell.temperature_state if cell else None,
            )

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

            if module.battery_voltage_state and not _is_normal(
                module.battery_voltage_state
            ):
                battery_voltage = module.battery_voltage_state.lower()
                if "low" in battery_voltage or "under" in battery_voltage:
                    alarms["LowVoltage"] = 2
                elif "high" in battery_voltage or "over" in battery_voltage:
                    alarms["HighVoltage"] = 2
                else:
                    alarms["InternalFailure"] = 2

            if module.battery_temperature_state and not _is_normal(
                module.battery_temperature_state
            ):
                battery_temperature = module.battery_temperature_state.lower()
                if "low" in battery_temperature or "under" in battery_temperature:
                    alarms["LowTemperature"] = 2
                elif "high" in battery_temperature or "over" in battery_temperature:
                    alarms["HighTemperature"] = 2
                else:
                    alarms["InternalFailure"] = 2

            if module.mos_temperature_state and not _is_normal(
                module.mos_temperature_state
            ):
                alarms["InternalFailure"] = 2
            if module.system_alarm_state and not _is_normal(
                module.system_alarm_state
            ):
                alarms["InternalFailure"] = 2

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
        self._set("/System/Soh", reading.soh)
        self._set("/System/MinCellVoltage", reading.cell_voltage_low)
        self._set("/System/MaxCellVoltage", reading.cell_voltage_high)
        self._set("/System/CellVoltageDiff", reading.cell_voltage_delta)
        self._set("/InstalledCapacity", installed_capacity)
        self._set("/Capacity", remaining_capacity)
        self._set("/System/NrOfModulesOnline", module_count)
        self._set("/System/NrOfModulesOffline", max(0, expected - module_count))
        self._set(
            "/Reason",
            "SOC {:.1f}% | {:.2f} V | {:.2f} A | {}/{} modules".format(
                reading.soc,
                reading.voltage,
                reading.current,
                module_count,
                expected,
            ),
        )

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
            "/System/Soh",
            "/System/MinCellVoltage",
            "/System/MaxCellVoltage",
            "/System/CellVoltageDiff",
        ):
            self._set(path, None)
        self._set("/Reason", "Pylontech console disconnected")
        for number in range(1, self.config.battery.max_modules + 1):
            self._clear_module(number)


class PylontechModuleServices:
    """Expose each online Pylontech module as an isolated service."""

    def __init__(self, config: DriverConfig) -> None:
        self.config = config
        self._services = {}
        self._buses = {}

    def _service_for(self, module: ModuleReading) -> PylontechDbusService:
        service = self._services.get(module.number)
        if service is not None:
            return service
        module_config = replace(
            self.config,
            service_name="{}_{}".format(
                self.config.service_name, module.number
            ),
            device_instance=self.config.device_instance + module.number - 1,
            battery=replace(
                self.config.battery,
                expected_modules=1,
                max_modules=1,
                custom_name="{} {}".format(
                    self.config.battery.custom_name, module.number
                ),
            ),
        )
        bus = None
        try:
            import dbus

            # Each VeDbusService exports the root object path "/". Use a
            # private connection per module so those handlers do not collide.
            bus = dbus.SystemBus(private=True)
        except Exception:
            pass
        service = PylontechDbusService(module_config, bus=bus)
        self._services[module.number] = service
        if bus is not None:
            self._buses[module.number] = bus
        return service

    def publish(self, reading: BankReading) -> None:
        online = set()
        for module in reading.modules:
            online.add(module.number)
            service = self._service_for(module)
            normalized = replace(module, number=1)
            service.publish(BankReading.from_modules((normalized,)))
            if module.metadata:
                metadata = module.metadata
                identity = [
                    metadata.manufacturer if metadata else None,
                    metadata.model,
                    metadata.serial_number if metadata else None,
                ]
                identity = [str(part).strip() for part in identity if part and str(part).strip()]
                if not identity:
                    identity = [self.config.battery.custom_name]
                if len(identity) < 3:
                    identity.append("module {}".format(module.number))
                display_name = " ".join(identity)
                service.set_identity(display_name, display_name)
        for number, service in self._services.items():
            if number not in online:
                service.disconnect()

    def disconnect(self) -> None:
        for service in self._services.values():
            service.disconnect()
