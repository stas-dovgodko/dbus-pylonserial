#!/bin/sh
set -eu

APP_DIR="/data/apps/dbus-pylontech-console"
TEMPLATE_SOURCE="$APP_DIR/serial-starter/service"
TEMPLATE_LINK="/opt/victronenergy/service-templates/dbus-pylonserial"
RULE_SOURCE="$APP_DIR/udev/zz-dbus-pylonserial.rules"
RULE_LINK="/etc/udev/rules.d/zz-dbus-pylonserial.rules"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this script as root." >&2
    exit 1
fi

if [ ! -d "$TEMPLATE_SOURCE" ] || [ ! -f "$RULE_SOURCE" ]; then
    echo "Serial-starter installation files are incomplete." >&2
    exit 1
fi

for target in "$TEMPLATE_LINK" "$RULE_LINK"; do
    if [ -e "$target" ] && [ ! -L "$target" ]; then
        echo "$target exists and is not a symlink; refusing to replace it." >&2
        exit 1
    fi
done

PROBE_FILE="/etc/udev/rules.d/.dbus-pylonserial-write-test"
if ! touch "$PROBE_FILE" 2>/dev/null; then
    /opt/victronenergy/swupdate-scripts/remount-rw.sh
    touch "$PROBE_FILE"
fi
rm -f "$PROBE_FILE"

ln -sfn "$TEMPLATE_SOURCE" "$TEMPLATE_LINK"
ln -sfn "$RULE_SOURCE" "$RULE_LINK"

if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules
fi
