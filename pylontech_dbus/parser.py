"""Parsers for read-only Pylontech console responses."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Dict, List, Mapping, Optional, Sequence, Union

from .models import (
    BankReading,
    CellReading,
    ModuleMetadata,
    ModuleReading,
    ModuleStatistics,
)


class PwrParseError(ValueError):
    """Raised when a console response cannot be trusted as a complete reading."""


REQUIRED_COLUMNS = {
    "number": "Power",
    "voltage": "Volt",
    "current": "Curr",
    "temperature": "Tempr",
    "base_state": "Base.St",
    "voltage_state": "Volt.St",
    "current_state": "Curr.St",
    "temperature_state": "Temp.St",
    "soc": "Coulomb",
}

OPTIONAL_COLUMNS = {
    "temperature_low": "Tlow",
    "temperature_low_sensor": "Tlow.Id",
    "temperature_high": "Thigh",
    "temperature_high_sensor": "Thigh.Id",
    "cell_voltage_low": "Vlow",
    "cell_voltage_low_id": "Vlow.Id",
    "cell_voltage_high": "Vhigh",
    "cell_voltage_high_id": "Vhigh.Id",
    "timestamp": "Time",
    "battery_voltage_state": "B.V.St",
    "battery_temperature_state": "B.T.St",
    "mos_temperature": "MosTempr",
    "mos_temperature_state": "M.T.St",
    "system_alarm_state": "SysAlarm.St",
}


def _decode(response: Union[bytes, str]) -> str:
    if isinstance(response, bytes):
        return response.decode("latin-1", errors="replace")
    return response


def _column_indexes(header: Sequence[str]) -> Dict[str, int]:
    indexes = {}
    for field, column in REQUIRED_COLUMNS.items():
        try:
            indexes[field] = header.index(column)
        except ValueError as exc:
            raise PwrParseError("Missing required pwr column: {}".format(column)) from exc
    return indexes


def _parse_scaled_integer(value: str, scale: float, field: str) -> float:
    try:
        return round(int(value) / scale, 3)
    except ValueError as exc:
        raise PwrParseError("Invalid {} value: {!r}".format(field, value)) from exc


def _optional_value(
    values: Sequence[str], header: Sequence[str], indexes: Mapping[str, int], field: str
) -> Optional[str]:
    index = indexes.get(field)
    if index is None:
        return None
    time_index = indexes.get("timestamp")
    if time_index is not None and index > time_index and len(values) > len(header):
        index += 1
    if index >= len(values) or values[index] == "-":
        return None
    if field == "timestamp" and index + 1 < len(values):
        return "{} {}".format(values[index], values[index + 1])
    return values[index]


def _optional_scaled(value: Optional[str], scale: float) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(int(value) / scale, 3)
    except ValueError:
        return None


def _optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_pwr_response(
    response: Union[bytes, str], expected_modules: int = 0
) -> BankReading:
    """Parse a complete ``pwr`` response into an aggregated bank reading.

    ``expected_modules`` set to zero enables discovery. A positive value makes
    missing, duplicate, or out-of-order modules a hard error so partial serial
    responses are never published as a healthy bank.
    """

    lines = [line.strip() for line in _decode(response).replace("\r", "").split("\n")]
    header_position = None
    indexes = None

    for position, line in enumerate(lines):
        columns = line.split()
        if "Power" in columns and "Volt" in columns:
            header_position = position
            indexes = _column_indexes(columns)
            for field, column in OPTIONAL_COLUMNS.items():
                if column in columns:
                    indexes[field] = columns.index(column)
            header = columns
            break

    if header_position is None or indexes is None:
        raise PwrParseError("The pwr table header was not found")

    highest_index = max(indexes.values())
    readings: List[ModuleReading] = []
    seen = set()

    for line in lines[header_position + 1 :]:
        if not line:
            continue
        lower_line = line.lower()
        if lower_line.startswith("command completed"):
            break
        if lower_line in {"pytes>", "pytes_debug>", "pylon>", "pylon_debug>"}:
            break

        values = line.split()
        if not values or not values[0].isdigit():
            continue
        if any(value.lower() == "absent" for value in values[1:]):
            continue
        if len(values) <= highest_index:
            raise PwrParseError("Incomplete pwr row: {!r}".format(line))

        try:
            number = int(values[indexes["number"]])
        except ValueError as exc:
            raise PwrParseError("Invalid module number in row: {!r}".format(line)) from exc

        if number in seen:
            raise PwrParseError("Duplicate module number: {}".format(number))
        seen.add(number)

        base_state = values[indexes["base_state"]]

        try:
            soc = float(values[indexes["soc"]].rstrip("%"))
        except ValueError as exc:
            raise PwrParseError(
                "Invalid state of charge: {!r}".format(values[indexes["soc"]])
            ) from exc

        readings.append(
            ModuleReading(
                number=number,
                voltage=_parse_scaled_integer(
                    values[indexes["voltage"]], 1000.0, "voltage"
                ),
                current=_parse_scaled_integer(
                    values[indexes["current"]], 1000.0, "current"
                ),
                temperature=_parse_scaled_integer(
                    values[indexes["temperature"]], 1000.0, "temperature"
                ),
                soc=soc,
                base_state=base_state,
                voltage_state=values[indexes["voltage_state"]],
                current_state=values[indexes["current_state"]],
                temperature_state=values[indexes["temperature_state"]],
                temperature_low=_optional_scaled(
                    _optional_value(values, header, indexes, "temperature_low"),
                    1000.0,
                ),
                temperature_low_sensor=_optional_int(
                    _optional_value(
                        values, header, indexes, "temperature_low_sensor"
                    )
                ),
                temperature_high=_optional_scaled(
                    _optional_value(values, header, indexes, "temperature_high"),
                    1000.0,
                ),
                temperature_high_sensor=_optional_int(
                    _optional_value(
                        values, header, indexes, "temperature_high_sensor"
                    )
                ),
                cell_voltage_low=_optional_scaled(
                    _optional_value(values, header, indexes, "cell_voltage_low"),
                    1000.0,
                ),
                cell_voltage_low_id=_optional_int(
                    _optional_value(values, header, indexes, "cell_voltage_low_id")
                ),
                cell_voltage_high=_optional_scaled(
                    _optional_value(values, header, indexes, "cell_voltage_high"),
                    1000.0,
                ),
                cell_voltage_high_id=_optional_int(
                    _optional_value(values, header, indexes, "cell_voltage_high_id")
                ),
                timestamp=_optional_value(values, header, indexes, "timestamp"),
                battery_voltage_state=_optional_value(
                    values, header, indexes, "battery_voltage_state"
                ),
                battery_temperature_state=_optional_value(
                    values, header, indexes, "battery_temperature_state"
                ),
                mos_temperature=_optional_scaled(
                    _optional_value(values, header, indexes, "mos_temperature"),
                    1000.0,
                ),
                mos_temperature_state=_optional_value(
                    values, header, indexes, "mos_temperature_state"
                ),
                system_alarm_state=_optional_value(
                    values, header, indexes, "system_alarm_state"
                ),
            )
        )

    if not readings:
        raise PwrParseError("The pwr response contains no online battery modules")

    if expected_modules:
        found = [item.number for item in readings]
        required = list(range(1, expected_modules + 1))
        if found != required:
            raise PwrParseError(
                "Expected modules {}, received {}".format(required, found)
            )

    return BankReading.from_modules(readings)


def _key_values(response: Union[bytes, str]) -> Dict[str, str]:
    values = {}
    for raw_line in _decode(response).replace("\r", "").split("\n"):
        line = raw_line.strip()
        if not line or line in {"@", "$$"} or line.lower().startswith("command "):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
        else:
            match = re.match(r"^(Device address)\s+(-?\d+)\s*$", line, re.I)
            if not match:
                continue
            key, value = match.groups()
        normalized = " ".join(key.lower().replace(".", " ").split())
        values[normalized] = value.strip()
    return values


def _integer(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    match = re.search(r"-?\d+", value)
    return int(match.group(0)) if match else None


def _current_amps(value: Optional[str]) -> Optional[float]:
    parsed = _integer(value)
    return round(parsed / 1000.0, 3) if parsed is not None else None


def _first(values: Mapping[str, str], *keys: str) -> Optional[str]:
    for key in keys:
        if key in values:
            return values[key]
    return None


def _first_counter(counters: Mapping[str, int], *keys: str) -> Optional[int]:
    for key in keys:
        if key in counters:
            return counters[key]
    return None


def parse_info_response(
    response: Union[bytes, str], expected_address: Optional[int] = None
) -> ModuleMetadata:
    values = _key_values(response)
    address = _integer(values.get("device address"))
    if address is None:
        raise PwrParseError("The info response has no device address")
    if expected_address is not None and address != expected_address:
        raise PwrParseError(
            "Expected info for module {}, received {}".format(
                expected_address, address
            )
        )
    return ModuleMetadata(
        address=address,
        manufacturer=_first(values, "manufacturer", "vendor"),
        model=_first(values, "device name", "model", "product name"),
        board_version=values.get("board version") or values.get("board"),
        main_firmware_version=_first(
            values, "main soft version", "main software version", "firmware version"
        ),
        software_version=_first(values, "soft version", "software version"),
        boot_version=_first(values, "boot version", "bootloader version"),
        communication_version=_first(
            values, "comm version", "communication version"
        ),
        release_date=_first(values, "release date", "production date"),
        serial_number=_first(
            values, "barcode", "bar code", "serial number", "serial no"
        ),
        specification=_first(values, "specification", "spec"),
        cell_count=_integer(_first(values, "cell number", "cell count")),
        max_discharge_current=_current_amps(
            _first(
                values,
                "max dischg curr",
                "max discharge curr",
                "max discharge current",
            )
        ),
        max_charge_current=_current_amps(
            _first(values, "max charge curr", "max charge current")
        ),
        epon_port_rate=_integer(_first(values, "eponport rate", "epon port rate")),
        console_port_rate=_integer(values.get("console port rate")),
        raw_values=values,
    )


def parse_stat_response(
    response: Union[bytes, str], expected_address: Optional[int] = None
) -> ModuleStatistics:
    values = _key_values(response)
    counters = {
        key: parsed
        for key, value in values.items()
        if (parsed := _integer(value)) is not None
    }
    address = counters.get("device address")
    if address is None:
        if expected_address is None:
            raise PwrParseError("The stat response has no device address")
        address = expected_address
    if expected_address is not None and address != expected_address:
        raise PwrParseError(
            "Expected statistics for module {}, received {}".format(
                expected_address, address
            )
        )
    return ModuleStatistics(
        address=address,
        cycles=_first_counter(counters, "cycle times", "cycle time", "cycles"),
        soh=counters.get("soh"),
        soc=counters.get("pwr percent"),
        charge_count=counters.get("charge cnt"),
        discharge_count=_first_counter(counters, "discharge cnt", "dsg cnt"),
        high_voltage_count=counters.get("bat hv times"),
        low_voltage_count=counters.get("bat lv times"),
        reset_count=counters.get("reset times"),
        shutdown_count=counters.get("shut times"),
        bmic_error_count=counters.get("bmicerr times"),
        life_warning_count=counters.get("lifewarn times"),
        life_alarm_count=counters.get("lifealarm times"),
        raw_counters=counters,
    )


def parse_bat_response(
    response: Union[bytes, str], expected_cells: int = 0
) -> Sequence[CellReading]:
    cells = []
    pattern = re.compile(
        r"^\s*(\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+"
        r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+"
        r"(\d+(?:\.\d+)?)%\s+(-?\d+)(?:\s+mAH)?(?:\s+([YN]))?\s*$",
        re.I,
    )
    for line in _decode(response).replace("\r", "").split("\n"):
        match = pattern.match(line)
        if not match:
            continue
        (
            raw_number,
            voltage,
            current,
            temperature,
            base_state,
            voltage_state,
            current_state,
            temperature_state,
            soc,
            remaining_capacity,
            balancing,
        ) = match.groups()
        cells.append(
            CellReading(
                number=int(raw_number),
                voltage=round(int(voltage) / 1000.0, 3),
                current=round(int(current) / 1000.0, 3),
                temperature=round(int(temperature) / 1000.0, 3),
                soc=float(soc),
                remaining_capacity_ah=round(int(remaining_capacity) / 1000.0, 3),
                balancing=None if balancing is None else balancing.upper() == "Y",
                base_state=base_state,
                voltage_state=voltage_state,
                current_state=current_state,
                temperature_state=temperature_state,
            )
        )
    if not cells:
        raise PwrParseError("The bat response contains no cell rows")
    if min(cell.number for cell in cells) == 0:
        cells = [replace(cell, number=cell.number + 1) for cell in cells]
    if expected_cells and len(cells) != expected_cells:
        raise PwrParseError(
            "Expected {} cells, received {}".format(expected_cells, len(cells))
        )
    return tuple(cells)
