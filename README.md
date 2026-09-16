# dbus-pylontech-console

An isolated telemetry driver for Victron Venus OS. The driver reads the RS232
console port of the master Pylontech/Pytes battery using the read-only `pwr`
command and publishes the aggregated data as
`com.victronenergy.pylontechmonitor.rs232`.

## Supported features

- bank voltage calculated as the average module voltage;
- bank current calculated as the sum of all module currents;
- power calculated as voltage multiplied by current;
- state of charge calculated as the average module SOC;
- temperature reported as the highest module temperature;
- online and offline module counts;
- individual module values under `/Modules/<n>/...`;
- stale value invalidation after repeated communication failures;
- support for `PYTES>`, `PYTES_debug>`, `pylon>`, and `pylon_debug>` prompts;
- a standalone probe for testing serial communication without D-Bus.

## ESS and inverter isolation

The driver is **telemetry-only** and uses several independent safeguards:

- its service name is restricted to the custom
  `com.victronenergy.pylontechmonitor.*` namespace;
- it cannot be configured as `com.victronenergy.battery.*`, so Venus OS does
  not discover it as a main battery monitor;
- it does not publish `/Info/MaxChargeVoltage`, `/Info/MaxChargeCurrent`,
  `/Info/MaxDischargeCurrent`, or any other DVCC limits;
- all exported paths are read-only;
- it does not import or write to `com.victronenergy.settings`,
  `com.victronenergy.system`, `com.victronenergy.vebus`, or the primary battery
  service.

Consequently, the service is not offered in the Main battery monitor selector
and is not used by `dbus-systemcalc`, ESS, DVCC, Shared Voltage Sense, or Shared
Current Sense. Its values are available only to clients that explicitly read
the custom service name. This isolation also means that the telemetry service
will not appear as a regular battery in the standard Venus OS battery UI.

## Configuration

Copy the example configuration:

```sh
cp config.ini.example config.ini
```

Review and update the following settings:

- `serial.port` — usually `/dev/ttyUSB0`;
- `battery.expected_modules` — the actual number of modules; setting it to `0`
  enables automatic discovery but cannot protect against a partial response;
- `battery.module_capacity_ah` — the capacity of one module, or `0` if unknown;
- `driver.device_instance` — a unique device instance in the Victron system.

## Initial test on a GX device

The standalone `probe.py` script never imports D-Bus modules, never registers a
service, and never publishes data. It only sends the diagnostic `pwr` query and
prints the result. Run it before installing or starting the D-Bus service:

```sh
python3 probe.py --port /dev/ttyUSB0 --expected-modules 4
```

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
dbus -y com.victronenergy.pylontechmonitor.rs232 /Soc GetValue
dbus -y com.victronenergy.pylontechmonitor.rs232 /Dc/0/Voltage GetValue
dbus -y com.victronenergy.pylontechmonitor.rs232 /System/NrOfModulesOnline GetValue
```

## Installation under `/data`

Copy the repository to the GX device and run the installer as root:

```sh
chmod +x install.sh service/run
./install.sh
```

The installer copies the driver to `/data/apps/dbus-pylontech-console`, creates
`config.ini`, installs a runit service, and adds an idempotent hook to
`/data/rc.local`. Files under `/data` survive Venus OS updates, but the
modification should still be verified after major updates. On the first
installation, the service remains disabled so that it cannot claim the serial
port before the configuration has been reviewed.

After editing the configuration, start the service for the first time:

```sh
rm /data/apps/dbus-pylontech-console/service/down
svc -u /service/dbus-pylontech-console
```

For subsequent restarts and status checks, use:

```sh
svc -t /service/dbus-pylontech-console
svstat /service/dbus-pylontech-console
```

Do not change the service namespace to `com.victronenergy.battery` and do not
attempt to select this telemetry service as the main battery monitor.

After starting the service, run the read-only isolation check:

```sh
/data/apps/dbus-pylontech-console/verify-isolation.sh
```

The check fails if the custom namespace appears as the active battery service
or in the list of available battery monitors. It also confirms that the custom
telemetry paths can be read.

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
