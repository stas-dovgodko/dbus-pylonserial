# GUI v2 device integration

The optional GUI v2 plugin adds a read-only Pylontech details page below the
device entry. The default D-Bus service uses the `battery` device type so the
standard battery page can display it; the driver publishes no ESS/DVCC limit
paths and remains read-only. The isolated `dcload` type is available as an
explicit alternative.

The main installer compiles this plugin when the Venus OS GUI v2 plugin
compiler and its Qt tools are available. This is normally available on recent
Venus OS Large images. If the compiler is unavailable, the driver still
appears in Device List using the configured service type and its `/Reason`
field shows the live bank summary.

The plugin requires GUI v2 1.2.13 or newer. Local GUI loading is supported by
that version. Browser Remote Console support depends on the Venus OS version's
ability to distribute filesystem plugins over MQTT.
