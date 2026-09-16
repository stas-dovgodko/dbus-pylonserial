import unittest

from pylontech_dbus.parser import (
    PwrParseError,
    parse_bat_response,
    parse_info_response,
    parse_pwr_response,
    parse_stat_response,
)


PWR_RESPONSE = b"""pwr\r
Power Volt Curr Tempr Base.St Volt.St Curr.St Temp.St Coulomb\r
1 52810 -6100 30000 Dischg Normal Normal Normal 71%\r
2 52810 -2460 30000 Dischg Normal Normal Normal 68%\r
3 52810 -3160 28000 Dischg Normal Normal Normal 65%\r
4 52800 -1360 27000 Dischg Normal Normal Normal 70%\r
Command completed successfully\r
pylon>"""


class PwrParserTest(unittest.TestCase):
    def test_parses_and_aggregates_bank(self):
        bank = parse_pwr_response(PWR_RESPONSE, expected_modules=4)

        self.assertEqual(4, len(bank.modules))
        self.assertEqual(52.81, bank.voltage)
        self.assertEqual(-13.08, bank.current)
        self.assertEqual(68.5, bank.soc)
        self.assertEqual(30.0, bank.temperature)
        self.assertEqual(-690.75, bank.power)

    def test_rejects_partial_bank_when_count_is_configured(self):
        response = PWR_RESPONSE.replace(
            b"4 52800 -1360 27000 Dischg Normal Normal Normal 70%\r\n", b""
        )

        with self.assertRaisesRegex(PwrParseError, "Expected modules"):
            parse_pwr_response(response, expected_modules=4)

    def test_discovers_module_count_when_zero_is_configured(self):
        bank = parse_pwr_response(PWR_RESPONSE, expected_modules=0)
        self.assertEqual([1, 2, 3, 4], [item.number for item in bank.modules])

    def test_rejects_missing_header_column(self):
        response = PWR_RESPONSE.replace(b"Coulomb", b"Capacity")
        with self.assertRaisesRegex(PwrParseError, "Missing required pwr column"):
            parse_pwr_response(response)

    def test_skips_absent_module_but_exact_count_still_fails(self):
        response = PWR_RESPONSE.replace(
            b"4 52800 -1360 27000 Dischg Normal Normal Normal 70%",
            b"4 0 0 0 Absent Normal Normal Normal 0%",
        )
        with self.assertRaisesRegex(PwrParseError, "Expected modules"):
            parse_pwr_response(response, expected_modules=4)

    def test_skips_short_absent_rows_after_online_modules(self):
        response = b"""pwr\r
Power Volt Curr Tempr Tlow Tlow.Id Thigh Thigh.Id Vlow Vlow.Id Vhigh Vhigh.Id Base.St Volt.St Curr.St Temp.St Coulomb Time\r
1 49647 -303 28200 27000 12 27800 0 3309 2 3311 10 Dischg Normal Normal Normal 64% 2026-09-17\r
2 49650 -503 29600 28200 10 28400 5 3309 0 3311 4 Dischg Normal Normal Normal 65% 2026-09-17\r
3 49651 -377 29900 28800 0 28900 5 3309 0 3311 8 Dischg Normal Normal Normal 65% 2026-09-17\r
4 49651 -407 30000 28900 5 29100 10 3308 0 3312 11 Dischg Normal Normal Normal 66% 2026-09-17\r
5 49643 0 29700 28400 10 28700 5 3308 0 3311 5 Idle Normal Normal Normal 69% 2026-09-17\r
6 - - - - - - Absent - - - - - - - -\r
7 - - - - - - Absent - - - - - - - -\r
Command completed successfully\r
pylon>"""

        bank = parse_pwr_response(response, expected_modules=5)

        self.assertEqual([1, 2, 3, 4, 5], [item.number for item in bank.modules])

    def test_parses_extended_pwr_columns(self):
        response = b"""pwr\r
Power Volt Curr Tempr Tlow Tlow.Id Thigh Thigh.Id Vlow Vlow.Id Vhigh Vhigh.Id Base.St Volt.St Curr.St Temp.St Coulomb Time B.V.St B.T.St MosTempr M.T.St SysAlarm.St\r
1 49647 -303 28200 27000 12 27800 0 3309 2 3311 10 Dischg Normal Normal Normal 64% 2026-09-17 05:08:49 Normal Normal 28100 Normal Normal\r
Command completed successfully\r
pylon>"""

        module = parse_pwr_response(response).modules[0]

        self.assertEqual(3.309, module.cell_voltage_low)
        self.assertEqual(10, module.cell_voltage_high_id)
        self.assertEqual("2026-09-17 05:08:49", module.timestamp)
        self.assertEqual(28.1, module.mos_temperature)

    def test_parses_info_stat_and_cell_details(self):
        info = """info 2
@
Device address      : 2
Manufacturer        : Pylon
Device name         : US2000C
Board version       : V10R04
Main Soft version   : B67.5.0
Barcode             : HPTCR03170C09377
Specification       : 48V/50AH
Cell Number         : 15
Max Dischg Curr     : -90000mA
Max Charge Curr     : 90000mA
EPONPort rate       : 1200
Console Port rate   : 115200
Command completed successfully
pylon_debug>"""
        stat = """stat 2
@
Device address           2
Charge Cnt.     :        7
Discharge Cnt.  :     1369
Bat HV Times    :       25
CYCLE Times     :      666
SOH             :       93
Pwr Percent     :       94
Command completed successfully
pylon_debug>"""
        bat = """bat 2
@
Battery Volt Curr Tempr Base State Volt. State Curr. State Temp. State SOC Coulomb BAL
0 3316 -2964 26400 Dischg Normal Normal Normal 96% 44628 mAH N
1 3317 -2964 26600 Dischg Normal Normal Normal 96% 44632 mAH Y
Command completed successfully
pylon_debug>"""

        metadata = parse_info_response(info, 2)
        statistics = parse_stat_response(stat, 2)
        cells = parse_bat_response(bat, 2)

        self.assertEqual("HPTCR03170C09377", metadata.serial_number)
        self.assertEqual(15, metadata.cell_count)
        self.assertEqual(-90.0, metadata.max_discharge_current)
        self.assertEqual(115200, metadata.console_port_rate)
        self.assertEqual(666, statistics.cycles)
        self.assertEqual(93, statistics.soh)
        self.assertEqual(2, cells[1].number)
        self.assertEqual(3.317, cells[1].voltage)
        self.assertTrue(cells[1].balancing)

    def test_preserves_one_based_cell_numbers(self):
        response = """bat 1
Battery Volt Curr Tempr Base State Volt. State Curr. State Temp. State SOC Coulomb BAL
1 3316 -2964 26400 Dischg Normal Normal Normal 96% 44628 mAH N
2 3317 -2964 26600 Dischg Normal Normal Normal 96% 44632 mAH Y
pylon>"""

        cells = parse_bat_response(response, 2)

        self.assertEqual([1, 2], [cell.number for cell in cells])


if __name__ == "__main__":
    unittest.main()
