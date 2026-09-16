#!/bin/sh
set -eu

SYSTEM_SERVICE="com.victronenergy.system"
TELEMETRY_SERVICE="com.victronenergy.pylontechmonitor.rs232"

active=$(dbus -y "$SYSTEM_SERVICE" /ActiveBatteryService GetValue)
battery=$(dbus -y "$SYSTEM_SERVICE" /Dc/Battery/BatteryService GetValue)
available=$(dbus -y "$SYSTEM_SERVICE" /AvailableBatteryServices GetValue)

if printf '%s\n%s\n%s\n' "$active" "$battery" "$available" | grep -q 'pylontechmonitor'; then
    echo "FAIL: the telemetry namespace appeared in the system battery selection." >&2
    exit 1
fi

dbus -y "$TELEMETRY_SERVICE" /Connected GetValue >/dev/null
soc=$(dbus -y "$TELEMETRY_SERVICE" /Soc GetValue)
voltage=$(dbus -y "$TELEMETRY_SERVICE" /Dc/0/Voltage GetValue)

echo "PASS: the telemetry service is available but is not a system battery source."
echo "ActiveBatteryService: $active"
echo "BatteryService: $battery"
echo "Telemetry SOC: $soc"
echo "Telemetry voltage: $voltage"
