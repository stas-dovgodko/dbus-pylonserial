#!/bin/sh
set -eu

APP_NAME="dbus-pylontech-console"
APP_DIR="/data/apps/$APP_NAME"
SERVICE_LINK="/service/$APP_NAME"
SERIAL_STARTER_CONF="/data/conf/serial-starter.d/dbus-pylonserial.conf"
PANEL_WEB_ROOT="/var/www/venus/gui-v2/pylontech-panel"
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SERIAL_STARTER_DEVICE=""

usage() {
    cat <<'EOF'
Usage:
  ./install.sh
  ./install.sh --serial-starter /dev/ttyUSB0

Without options, install a disabled standalone service for manual testing.
With --serial-starter, register this driver for the selected USB serial adapter.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --serial-starter)
            if [ "$#" -lt 2 ]; then
                echo "--serial-starter requires a serial device path." >&2
                exit 2
            fi
            SERIAL_STARTER_DEVICE=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root." >&2
    exit 1
fi

add_rc_hook() {
    hook=$1
    if ! grep -Fqx "$hook" "$RC_LOCAL"; then
        if grep -Fqx 'exit 0' "$RC_LOCAL"; then
            sed -i "/^exit 0$/i\\$hook" "$RC_LOCAL"
        else
            printf '%s\n' "$hook" >> "$RC_LOCAL"
        fi
    fi
}

remove_rc_hook() {
    hook=$1
    temporary="$RC_LOCAL.tmp.$$"
    grep -Fvx "$hook" "$RC_LOCAL" > "$temporary" || true
    mv "$temporary" "$RC_LOCAL"
}

run_tty_helper() {
    helper=$1
    if command -v timeout >/dev/null 2>&1; then
        timeout 15 "$helper" "$DEVICE_NAME"
        return $?
    fi

    # BusyBox images without timeout still get a bounded wait.
    "$helper" "$DEVICE_NAME" &
    helper_pid=$!
    elapsed=0
    while kill -0 "$helper_pid" 2>/dev/null; do
        if [ "$elapsed" -ge 15 ]; then
            kill "$helper_pid" 2>/dev/null || true
            wait "$helper_pid" 2>/dev/null || true
            return 124
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    wait "$helper_pid"
}

