"""Domain models for Pylontech module and bank readings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


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

    def as_dict(self) -> Dict[str, object]:
        return {
            "number": self.number,
            "voltage": self.voltage,
            "current": self.current,
            "temperature": self.temperature,
            "soc": self.soc,
            "base_state": self.base_state,
            "voltage_state": self.voltage_state,
            "current_state": self.current_state,
            "temperature_state": self.temperature_state,
        }


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

    def as_dict(self) -> Dict[str, object]:
        return {
            "voltage": self.voltage,
            "current": self.current,
            "power": self.power,
            "soc": self.soc,
            "temperature": self.temperature,
            "modules": [item.as_dict() for item in self.modules],
        }
