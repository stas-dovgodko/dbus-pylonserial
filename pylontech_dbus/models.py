"""Domain models for Pylontech module and bank readings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Tuple


@dataclass(frozen=True)
class CellReading:
    number: int
    voltage: float
    current: float
    temperature: float
    soc: float
    remaining_capacity_ah: float
    balancing: Optional[bool]
    base_state: str
    voltage_state: str
    current_state: str
    temperature_state: str

    def as_dict(self) -> Dict[str, object]:
        return {
            "number": self.number,
            "voltage": self.voltage,
            "current": self.current,
            "temperature": self.temperature,
            "soc": self.soc,
            "remaining_capacity_ah": self.remaining_capacity_ah,
            "balancing": self.balancing,
            "base_state": self.base_state,
            "voltage_state": self.voltage_state,
            "current_state": self.current_state,
            "temperature_state": self.temperature_state,
        }


@dataclass(frozen=True)
class ModuleMetadata:
    address: int
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    board_version: Optional[str] = None
    main_firmware_version: Optional[str] = None
    software_version: Optional[str] = None
    boot_version: Optional[str] = None
    communication_version: Optional[str] = None
    release_date: Optional[str] = None
    serial_number: Optional[str] = None
    specification: Optional[str] = None
    cell_count: Optional[int] = None
    max_discharge_current: Optional[float] = None
    max_charge_current: Optional[float] = None
    epon_port_rate: Optional[int] = None
    console_port_rate: Optional[int] = None
    raw_values: Mapping[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        result = dict(self.__dict__)
        result["raw_values"] = dict(self.raw_values)
        return result


@dataclass(frozen=True)
class ModuleStatistics:
    address: int
    cycles: Optional[int] = None
    soh: Optional[float] = None
    soc: Optional[float] = None
    charge_count: Optional[int] = None
    discharge_count: Optional[int] = None
    high_voltage_count: Optional[int] = None
    low_voltage_count: Optional[int] = None
    reset_count: Optional[int] = None
    shutdown_count: Optional[int] = None
    bmic_error_count: Optional[int] = None
    life_warning_count: Optional[int] = None
    life_alarm_count: Optional[int] = None
    raw_counters: Mapping[str, int] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        result = dict(self.__dict__)
        result["raw_counters"] = dict(self.raw_counters)
        return result


@dataclass(frozen=True)
class ModuleReading:
    number: int
    voltage: float
    current: float
    temperature: float
    soc: float
    base_state: str
    voltage_state: str
    current_state: str
    temperature_state: str
    temperature_low: Optional[float] = None
    temperature_low_sensor: Optional[int] = None
    temperature_high: Optional[float] = None
    temperature_high_sensor: Optional[int] = None
    cell_voltage_low: Optional[float] = None
    cell_voltage_low_id: Optional[int] = None
    cell_voltage_high: Optional[float] = None
    cell_voltage_high_id: Optional[int] = None
    timestamp: Optional[str] = None
    battery_voltage_state: Optional[str] = None
    battery_temperature_state: Optional[str] = None
    mos_temperature: Optional[float] = None
    mos_temperature_state: Optional[str] = None
    system_alarm_state: Optional[str] = None
    metadata: Optional[ModuleMetadata] = None
    statistics: Optional[ModuleStatistics] = None
    cells: Tuple[CellReading, ...] = ()

    def as_dict(self) -> Dict[str, object]:
        result = {
            "number": self.number,
            "voltage": self.voltage,
            "current": self.current,
            "temperature": self.temperature,
            "soc": self.soc,
            "base_state": self.base_state,
            "voltage_state": self.voltage_state,
            "current_state": self.current_state,
            "temperature_state": self.temperature_state,
            "temperature_low": self.temperature_low,
            "temperature_low_sensor": self.temperature_low_sensor,
            "temperature_high": self.temperature_high,
            "temperature_high_sensor": self.temperature_high_sensor,
            "cell_voltage_low": self.cell_voltage_low,
            "cell_voltage_low_id": self.cell_voltage_low_id,
            "cell_voltage_high": self.cell_voltage_high,
            "cell_voltage_high_id": self.cell_voltage_high_id,
            "timestamp": self.timestamp,
            "battery_voltage_state": self.battery_voltage_state,
            "battery_temperature_state": self.battery_temperature_state,
            "mos_temperature": self.mos_temperature,
            "mos_temperature_state": self.mos_temperature_state,
            "system_alarm_state": self.system_alarm_state,
            "cells": [item.as_dict() for item in self.cells],
        }
        result["metadata"] = self.metadata.as_dict() if self.metadata else None
        result["statistics"] = self.statistics.as_dict() if self.statistics else None
        return result


@dataclass(frozen=True)
class BankReading:
    modules: Tuple[ModuleReading, ...]

    @classmethod
    def from_modules(cls, modules: Iterable[ModuleReading]) -> "BankReading":
        ordered = tuple(sorted(modules, key=lambda item: item.number))
        if not ordered:
            raise ValueError("At least one online battery module is required")
        return cls(modules=ordered)

    @property
    def voltage(self) -> float:
        return round(sum(item.voltage for item in self.modules) / len(self.modules), 2)

    @property
    def current(self) -> float:
        return round(sum(item.current for item in self.modules), 2)

    @property
    def power(self) -> float:
        return round(self.voltage * self.current, 2)

    @property
    def soc(self) -> float:
        return round(sum(item.soc for item in self.modules) / len(self.modules), 1)

    @property
    def temperature(self) -> float:
        # The hottest module is the safest representative bank temperature.
        return max(item.temperature for item in self.modules)

    @property
    def soh(self) -> Optional[float]:
        values = [
            item.statistics.soh
            for item in self.modules
            if item.statistics and item.statistics.soh is not None
        ]
        return round(sum(values) / len(values), 1) if values else None

    @property
    def cell_voltage_low(self) -> Optional[float]:
        values = [
            item.cell_voltage_low
            for item in self.modules
            if item.cell_voltage_low is not None
        ]
        return min(values) if values else None

    @property
    def cell_voltage_high(self) -> Optional[float]:
        values = [
            item.cell_voltage_high
            for item in self.modules
            if item.cell_voltage_high is not None
        ]
        return max(values) if values else None

    @property
    def cell_voltage_delta(self) -> Optional[float]:
        if self.cell_voltage_low is None or self.cell_voltage_high is None:
            return None
        return round(self.cell_voltage_high - self.cell_voltage_low, 3)

    @property
    def cell_voltage_low_id(self) -> Optional[int]:
        candidates = [
            (item.cell_voltage_low, item.cell_voltage_low_id)
            for item in self.modules
            if item.cell_voltage_low is not None and item.cell_voltage_low_id is not None
        ]
        return min(candidates, key=lambda item: item[0])[1] if candidates else None

    @property
    def cell_voltage_high_id(self) -> Optional[int]:
        candidates = [
            (item.cell_voltage_high, item.cell_voltage_high_id)
            for item in self.modules
            if item.cell_voltage_high is not None and item.cell_voltage_high_id is not None
        ]
        return max(candidates, key=lambda item: item[0])[1] if candidates else None

    @property
    def cells_per_battery(self) -> Optional[int]:
        counts = []
        for item in self.modules:
            if item.metadata and item.metadata.cell_count:
                counts.append(item.metadata.cell_count)
            elif item.cells:
                counts.append(len(item.cells))
        if not counts:
            return None
        return max(counts)

    def as_dict(self) -> Dict[str, object]:
        return {
            "voltage": self.voltage,
            "current": self.current,
            "power": self.power,
            "soc": self.soc,
            "soh": self.soh,
            "temperature": self.temperature,
            "cell_voltage_low": self.cell_voltage_low,
            "cell_voltage_low_id": self.cell_voltage_low_id,
            "cell_voltage_high": self.cell_voltage_high,
            "cell_voltage_high_id": self.cell_voltage_high_id,
            "cell_voltage_delta": self.cell_voltage_delta,
            "cells_per_battery": self.cells_per_battery,
            "modules": [item.as_dict() for item in self.modules],
        }
