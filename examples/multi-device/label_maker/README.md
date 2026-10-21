# Generic e-paper label generator

This is an optional adaptation of JGAguado's [Label-maker](https://github.com/JGAguado/Label-maker).
The original renderer already covers label creation. This extraction adds a
shared scale contract and fixes the recommendation endpoint to use the same
135-degree start angle as Smart Plant's runtime needle. The original MIT
notice is retained in `LICENSE.Label-maker.txt`.

`example.yaml` contains synthetic recommendation bands. It contains no device
identity, Home Assistant snapshot or plant artwork. `gauge-contract.yaml`
defines the four positions and default scales from the current shared core.
The defaults preserve humidity 20-80 and light 0-3775. They are display ranges,
not calibration or botanical advice. Change each `band` to the intended range.
An optional `scale` must contain that band.

Run from the repository root in a Python virtual environment:

```sh
python3 -m pip install -r examples/multi-device/label_maker/requirements.txt
python3 scripts/smartplant_label_maker.py \
  --config examples/multi-device/label_maker/example.yaml \
  --image tmp/labels/example.png \
  --substitutions tmp/labels/display-scales.yaml
```

The command writes a 1-bit 296x128 PNG and matching ESPHome display substitutions.
Validate the image before use. Place both generated files beside the local
device configuration. Include `display-scales.yaml` as a package after the
core package. Remove conflicting device-level gauge substitutions; they take
precedence over package values. Set `label_image` to `example.png` in the
device substitutions. Use the
same YAML input to regenerate both outputs after a scale change. Moisture is
fixed at 0-100 in firmware. Light starts at 0. The tool rejects unsupported or
nonfinite ranges before writing either output.

The filled band ends at the recommendation midpoint. The renderer and live
needle use `135deg + 270deg * (value-min)/(max-min)`. The displayed measurement
remains raw; only the needle clamps. Neither generation nor these local tests
contacts devices or changes firmware:

```sh
python3 -m unittest discover -s tests -p test_generic_labels.py -v
```

The tests execute the actual runtime C++ gauge, compare arc endpoints and
scales, reject invalid inputs and render twice to check deterministic output.
They need `g++` plus the listed Python packages. PNG bytes can change with
rendering-library versions. New hardware or fleet validation remains a
separate operation. Revert this isolated optional-tool contribution to undo it.

With ESPHome 2026.9.0 installed, also run:

```sh
python3 -m unittest discover -s tests -p test_label_packages.py -v
```

These tests check the real package loader with custom scales, reversed package
order and conflicting device substitutions.