remove_runtime_pylon_service() {
    service="/service/dbus-pylonserial.$DEVICE_NAME"
    [ -e "$service" ] || return 0
    svc -d "$service" 2>/dev/null || true
    runtime_dir=$(readlink -f "$service" 2>/dev/null || true)
    # serial-starter keeps generated services on the writable runtime tree.
    # Remove only this exact generated service so the refreshed template is
    # copied and TTY substitution is applied on the next discovery.
    case "$runtime_dir" in
        /run/*|/var/volatile/services/*)
            rm -rf "$runtime_dir"
            rm -f "$service"
            ;;
    esac
}

read_udev_property() {
    property=$1
    printf '%s\n' "$UDEV_PROPERTIES" | sed -n "s/^$property=//p" | head -n 1
}

validate_udev_value() {
    value=$1
    label=$2
    case "$value" in
        ''|*[!A-Za-z0-9._:+@/-]*)
            echo "Unsafe or unsupported $label value: $value" >&2
            exit 1
            ;;
    esac
}

mkdir -p "$APP_DIR"
# Remove artifacts from the retired GUI v2 plugin before refreshing the app.
rm -rf "$APP_DIR/pylontech_dbus" "$APP_DIR/serial-starter" \
    "$APP_DIR/gui-v2-source" "$APP_DIR/gui-v2"
if [ -L "/data/apps/enabled/$APP_NAME" ] \
    && [ "$(readlink -f "/data/apps/enabled/$APP_NAME")" = "$(readlink -f "$APP_DIR")" ]; then
    rm -f "/data/apps/enabled/$APP_NAME"
fi
cp -R "$SOURCE_DIR/pylontech_dbus" "$APP_DIR/"
cp -R "$SOURCE_DIR/serial-starter" "$APP_DIR/"
cp "$SOURCE_DIR/main.py" "$APP_DIR/main.py"
cp "$SOURCE_DIR/probe.py" "$APP_DIR/probe.py"
cp "$SOURCE_DIR/verify-isolation.sh" "$APP_DIR/verify-isolation.sh"
cp "$SOURCE_DIR/restore-serial-starter.sh" "$APP_DIR/restore-serial-starter.sh"
cp "$SOURCE_DIR/uninstall.sh" "$APP_DIR/uninstall.sh"
mkdir -p "$APP_DIR/service"
cp "$SOURCE_DIR/service/run" "$APP_DIR/service/run"
chmod 755 "$APP_DIR/main.py" "$APP_DIR/probe.py" \
    "$APP_DIR/verify-isolation.sh" "$APP_DIR/restore-serial-starter.sh" \
    "$APP_DIR/uninstall.sh" \
    "$APP_DIR/service/run" "$APP_DIR/serial-starter/service/run" \
    "$APP_DIR/serial-starter/service/log/run"

if [ ! -f "$APP_DIR/config.ini" ]; then
    cp "$SOURCE_DIR/config.ini.example" "$APP_DIR/config.ini"
    echo "Created $APP_DIR/config.ini. Review it before relying on the service."
fi

if grep -Eq '^[[:space:]]*service_name[[:space:]]*=[[:space:]]*com\.victronenergy\.(pylontechmonitor\.|unsupported\.pylontechmonitor_|telemetry\.pylontechmonitor_)' "$APP_DIR/config.ini"; then
    sed -i -E 's#^[[:space:]]*service_name[[:space:]]*=.*com\.victronenergy\.(pylontechmonitor\.|unsupported\.pylontechmonitor_|telemetry\.pylontechmonitor_)([A-Za-z0-9_]+)[[:space:]]*$#service_name = com.victronenergy.dcload.pylontechmonitor_\2#' "$APP_DIR/config.ini"
    echo "Migrated the service to the non-battery dcload Device List namespace."
fi

if [ -d "/var/www/venus/gui-v2" ] \
    && mkdir -p "$PANEL_WEB_ROOT" 2>/dev/null \
    && cp -R "$SOURCE_DIR/panel/." "$PANEL_WEB_ROOT/"; then
    touch "$PANEL_WEB_ROOT/.pylontech-panel"
    echo "Installed standalone panel at /gui-v2/pylontech-panel/."
else
    echo "Existing GUI web root is unavailable; standalone panel was not installed." >&2
fi

RC_LOCAL="/data/rc.local"
DIRECT_HOOK="ln -sfn $APP_DIR/service $SERVICE_LINK"
SERIAL_STARTER_HOOK="sh $APP_DIR/restore-serial-starter.sh"
if [ ! -f "$RC_LOCAL" ]; then
    printf '%s\n' '#!/bin/sh' > "$RC_LOCAL"
fi

if [ -n "$SERIAL_STARTER_DEVICE" ]; then
    if [ ! -e "$SERIAL_STARTER_DEVICE" ]; then
        echo "Serial device not found: $SERIAL_STARTER_DEVICE" >&2
        exit 1
    fi
    RESOLVED_DEVICE=$(readlink -f "$SERIAL_STARTER_DEVICE")
    case "$RESOLVED_DEVICE" in
        /dev/tty*) ;;
        *)
            echo "Not a serial TTY device: $SERIAL_STARTER_DEVICE" >&2
            exit 1
            ;;
    esac
    DEVICE_NAME=$(basename "$RESOLVED_DEVICE")
    if ! command -v udevadm >/dev/null 2>&1; then
        echo "udevadm is required for serial-starter installation." >&2
        exit 1
    fi
    if [ -e "$SERVICE_LINK" ] && [ ! -L "$SERVICE_LINK" ]; then
        echo "$SERVICE_LINK exists and is not a symlink; refusing to replace it." >&2
        exit 1
    fi

    UDEV_PROPERTIES=$(udevadm info --query=property --name="$SERIAL_STARTER_DEVICE")
    SERIAL_SHORT=$(read_udev_property ID_SERIAL_SHORT)
    ID_PATH_VALUE=$(read_udev_property ID_PATH)

    if [ -n "$SERIAL_SHORT" ]; then
        validate_udev_value "$SERIAL_SHORT" "ID_SERIAL_SHORT"
        RULE_MATCH="ENV{ID_SERIAL_SHORT}==\"$SERIAL_SHORT\""
        MATCH_DESCRIPTION="USB serial number $SERIAL_SHORT"
    elif [ -n "$ID_PATH_VALUE" ]; then
        validate_udev_value "$ID_PATH_VALUE" "ID_PATH"
        RULE_MATCH="ENV{ID_PATH}==\"$ID_PATH_VALUE\""
        MATCH_DESCRIPTION="physical USB path $ID_PATH_VALUE"
    else
        echo "The adapter has neither ID_SERIAL_SHORT nor ID_PATH." >&2
        echo "Refusing to create a broad USB model rule." >&2
        exit 1
    fi

    mkdir -p "$APP_DIR/udev" /data/conf/serial-starter.d
    printf '%s\n' \
        "ACTION==\"add\", SUBSYSTEM==\"tty\", ENV{ID_BUS}==\"usb\", $RULE_MATCH, ENV{VE_SERVICE}=\"pylonserial\"" \
        > "$APP_DIR/udev/zz-dbus-pylonserial.rules"
    printf '%s\n' 'service pylonserial dbus-pylonserial' > "$SERIAL_STARTER_CONF"

    if [ -L "$SERVICE_LINK" ]; then
        if [ "$(readlink -f "$SERVICE_LINK")" = "$(readlink -f "$APP_DIR/service")" ]; then
            svc -d "$SERVICE_LINK" 2>/dev/null || true
            rm -f "$SERVICE_LINK"
        fi
    fi

    remove_rc_hook "$DIRECT_HOOK"
    add_rc_hook "$SERIAL_STARTER_HOOK"
    chmod 755 "$RC_LOCAL"
    "$APP_DIR/restore-serial-starter.sh"
    if [ -x /opt/victronenergy/serial-starter/stop-tty.sh ]; then
        # Venus OS releases differ here; the helper universally accepts the tty name.
        if ! run_tty_helper /opt/victronenergy/serial-starter/stop-tty.sh; then
            echo "Warning: stop-tty.sh did not finish; continuing with serial-starter reload." >&2
        fi
    fi
    # A previous probe (for example dbus-cgwacs) can remain supervised for this
    # TTY when udev classification changes. Stop only services attached to the
    # selected device so the Pylontech service can acquire the port.
    for stale_service in /service/*."$DEVICE_NAME"; do
        [ -e "$stale_service" ] || continue
        case "$stale_service" in
            "/service/dbus-pylonserial.$DEVICE_NAME") continue ;;
        esac
        svc -d "$stale_service" 2>/dev/null || true
    done
    remove_runtime_pylon_service
    rm -f "/data/var/lib/serial-starter/$DEVICE_NAME"
    if [ -d /service/serial-starter ]; then
        svc -t /service/serial-starter
        sleep 2
    fi
    # Use exactly one activation path. Calling start-tty.sh and then triggering
    # udev for the same TTY can leave multiple supervise processes behind.
    if [ -x /opt/victronenergy/serial-starter/start-tty.sh ]; then
        if ! run_tty_helper /opt/victronenergy/serial-starter/start-tty.sh; then
            echo "Warning: start-tty.sh did not finish; service activation may need a reconnect." >&2
        fi
    elif udevadm trigger --help 2>&1 | grep -q -- '--sysname-match'; then
        udevadm trigger --action=add --sysname-match="$DEVICE_NAME"
    else
        udevadm trigger --action=add --subsystem-match=tty
    fi

    echo "Installed serial-starter integration for $MATCH_DESCRIPTION"
    echo "Edit $APP_DIR/config.ini, then check /service/dbus-pylonserial.$DEVICE_NAME."
    echo "Reconnect the adapter or reboot if the service does not appear."
else
    if [ -f "$SERIAL_STARTER_CONF" ]; then
        echo "Serial-starter integration is already installed." >&2
        echo "Use --serial-starter with the intended device, or uninstall it first." >&2
        exit 1
    fi
    if [ -e "$SERVICE_LINK" ] && [ ! -L "$SERVICE_LINK" ]; then
        echo "$SERVICE_LINK exists and is not a symlink; refusing to replace it." >&2
        exit 1
    fi

    touch "$APP_DIR/service/down"
    ln -sfn "$APP_DIR/service" "$SERVICE_LINK"
    add_rc_hook "$DIRECT_HOOK"
    chmod 755 "$RC_LOCAL"

    echo "Installed standalone service to $APP_DIR"
    echo "The service is down until configuration is reviewed."
    echo "Edit $APP_DIR/config.ini, then run: rm $APP_DIR/service/down && svc -u $SERVICE_LINK"
fi
