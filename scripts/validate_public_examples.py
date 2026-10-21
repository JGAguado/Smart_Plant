#!/usr/bin/env python3
"""Validate public API/MQTT examples against this checkout with synthetic secrets.

Only schema validation runs. No compiler, device, broker or live service is used.
ESPHome may download the examples' Google Fonts. The public background is local.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples/multi-device"
PACKAGE_URL = re.compile(
    r"github://JGAguado/Smart_Plant/examples/multi-device/packages/"
    r"(smart_plant_(?:core|profile_api|profile_mqtt)\.yaml)@V2R1"
)


def validate():
    secrets = {
        "wifi_ssid": "offline-example",
        "wifi_password": "offline-example-password",
        "mqtt_broker": "192.0.2.1",
        "mqtt_username": "offline-example",
        "mqtt_password": "offline-example-password",
        "lemon_tree_api_encryption_key": "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",
    }
    label = ROOT / "docs/source/images/programming/Lemon_tree_label_page_1.png"
    with tempfile.TemporaryDirectory(prefix="smart-plant-examples-") as temporary:
        directory = Path(temporary)
        (directory / "secrets.yaml").write_text(yaml.safe_dump(secrets), encoding="utf-8")
        for name in ("my-lemon-tree-api.yaml", "my-lemon-tree.yaml"):
            # Keep the real example's substitutions, credentials references and
            # overrides. Resolve its two public packages from this checkout so
            # CI checks the PR source rather than a previously merged revision.
            source = (EXAMPLES / name).read_text(encoding="utf-8")
            source, count = PACKAGE_URL.subn(
                lambda match: "!include " + yaml.safe_dump(
                    str(EXAMPLES / "packages" / match[1]), default_style='"'
                ).strip(), source
            )
            if count != 2 or "github://" in source:
                raise ValueError(f"{name}: expected two upstream package references")
            fixture = directory / name
            fixture.write_text(source, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "esphome", "-s", "label_image", str(label),
                 "config", str(fixture)], capture_output=True, text=True, timeout=180
            )
            if result.returncode:
                # Inputs are synthetic. Keep failure output bounded for CI logs.
                print((result.stdout + result.stderr)[-12000:], file=sys.stderr)
                raise SystemExit(result.returncode)
            print(f"PASS {name}: current-checkout packages and synthetic secrets", flush=True)


if __name__ == "__main__":
    validate()
