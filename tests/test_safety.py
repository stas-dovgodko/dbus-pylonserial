import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SafetyInvariantTest(unittest.TestCase):
    def test_probe_has_no_dbus_imports(self):
        imported = set()
        probe_files = (
            ROOT / "probe.py",
            ROOT / "pylontech_dbus" / "__init__.py",
            ROOT / "pylontech_dbus" / "serial_console.py",
            ROOT / "pylontech_dbus" / "port_guard.py",
            ROOT / "pylontech_dbus" / "parser.py",
            ROOT / "pylontech_dbus" / "models.py",
        )
        for probe_file in probe_files:
            tree = ast.parse(probe_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)

        forbidden = {"dbus", "gi", "vedbus"}
        self.assertFalse(
            any(name.split(".")[0] in forbidden for name in imported), imported
        )

    def test_driver_does_not_reference_victron_control_services(self):
        source = (ROOT / "pylontech_dbus" / "dbus_service.py").read_text(
            encoding="utf-8"
        )
        forbidden = (
            "com.victronenergy.battery",
            "com.victronenergy.settings",
            "com.victronenergy.system",
            "com.victronenergy.vebus",
            "set_value_async",
            "VeDbusItemImport",
            "writeable=True",
        )
        for value in forbidden:
            self.assertNotIn(value, source)

    def test_isolation_check_is_read_only(self):
        source = (ROOT / "verify-isolation.sh").read_text(encoding="utf-8")
        self.assertIn("GetValue", source)
        for operation in ("SetValue", "SetDefault", "AddSetting"):
            self.assertNotIn(operation, source)


if __name__ == "__main__":
    unittest.main()
