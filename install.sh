#!/bin/sh
set -eu

APP_NAME="dbus-pylontech-console"
APP_DIR="/data/apps/$APP_NAME"
SERVICE_LINK="/service/$APP_NAME"
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
NEW_CONFIG=0

if [ "$(id -u)" -ne 0 ]; then
    echo "Run this installer as root." >&2
    exit 1
fi

mkdir -p "$APP_DIR"
cp -R "$SOURCE_DIR/pylontech_dbus" "$APP_DIR/"
cp "$SOURCE_DIR/main.py" "$APP_DIR/main.py"
cp "$SOURCE_DIR/probe.py" "$APP_DIR/probe.py"
cp "$SOURCE_DIR/verify-isolation.sh" "$APP_DIR/verify-isolation.sh"
mkdir -p "$APP_DIR/service"
cp "$SOURCE_DIR/service/run" "$APP_DIR/service/run"
chmod 755 "$APP_DIR/main.py" "$APP_DIR/probe.py" \
    "$APP_DIR/verify-isolation.sh" "$APP_DIR/service/run"

if [ ! -f "$APP_DIR/config.ini" ]; then
    cp "$SOURCE_DIR/config.ini.example" "$APP_DIR/config.ini"
    touch "$APP_DIR/service/down"
    NEW_CONFIG=1
    echo "Created $APP_DIR/config.ini. Edit it before relying on the service."
fi

if [ -e "$SERVICE_LINK" ] && [ ! -L "$SERVICE_LINK" ]; then
    echo "$SERVICE_LINK exists and is not a symlink; refusing to replace it." >&2
    exit 1
fi
ln -sfn "$APP_DIR/service" "$SERVICE_LINK"

RC_LOCAL="/data/rc.local"
HOOK="ln -sfn $APP_DIR/service $SERVICE_LINK"
if [ ! -f "$RC_LOCAL" ]; then
    printf '%s\n' '#!/bin/sh' > "$RC_LOCAL"
fi
if ! grep -Fqx "$HOOK" "$RC_LOCAL"; then
    if grep -Fqx 'exit 0' "$RC_LOCAL"; then
        sed -i "/^exit 0$/i\\$HOOK" "$RC_LOCAL"
    else
        printf '%s\n' "$HOOK" >> "$RC_LOCAL"
    fi
fi
chmod 755 "$RC_LOCAL"

echo "Installed to $APP_DIR"
if [ "$NEW_CONFIG" -eq 1 ]; then
    echo "The service is down until configuration is reviewed."
    echo "Edit $APP_DIR/config.ini, then run: rm $APP_DIR/service/down && svc -u $SERVICE_LINK"
else
    echo "Restart with: svc -t $SERVICE_LINK"
fi
