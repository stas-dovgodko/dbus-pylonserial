#!/bin/sh
set -eu

SYSTEM_SERVICE="com.victronenergy.system"
CONFIG_FILE="/data/apps/dbus-pylontech-console/config.ini"
DEVICE_SERVICE_BASE=$(sed -n 's/^[[:space:]]*service_name[[:space:]]*=[[:space:]]*\([^[:space:]]*\)[[:space:]]*$/\1/p' "$CONFIG_FILE" | head -n 1)
DEVICE_SERVICE="${DEVICE_SERVICE_BASE}_1"

case "$DEVICE_SERVICE_BASE" in
    com.victronenergy.pylontechmonitor.*|com.victronenergy.unsupported.pylontechmonitor_*|com.victronenergy.telemetry.pylontechmonitor_*|com.victronenergy.dcload.pylontechmonitor_*|com.victronenergy.battery.pylontechmonitor_*) ;;
    *)
        echo "FAIL: config.ini does not contain an isolated Pylontech service name." >&2
        exit 1
        ;;
esac

active=$(dbus -y "$SYSTEM_SERVICE" /ActiveBatteryService GetValue)
battery=$(dbus -y "$SYSTEM_SERVICE" /Dc/Battery/BatteryService GetValue)
available=$(dbus -y "$SYSTEM_SERVICE" /AvailableBatteryServices GetValue)

case "$DEVICE_SERVICE_BASE" in
    com.victronenergy.battery.*)
        if printf '%s\n%s\n' "$active" "$battery" | grep -Fq -- "$DEVICE_SERVICE_BASE"; then
            echo "FAIL: the Pylontech battery service is selected as the active system battery." >&2
            exit 1
        fi
        echo "WARN: battery namespace is enabled; keep it out of the active ESS/DVCC selection." >&2
        ;;
    *)
        if printf '%s\n%s\n%s\n' "$active" "$battery" "$available" | grep -q 'pylontechmonitor'; then
            echo "FAIL: the Pylontech namespace appeared in the system battery selection." >&2
            exit 1
        fi
        ;;
esac

dbus -y "$DEVICE_SERVICE" /Connected GetValue >/dev/null
soc=$(dbus -y "$DEVICE_SERVICE" /Soc GetValue)
voltage=$(dbus -y "$DEVICE_SERVICE" /Dc/0/Voltage GetValue)

echo "PASS: the Pylontech service is available and is not selected as the active system battery."
echo "ActiveBatteryService: $active"
echo "BatteryService: $battery"
echo "Pylontech SOC: $soc"
echo "Pylontech voltage: $voltage"
