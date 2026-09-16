# GUI v2 device integration

The optional GUI v2 plugin adds a read-only Pylontech details page below the
device entry. The D-Bus service remains an `unsupported` device type, so it is
not treated as a battery service by `dbus-systemcalc`, ESS, or DVCC.

The main installer compiles this plugin when the Venus OS GUI v2 plugin
compiler and its Qt tools are available. This is normally available on recent
Venus OS Large images. If the compiler is unavailable, the driver still
appears in Device List as an unsupported device and its `/Reason` field shows
the live bank summary.

The plugin requires GUI v2 1.2.13 or newer. Local GUI loading is supported by
that version. Browser Remote Console support depends on the Venus OS version's
ability to distribute filesystem plugins over MQTT.
