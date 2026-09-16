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


if __name__ == "__main__":
    unittest.main()
