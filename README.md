# dbus-pylontech-console

An isolated read-only Pylontech driver for Victron Venus OS. The driver reads the RS232
console port of the master Pylontech/Pytes battery using the read-only `pwr`
command and publishes the aggregated data as
`com.victronenergy.dcload.pylontechmonitor_rs232`.

## Supported features

- bank voltage calculated as the average module voltage;
- bank current calculated as the sum of all module currents;
- power calculated as voltage multiplied by current;
- state of charge calculated as the average module SOC;
- temperature reported as the highest module temperature;
- online and offline module counts;
- individual module values under `/Modules/<n>/...`;
- per-module model, barcode/serial number, hardware and firmware versions;
- per-module manufacturer, specification, release date, software, bootloader,
  communication version, and reported charge/discharge current limits;
- per-module cycle count, SOH, capacity, and the complete known `stat`
  counter set; counters with undocumented units remain explicitly marked raw;
- individual cell voltage, temperature, SOC, remaining capacity, and
  balancing state, plus the cell status fields, under
  `/Modules/<n>/Cells/<n>/...`;
- minimum and maximum cell voltage, cell-voltage spread, temperature extrema,
  and MOS temperature when supplied by the installed firmware;
- stale value invalidation after repeated communication failures;
- support for `PYTES>`, `PYTES_debug>`, `pylon>`, and `pylon_debug>` prompts;
- a standalone probe for testing serial communication without D-Bus.

## ESS and inverter isolation

The default driver mode is **read-only DC-load telemetry** and uses several
independent safeguards:

- the default service name is restricted to the isolated `dcload` namespace.
  The default service type is `dcload`, which is not a battery source;
- it cannot be configured as `com.victronenergy.battery.*`, so Venus OS does
  not discover it as a main battery monitor;
- it does not publish `/Info/MaxChargeVoltage`, `/Info/MaxChargeCurrent`,
  `/Info/MaxDischargeCurrent`, or any other DVCC limits;
- all exported paths are read-only;
- it does not import or write to `com.victronenergy.settings`,
  `com.victronenergy.system`, `com.victronenergy.vebus`, or the primary battery
  service.

Consequently, the default service is not offered in the Main battery monitor selector
and is not used by `dbus-systemcalc`, ESS, DVCC, Shared Voltage Sense, or Shared
Current Sense. Its values are available only to clients that explicitly read
the service name. It appears in Device List as a DC-load device rather than as
a battery.

An experimental opt-in mode is also accepted for testing the standard battery
page: set `driver.service_name` to
`com.victronenergy.battery.pylontechmonitor_rs232`. The driver still omits
`/Info/MaxChargeVoltage`, `/Info/MaxChargeCurrent`, and
`/Info/MaxDischargeCurrent`, and remains read-only. However, the `battery.`
namespace itself makes the service a battery candidate in Venus OS. Do not
select it as the active battery for ESS/DVCC; the absence of limit paths is not
a guarantee that system software will ignore it.

## Data acquisition scope

The driver uses a strict read-only command allowlist:

- `pwr` every `driver.poll_interval` seconds for live module and bank values;
- `info N` for model, barcode, firmware, hardware, specification, and cell
  count;
- `stat N` for cycle count, SOH, SOC, and lifetime counters;
- `bat N` for individual cells and balancing state.

The detail commands run only every `driver.details_poll_interval` seconds.
Unsupported commands or fields are left empty. Pylontech and Pytes firmware
varies considerably, so the presence of a D-Bus path does not imply that every
model can populate it. The driver deliberately does not issue `config`,
`ctrl`, `prot`, `shut`, firmware-update, calibration, reset, or arbitrary
console commands.

The console protocol exposes more commands than this driver should poll:

- `time` reports the BMS clock, but the same timestamp is already included in
  many `pwr` responses;
- `pwr N` adds per-module event bit fields, protection lists, nominal coulomb
  capacity, and charge/discharge duration on verified firmware. Most numeric
  measurements duplicate `pwr`/`bat`, while event-bit semantics are not
  documented consistently, so this variant is not polled yet;
- `log`, `data`, and `datalist` expose historical/event data and may return
  large or firmware-specific responses, so they are intentionally excluded
  from the live service;
- `soh N` exists on some models, but `stat N` already supplies the supported
  module SOH and several Pytes firmwares do not implement `soh N`;
- `pwrsys` can expose rack-wide capacity, extrema, and recommended limits on
  some firmware, but often requires authenticated debug mode. This project
  never logs in and never publishes inverter-control limits;
- configuration, control, shutdown, reset, calibration, and update commands
  are outside the allowlist even if a particular firmware also uses one of
  them for a read-only display.

