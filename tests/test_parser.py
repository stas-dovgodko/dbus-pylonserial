import unittest

from pylontech_dbus.parser import PwrParseError, parse_pwr_response


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


if __name__ == "__main__":
    unittest.main()
