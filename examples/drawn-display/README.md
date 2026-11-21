# ESPHome page proof

The shared core and standalone example draw the same normal-page lambda.
Only a plant illustration is static. No inventory, HA access, threshold MQTT
messages or fork infrastructure is required. Recommendations and scales are
fixed YAML values. Soil voltage calibration remains a sensor input.

The ring preserves the legacy 270-degree sweep, radius22, width5 and fill from
the start to the recommendation midpoint. It does not fill the interval
between minimum and maximum. Pointer geometry and raw finite numeric labels
remain unchanged. Binary contours differ by at most one pixel from the Cairo
reference. Material Symbols replace the former PNG icon silhouettes.

## Reproduce with synthetic inputs

Use ESPHome2026.10.0 and the existing label-generator Python dependencies.
Place existing `Audiowide-Regular.ttf` and `MaterialSymbolsOutlined.ttf` files
in one local directory. The fonts are not committed by this contribution.

```sh
python scripts/prove_drawn_display.py --icon-font /path/to/MaterialSymbolsOutlined.ttf
esphome compile tmp/drawn-display/integrated/host.yaml
esphome compile tmp/drawn-display/integrated/host-standalone.yaml
DRAWN_DISPLAY_HOST="$PWD/tmp/drawn-display/integrated/host-build/.pioenvs/drawn-page-host/program" \
  python -m unittest discover -s tests -p test_drawn_display.py -v
python scripts/prove_drawn_display.py --icon-font /path/to/MaterialSymbolsOutlined.ttf \
  --render-host tmp/drawn-display/integrated/host-build/.pioenvs/drawn-page-host/program
esphome compile tmp/drawn-display/integrated/candidate-api.yaml
esphome compile tmp/drawn-display/integrated/candidate-mqtt.yaml
esphome compile tmp/drawn-display/integrated/standalone.yaml
```

Build firmware fixtures sequentially, or use separate ESPHOME_DATA_DIR values.
Parallel first builds can race while populating temporary ESP-IDF components.
The script uses a local public Lemon illustration and synthetic credentials.
The broker is an RFC5737 documentation address. Host fixtures replace only
panel transport, sensors and time. mDNS is disabled and preferences isolated.
Compiling ESP32-S2 fixtures never executes them.

Eight PNGs and a source/fixture/executable-hashed report are written below
ignored `tmp/`. The tests cover normal/inverse pixels, warning limits,
missing/non-finite/extreme measurements, recommendation and scale limits,
zero-width recommendations, long text, French characters and literal percent.
The existing Cairo generator supplies the geometry reference. It is preserved
for printable/historical output; it is not a firmware build prerequisite.

## Cost and limits

Each refresh visits4*46*46 ring candidate pixels. Only annular pixels need
atan2. No extra firmware screen/ring cache is allocated. Linked static RAM
does not measure peak stack or heap. Host durations do not measure ESP32 time,
physical panel refresh, energy or battery lifetime. No energy gain is claimed.
Long text and extreme raw numeric values can overlap. Text is not truncated
or wrapped; choose fitting inputs as described in the display guide.
Audiowide lacks some Latin-Core glyphs; validation reports those warnings.

The fork's normal physical page was accepted by its operator on one ESP32-S2
under2026.10.0. Initial readings and runtime hash were verified. A panel timeout
also existed before the change and remains unresolved. Two later hourly
cycles were not accepted as observed after the operator stopped monitoring.
Physical inversion/invalid scenarios remain untested. This is limited field
evidence for the drawing mechanism, not physical acceptance of this upstream
port or a fleet deployment claim. Upstream review and any deployment remain
separate decisions.