The implemented `pwr`, `info N`, `stat N`, and `bat N` set therefore covers
the useful live, identity, lifetime, and per-cell telemetry without changing
console privilege level or battery state. Captures and field names were
cross-checked against the
[Pylontech Console protocol project](https://github.com/Hrabovszki1023/pylontech-console),
[pylontech-rs232-venus](https://github.com/tejno/pylontech-rs232-venus), and
[ioBroker.pylontech](https://github.com/PLCHome/ioBroker.pylontech).

## Configuration

Copy the example configuration:

```sh
cp config.ini.example config.ini
```

Review and update the following settings:

- `serial.port` — usually `/dev/ttyUSB0`; serial-starter overrides this value
  with the TTY selected by Venus OS;
- `serial.command_delay` — minimum spacing between console commands; the
  default 1.2 seconds is intentionally conservative for slave modules;
- `battery.expected_modules` — the actual number of modules; setting it to `0`
  enables automatic discovery but cannot protect against a partial response;
- `battery.module_capacity_ah` — the capacity of one module, or `0` if unknown;
- `battery.max_cells_per_module` — the maximum number of D-Bus cell paths to
  reserve for each module;
- `driver.details_poll_interval` — interval for `info`, `stat`, and `bat`
  queries; use `0` to disable detailed polling;
- `driver.device_instance` — a unique device instance in the Victron system.

## Initial test on a GX device

The standalone `probe.py` script never imports D-Bus modules, never registers a
service, and never publishes data. It only sends the diagnostic `pwr` query and
prints the result. Run it before installing or starting the D-Bus service:

```sh
python3 probe.py --port /dev/ttyUSB0 --expected-modules 4
```

To safely inspect serial numbers, cycles, SOH, and cell data without creating
or accessing any D-Bus service, run:

```sh
python3 probe.py --port /dev/ttyUSB0 --expected-modules 4 --details
```

The detailed probe also handles firmware pagination prompts such as
`[enter]` and `--more--`. If a slow stack still omits detail fields, retry with
`--command-delay 2.0` and a larger `--timeout`.

To capture the original console response for troubleshooting, use:

```sh
python3 probe.py --port /dev/ttyUSB0 --raw
```

The probe and driver both refuse to open a serial device detected as already in
use and request an exclusive serial lock. This prevents accidental concurrent
use with `pytes_serial` or another console reader. The process scan is
best-effort, so stop known users of the same serial device before probing. This
check does not affect a primary Pylontech integration connected through a
separate CAN interface.

The probe should return JSON containing every battery module. Start the D-Bus
service only after the probe succeeds:

```sh
python3 main.py --config config.ini
```

Verify the published values on Venus OS:

```sh
dbus -y com.victronenergy.dcload.pylontechmonitor_rs232_1 /Soc GetValue
dbus -y com.victronenergy.dcload.pylontechmonitor_rs232_1 /Dc/0/Voltage GetValue
dbus -y com.victronenergy.dcload.pylontechmonitor_rs232_1 /Modules/1/Cycles GetValue
dbus -y com.victronenergy.dcload.pylontechmonitor_rs232_1 /Modules/1/Serial GetValue
```

## Device List and GUI v2

The service uses the isolated `dcload` device type so that it appears in
Settings -> Device List without masquerading as a Victron battery. Each online
Pylontech module is exposed as its own read-only service (for example,
`...pylontechmonitor_rs232_1`), with the module's complete parameter tree and
cell paths under `/Modules/1/...`. This keeps the modules as separate Device
List rows without enabling ESS/DVCC battery control.

The installer also enables the bundled GUI v2 plugin. It adds a `Pylontech
battery data` page containing bank values, module pages, cycles, serial
numbers, firmware and hardware identity, SOH, lifetime counters, voltage
spread, temperatures, and detailed cell pages. The bundled plugin
requires GUI v2 1.2.13 or newer. On older Venus OS releases or when a browser
Remote Console cannot load filesystem plugins, the generic device entry still
works; update Venus OS or use the local GUI to obtain the full custom page.
After updating an existing installation, run the installer again so it copies
the plugin bundle and refreshes `/data/apps/enabled/dbus-pylontech-console`.

## Standalone browser panel

The installer can place a standalone telemetry panel into the existing GUI-v2
web root, without starting another HTTP service. When `/var/www/venus/gui-v2`
is available, open `https://<cerbo-address>/gui-v2/pylontech-panel/` in a
browser. The panel reads the existing Venus MQTT-over-WebSocket endpoint at
`/websocket-mqtt` and shows the bank summary, individual Pylontech modules,
cell values, and the complete read-only D-Bus tree. It subscribes only to
`dcload` and `battery` telemetry topics and does not send control commands.

The page requires a Venus OS web server with the MQTT WebSocket endpoint
enabled. For local development or a different host, pass `?host=<venus-ip>`;
older firmware may require `?host=<venus-ip>&port=9001&path=%02%03` for the
direct FlashMQ WebSocket endpoint.

## Production installation with Venus OS serial-starter

Venus OS normally probes unclassified USB serial adapters with several drivers.
This can make `dbus-cgwacs` temporarily open a Pylontech console cable even
when no energy meter is installed. The production installer registers a
dedicated `pylonserial` device class so that only this driver opens the selected
adapter.

Copy the repository to the GX device and run the installer as root, passing the
currently assigned device path:

```sh
chmod +x install.sh restore-serial-starter.sh \
    serial-starter/service/run serial-starter/service/log/run
./install.sh --serial-starter /dev/ttyUSB0
```

The installer determines how to identify the adapter without embedding
device-specific values in this project:

1. `ID_SERIAL_SHORT` is preferred when the adapter provides a unique serial
   number. The adapter can then move between USB sockets.
2. `ID_PATH` is used when the adapter has no unique serial number. In that case,
   the physical USB socket becomes the stable identity.
3. Installation stops if neither property is available. It never creates a
   broad `ID_MODEL` rule that could capture unrelated adapters.

The generated udev rule is stored under
`/data/apps/dbus-pylontech-console/udev`, and the serial-starter registration is
stored in `/data/conf/serial-starter.d/dbus-pylonserial.conf`. The installer
does not modify the global `rs485` or `default` probe lists, so no other serial
adapter receives a Pylontech query.

Review the persistent configuration before reconnecting the cable:

```sh
vi /data/apps/dbus-pylontech-console/config.ini
```

Set `battery.expected_modules` to the number confirmed by `probe.py`. The
installer migrates the previous `com.victronenergy.pylontechmonitor.*` default
to the non-battery `com.victronenergy.dcload.pylontechmonitor_*`
namespace while preserving the suffix. The
installer reloads serial-starter and re-enables only the selected TTY. If the
service does not appear, unplug and reconnect the selected USB adapter, or
reboot the GX device. Check the serial-starter service and its log with:

```sh
svstat /service/dbus-pylonserial.ttyUSB0
tail -F /data/log/dbus-pylonserial.ttyUSB0/current | tai64nlocal
```

The template starts the driver with the TTY supplied by serial-starter. The
read-only D-Bus device is registered immediately and initially reports
`/Connected = 0`; this makes the device visible while the adapter is being
probed. The driver publishes battery values only after receiving and parsing a
valid `pwr` response. If detection fails, it exits so serial-starter can
recover normally. If an established connection repeatedly fails, it marks the
device disconnected and exits so serial-starter can restart device detection.

Files under `/data` survive Venus OS updates. The installer adds an idempotent
`/data/rc.local` hook that restores the service-template and udev-rule symlinks.
The integration should still be verified after a major Venus OS update.

To disable the integration and return the adapter to normal Venus OS probing:

```sh
/data/apps/dbus-pylontech-console/uninstall.sh
```

The uninstaller removes only this project's registration and owned symlinks.
It preserves the application directory and `config.ini`, and refuses to remove
foreign files found at the expected paths. Reconnect the adapter or reboot
afterward.

## Standalone service installation

For development without serial-starter, run:

```sh
./install.sh
```

This creates a disabled standalone service. After reviewing its configuration,
start it explicitly:

```sh
rm /data/apps/dbus-pylontech-console/service/down
svc -u /service/dbus-pylontech-console
```

For subsequent standalone restarts and status checks, use:

```sh
svc -t /service/dbus-pylontech-console
svstat /service/dbus-pylontech-console
```

The default `dcload` namespace is recommended for normal operation. To test
the experimental battery page, change only `driver.service_name` in
`config.ini` to `com.victronenergy.battery.pylontechmonitor_rs232`, restart the
service, and ensure that Venus OS has not selected it as the active battery.

After starting the service, run the read-only isolation check:

```sh
/data/apps/dbus-pylontech-console/verify-isolation.sh
```

The check is intended for the default dcload mode and fails if the Pylontech
namespace appears as the active battery service or in the list of available
battery monitors. It also confirms that the custom Pylontech paths can be read.

## Development and tests

The parser has no D-Bus dependency and can be tested with a regular Python
installation:

```sh
python -m unittest discover -v
```

Full D-Bus integration can be tested only on Venus OS or in a Linux environment
with `dbus`, `PyGObject`, and Victron `velib_python` available.

## License

This project is based on the console parsing approach used by `pytes_serial`,
which is licensed under AGPL-3.0. This code is therefore distributed under
`AGPL-3.0-only`. Source attribution is retained in `NOTICE`, and the license
terms are referenced in `LICENSE`.
