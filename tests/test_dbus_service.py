import os
import sys
import tempfile
import types
import unittest
from dataclasses import replace

from pylontech_dbus.config import load_config
from pylontech_dbus.dbus_service import (
    PylontechDbusService,
    PylontechModuleServices,
)
from pylontech_dbus.models import (
    BankReading,
    CellReading,
    ModuleMetadata,
    ModuleStatistics,
)
from pylontech_dbus.parser import parse_pwr_response

from tests.test_parser import PWR_RESPONSE


class FakeVeDbusService:
    def __init__(self, name, bus=None, register=None):
        self.name = name
        self.values = {}
        self.registered = False

    def add_path(self, path, value=None, **_arguments):
        self.values[path] = value

    def register(self):
        self.registered = True

    def __setitem__(self, path, value):
        self.values[path] = value

    def __getitem__(self, path):
        return self.values[path]


class DbusServiceTest(unittest.TestCase):
    def setUp(self):
        self.original_vedbus = sys.modules.get("vedbus")
        sys.modules["vedbus"] = types.SimpleNamespace(VeDbusService=FakeVeDbusService)
        content = """[serial]
port=/dev/ttyUSB0
[battery]
expected_modules=4
module_capacity_ah=100
max_modules=4
max_cells_per_module=16
[driver]
poll_interval=5
details_poll_interval=60
failure_threshold=3
device_instance=288
service_name=com.victronenergy.dcload.pylontechmonitor_rs232
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write(content)
            self.path = handle.name

    def tearDown(self):
        os.unlink(self.path)
        if self.original_vedbus is None:
            sys.modules.pop("vedbus", None)
        else:
            sys.modules["vedbus"] = self.original_vedbus

    def test_publishes_monitor_values_and_clears_stale_data(self):
        config = load_config(self.path)
        service = PylontechDbusService(config)
        reading = parse_pwr_response(PWR_RESPONSE, expected_modules=4)
        detailed_module = replace(
            reading.modules[0],
            cell_voltage_low=3.316,
            cell_voltage_low_id=1,
            cell_voltage_high=3.316,
            cell_voltage_high_id=1,
            temperature_low=27.0,
            temperature_low_sensor=10,
            temperature_high=30.0,
            temperature_high_sensor=5,
            metadata=ModuleMetadata(
                address=1,
                manufacturer="Pylon",
                model="US2000C",
                main_firmware_version="B67.5.0",
                serial_number="HPTCR03170C09377",
                specification="48V/50AH",
                cell_count=15,
                max_charge_current=90.0,
                console_port_rate=115200,
            ),
            statistics=ModuleStatistics(
                address=1,
                cycles=666,
                soh=93,
                soc=94,
                raw_counters={
                    "cycle times": 666,
                    "pwr coulomb": 158824440,
                    "lifealarm times": 0,
                },
            ),
            cells=(
                CellReading(
                    number=1,
                    voltage=3.316,
                    current=-2.964,
                    temperature=26.4,
                    soc=96,
                    remaining_capacity_ah=44.628,
                    balancing=True,
                    base_state="Dischg",
                    voltage_state="Normal",
                    current_state="Normal",
                    temperature_state="Normal",
                ),
            ),
        )
        reading = BankReading.from_modules(
            (detailed_module,) + reading.modules[1:]
        )

        service.publish(reading)
        values = service._service.values
        self.assertEqual(1, values["/Connected"])
        self.assertEqual(68.5, values["/Soc"])
        self.assertEqual(-13.08, values["/Dc/0/Current"])
        self.assertEqual(400.0, values["/InstalledCapacity"])
        self.assertEqual(274.0, values["/Capacity"])
        self.assertEqual(93, values["/Soh"])
        self.assertEqual(27.0, values["/System/MinCellTemperature"])
        self.assertEqual(30.0, values["/System/MaxCellTemperature"])
        self.assertEqual("C10", values["/System/MinTemperatureCellId"])
        self.assertEqual("C5", values["/System/MaxTemperatureCellId"])
        self.assertIsNone(values["/System/MOSTemperature"])
        self.assertEqual(1, values["/Balancing"])
        self.assertEqual(1, values["/Modules/4/Online"])
        self.assertEqual(0xF0A1, values["/ProductId"])
        self.assertIn("4/4 modules", values["/Reason"])
        self.assertEqual(666, values["/Modules/1/Cycles"])
        self.assertEqual("HPTCR03170C09377", values["/Modules/1/Serial"])
        self.assertEqual("C1", values["/System/MinVoltageCellId"])
        self.assertEqual("C1", values["/System/MaxVoltageCellId"])
        self.assertEqual(15, values["/System/NrOfCellsPerBattery"])
        self.assertEqual(4, values["/System/NrOfBatteries"])
        self.assertEqual(90.0, values["/Modules/1/MaxChargeCurrent"])
        self.assertEqual(115200, values["/Modules/1/ConsolePortRate"])
        self.assertEqual(
            158824440,
            values["/Modules/1/Statistics/PowerCoulombRaw"],
        )
        self.assertEqual(3.316, values["/Modules/1/Cells/1/Voltage"])
        self.assertEqual(1, values["/Modules/1/Cells/1/Balancing"])
        self.assertFalse(any(path.startswith("/Info/") for path in values))

        service.disconnect()
        self.assertEqual(0, values["/Connected"])
        self.assertEqual(2, values["/Alarms/BmsCable"])
        self.assertIsNone(values["/Dc/0/Voltage"])
        self.assertIsNone(values["/Soh"])
        self.assertIsNone(values["/System/MinCellTemperature"])
        self.assertIsNone(values["/System/MinTemperatureCellId"])
        self.assertIsNone(values["/System/MaxCellTemperature"])
        self.assertIsNone(values["/System/MaxTemperatureCellId"])
        self.assertEqual(4, values["/System/NrOfModulesOffline"])

    def test_exposes_each_module_as_a_separate_service(self):
        config = load_config(self.path)
        services = PylontechModuleServices(config)
        reading = parse_pwr_response(PWR_RESPONSE, expected_modules=4)

        services.publish(reading)

        self.assertEqual({1, 2, 3, 4}, set(services._services))
        first = services._services[1]
        fourth = services._services[4]
        self.assertEqual(
            "com.victronenergy.dcload.pylontechmonitor_rs232_1",
            first.config.service_name,
        )
        self.assertEqual(291, fourth.config.device_instance)
        self.assertEqual(1, first._service.values["/Modules/1/Online"])
        self.assertEqual(1, fourth._service.values["/Modules/1/Online"])

    def test_capacity_aggregates_live_cells_and_passport_specification(self):
        reading = parse_pwr_response(PWR_RESPONSE, expected_modules=4)
        modules = []
        for module in reading.modules:
            modules.append(
                replace(
                    module,
                    metadata=ModuleMetadata(
                        address=module.number,
                        specification="48V/50AH",
                    ),
                    cells=(
                        CellReading(
                            number=1,
                            voltage=3.3,
                            current=-1.0,
                            temperature=25.0,
                            soc=70.0,
                            remaining_capacity_ah=45.0 + module.number,
                            balancing=False,
                            base_state="Dischg",
                            voltage_state="Normal",
                            current_state="Normal",
                            temperature_state="Normal",
                        ),
                    ),
                )
            )

        bank = BankReading.from_modules(modules)

        self.assertEqual(200.0, bank.nominal_capacity_ah)
        self.assertEqual(190.0, bank.remaining_capacity_ah)

    def test_module_identity_uses_manufacturer_model_and_serial(self):
        config = load_config(self.path)
        services = PylontechModuleServices(config)
        reading = parse_pwr_response(PWR_RESPONSE, expected_modules=4)
        module = replace(
            reading.modules[0],
            metadata=ModuleMetadata(
                address=1,
                manufacturer="Pylontech",
                model="US3000C",
                serial_number="SN123456",
            ),
        )

        services.publish(BankReading.from_modules((module,)))

        exported = services._services[1]._service.values
        self.assertEqual("Pylontech US3000C SN123456", exported["/ProductName"])
        self.assertEqual("Pylontech US3000C SN123456", exported["/CustomName"])


if __name__ == "__main__":
    unittest.main()
