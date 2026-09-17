#!/bin/sh
set -eu

SYSTEM_SERVICE="com.victronenergy.system"
CONFIG_FILE="/data/apps/dbus-pylontech-console/config.ini"
DEVICE_SERVICE_BASE=$(sed -n 's/^[[:space:]]*service_name[[:space:]]*=[[:space:]]*\([^[:space:]]*\)[[:space:]]*$/\1/p' "$CONFIG_FILE" | head -n 1)
DEVICE_SERVICE="${DEVICE_SERVICE_BASE}_1"

case "$DEVICE_SERVICE_BASE" in
    com.victronenergy.pylontechmonitor.*|com.victronenergy.unsupported.pylontechmonitor_*|com.victronenergy.telemetry.pylontechmonitor_*|com.victronenergy.dcload.pylontechmonitor_*) ;;
    *)
        echo "FAIL: config.ini does not contain a safe dcload service name." >&2
        exit 1
        ;;
esac

active=$(dbus -y "$SYSTEM_SERVICE" /ActiveBatteryService GetValue)
battery=$(dbus -y "$SYSTEM_SERVICE" /Dc/Battery/BatteryService GetValue)
available=$(dbus -y "$SYSTEM_SERVICE" /AvailableBatteryServices GetValue)

if printf '%s\n%s\n%s\n' "$active" "$battery" "$available" | grep -q 'pylontechmonitor'; then
    echo "FAIL: the Pylontech namespace appeared in the system battery selection." >&2
    exit 1
fi

dbus -y "$DEVICE_SERVICE" /Connected GetValue >/dev/null
soc=$(dbus -y "$DEVICE_SERVICE" /Soc GetValue)
voltage=$(dbus -y "$DEVICE_SERVICE" /Dc/0/Voltage GetValue)

echo "PASS: the Pylontech dcload service is available but is not a system battery source."
echo "ActiveBatteryService: $active"
echo "BatteryService: $battery"
echo "Pylontech SOC: $soc"
echo "Pylontech voltage: $voltage"
