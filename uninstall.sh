#!/bin/sh
set -eu

APP_DIR="/data/apps/dbus-pylontech-console"
DIRECT_SERVICE_LINK="/service/dbus-pylontech-console"
TEMPLATE_LINK="/opt/victronenergy/service-templates/dbus-pylonserial"
TEMPLATE_SOURCE="$APP_DIR/serial-starter/service"
RULE_LINK="/etc/udev/rules.d/zz-dbus-pylonserial.rules"
RULE_SOURCE="$APP_DIR/udev/zz-dbus-pylonserial.rules"
SERIAL_STARTER_CONF="/data/conf/serial-starter.d/dbus-pylonserial.conf"
PANEL_WEB_ROOT="/var/www/venus/gui-v2/pylontech-panel"
RC_LOCAL="/data/rc.local"
DIRECT_HOOK="ln -sfn $APP_DIR/service $DIRECT_SERVICE_LINK"
SERIAL_STARTER_HOOK="sh $APP_DIR/restore-serial-starter.sh"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this uninstaller as root." >&2
    exit 1
fi

remove_owned_link() {
    link=$1
    expected_source=$2
    if [ -L "$link" ]; then
        actual=$(readlink -f "$link" || true)
        expected=$(readlink -f "$expected_source" || true)
        if [ -n "$expected" ] && [ "$actual" = "$expected" ]; then
            rm -f "$link"
        else
            echo "Leaving foreign symlink untouched: $link" >&2
        fi
    elif [ -e "$link" ]; then
        echo "Leaving non-symlink path untouched: $link" >&2
    fi
}

for service in /service/dbus-pylonserial.*; do
    if [ -e "$service" ] || [ -L "$service" ]; then
        svc -d "$service" 2>/dev/null || true
    fi
done

if [ -L "$DIRECT_SERVICE_LINK" ]; then
    if [ "$(readlink -f "$DIRECT_SERVICE_LINK")" = "$(readlink -f "$APP_DIR/service")" ]; then
        svc -d "$DIRECT_SERVICE_LINK" 2>/dev/null || true
        rm -f "$DIRECT_SERVICE_LINK"
    fi
fi

rm -f "$SERIAL_STARTER_CONF"

if [ -L "$TEMPLATE_LINK" ] || [ -L "$RULE_LINK" ]; then
    PROBE_FILE="/etc/udev/rules.d/.dbus-pylonserial-write-test"
    if ! touch "$PROBE_FILE" 2>/dev/null; then
        /opt/victronenergy/swupdate-scripts/remount-rw.sh
        touch "$PROBE_FILE"
    fi
    rm -f "$PROBE_FILE"
fi

remove_owned_link "$TEMPLATE_LINK" "$TEMPLATE_SOURCE"
remove_owned_link "$RULE_LINK" "$RULE_SOURCE"
if [ -f "$PANEL_WEB_ROOT/.pylontech-panel" ]; then
    rm -rf "$PANEL_WEB_ROOT"
fi

if [ -f "$RC_LOCAL" ]; then
    temporary="$RC_LOCAL.tmp.$$"
    grep -Fvx -e "$DIRECT_HOOK" -e "$SERIAL_STARTER_HOOK" "$RC_LOCAL" \
        > "$temporary" || true
    mv "$temporary" "$RC_LOCAL"
    chmod 755 "$RC_LOCAL"
fi

if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules
fi

echo "Disabled dbus-pylonserial integration."
echo "Application files and config.ini were preserved under $APP_DIR."
echo "Reconnect the USB adapter or reboot to restore normal Venus OS probing."
