"""Parser for the text table returned by the Pylontech ``pwr`` command."""

from __future__ import annotations

from typing import Dict, List, Sequence, Union

from .models import BankReading, ModuleReading


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
        if base_state.lower() == "absent":
            continue

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
