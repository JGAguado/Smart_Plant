#!/usr/bin/env python3
"""Prepare synthetic local builds. Never call a device, broker, HA or builder.

Run with the ESPHome 2026.10.0 Python environment. This writes only to tmp/.
Shared and standalone pages have no runtime renderer switch. Baselines are test inputs.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image, ImageDraw
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("examples/multi-device/packages/smart_plant_core.yaml", "docs/source/files/configuration.yaml")
PACKAGES = ROOT / "examples/multi-device/packages"


class Loader(yaml.SafeLoader):
    pass


class Lambda(str):
    pass


Loader.add_constructor("!lambda", lambda loader, node: Lambda(loader.construct_scalar(node)))
yaml.SafeDumper.add_representer(Lambda, lambda dumper, value: dumper.represent_scalar("!lambda", value, style="|"))


def load_page(path):
    return yaml.load(path.read_text(encoding="utf-8"), Loader)


def prepare(output, icon_font):
    output = output.resolve()
    if (ROOT / "tmp").resolve() not in output.parents:
        raise ValueError("proof output must be below the ignored project tmp/")
    output.mkdir(parents=True, exist_ok=True)
    core = load_page(PACKAGES / "smart_plant_core.yaml")
    public = load_page(ROOT / "docs/source/files/configuration.yaml")
    fonts = copy.deepcopy(core["font"])
    audiowide = icon_font.parent / "Audiowide-Regular.ttf"
    for font in fonts:
        font["file"] = str(audiowide) if font["file"] == "gfonts://Audiowide" else str(icon_font.resolve())
        if not Path(font["file"]).is_file():
            raise ValueError(f"missing font: {font['file']}")
    illustration = ROOT / "docs/source/images/programming/Lemon_tree.png"
    synthetic = {"device_name": "drawn-page-proof", "display_name": "Example plant",
                 "screen_title": "Example plant", "secondary_name": "Synthetic inputs",
                 "ota_password": "offline-synthetic-ota", "wifi_ssid": "offline-synthetic", "wifi_password": "offline-synthetic-password",
                 "mqtt_broker": "192.0.2.1", "api_encryption_key": "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",
                 "plant_illustration": str(illustration), "illustration_x": "10", "illustration_y": "37",
                 "illustration_width": "90", "illustration_height": "90"}
    shutil.copyfile(ROOT / "tests/drawn_display_host.h", output / "host.h")
    for name, entry in (("host", core), ("host-standalone", public)):
        host = {key: copy.deepcopy(entry[key]) for key in ("substitutions", "image")}
        host["substitutions"].update(synthetic)
        host.update(host={}, logger={"level": "WARN"}, mdns={"disabled": True}, display=[], font=fonts)
        body = entry["display"][0]["pages"][0]["lambda"]
        for sensor in ("batpercent", "soil", "light", "temp", "hum", "esptime"):
            body = body.replace(f"id({sensor})", sensor)
        body = body.replace('"${screen_title}"', "proof_title").replace('"${secondary_name}"', "proof_subtitle")
        # Host-only controls exercise edge recommendations and isolate ring ink.
        body = body.replace("auto draw_ring =", "if (proof_ring_only) it.fill(bg);\nauto draw_ring =")
        body = body.replace("const float midpoint =", '''
if (const char *bands = std::getenv("SMART_PLANT_RECOMMENDATION")) {
  float low, high;
  if (std::sscanf(bands, "%f %f", &low, &high) != 2) std::exit(2);
  recommended_min = vmin + low * (vmax - vmin);
  recommended_max = vmin + high * (vmax - vmin);
}
const float midpoint =''')
        body = body.replace("it.printf(xc + 22, yc + 11", "if (!proof_ring_only) it.printf(xc + 22, yc + 11")
        body = body.replace("draw_gauge(id(", "if (!proof_ring_only) draw_gauge(id(")
        # Sensor id() references were replaced above.
        for sensor in ("soil", "light", "temp", "hum"):
            body = body.replace(f"draw_gauge({sensor}.", f"if (!proof_ring_only) draw_gauge({sensor}.")
        host["esphome"] = {
            "name": "drawn-page-host", "build_path": str(output / (name + "-build")),
            "includes": [str(output / "host.h")],
            "on_boot": {"priority": -100, "then": [{"lambda": '''
const char *input = std::getenv("SMART_PLANT_VALUES");
if (!input) std::exit(2);
float v[5]; int present[5];
if (std::sscanf(input, "%f %d %f %d %f %d %f %d %f %d",
    &v[0], &present[0], &v[1], &present[1], &v[2], &present[2],
    &v[3], &present[3], &v[4], &present[4]) != 10) std::exit(2);
ProofSensor batpercent{v[0], bool(present[0])}, soil{v[1], bool(present[1])},
    light{v[2], bool(present[2])}, temp{v[3], bool(present[3])}, hum{v[4], bool(present[4])};
ProofTime esptime;
ProofDisplay it;
const char *proof_title = std::getenv("SMART_PLANT_TITLE");
const char *proof_subtitle = std::getenv("SMART_PLANT_SUBTITLE");
if (!proof_title) proof_title = "${screen_title}";
if (!proof_subtitle) proof_subtitle = "${secondary_name}";
const bool proof_ring_only = std::getenv("SMART_PLANT_RING_ONLY") != nullptr;
const auto started = std::chrono::steady_clock::now();
''' + body + '''
const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
    std::chrono::steady_clock::now() - started).count();
const char *path = std::getenv("SMART_PLANT_OUTPUT");
if (!path) std::exit(2);
it.save(path);
std::printf("PROOF us=%lld writes=%u\\n", static_cast<long long>(elapsed), it.writes);
std::exit(0);
'''}]},
        }
        (output / (name + ".yaml")).write_text(yaml.safe_dump(host, allow_unicode=True, sort_keys=False))

    for name, entry in (("candidate-api", core), ("candidate-mqtt", core),
                        ("standalone", public)):
        fixture = copy.deepcopy(entry)
        fixture["substitutions"].update(synthetic)
        fixture["font"] = copy.deepcopy(fonts)
        fixture["esphome"]["build_path"] = str(output / (name + "-build"))
        if name == "standalone":
            # Import metadata is irrelevant to a local full-config compile.
            fixture.pop("dashboard_import", None)
            fixture["wifi"].update(ssid="offline-synthetic", password="offline-synthetic-password")
        else:
            profile = "mqtt" if name.endswith("mqtt") else "api"
            fixture["packages"] = {"transport": None}
        text = yaml.safe_dump(fixture, allow_unicode=True, sort_keys=False)
        if name != "standalone":
            text = text.replace("transport: null", f"transport: !include {PACKAGES}/smart_plant_profile_{profile}.yaml")
        (output / (name + ".yaml")).write_text(text)
    print(f"Prepared integrated shared/standalone host and ESP32-S2 fixtures in {output}")


def render_cases(output, executable):
    """Run only a previously built host executable; produce reviewable proof."""
    output = output.resolve()
    executable = executable.resolve()
    cases = {
        "normal": ("70 1 40 1 1500 1 22 1 50 1", {}),
        "inverted": ("25 1 40 1 1500 1 22 1 50 1", {}),
        "invalid": ("nan 1 nan 1 inf 1 -inf 1 50 0", {}),
        "outside-scales": ("70 1 -5 1 10000 1 -15 1 120 1", {}),
        "scale-minima": ("70 1 0 1 0 1 -10 1 20 1", {}),
        "scale-maxima": ("70 1 100 1 3775 1 50 1 80 1", {}),
        "long-title": ("70 1 40 1 1500 1 22 1 50 1", {
            "SMART_PLANT_TITLE": "Very long plant title 100%",
            "SMART_PLANT_SUBTITLE": "Long botanical subtitle that exceeds the title area"}),
        "clock-valid": ("70 1 40 1 1500 1 22 1 50 1", {"SMART_PLANT_CLOCK_VALID": "1"}),
    }
    sheet = Image.new("RGB", (296 * 2, len(cases) * 148 * 2), "#dddddd")
    draw = ImageDraw.Draw(sheet)
    results = []
    for i, (name, (values, extra)) in enumerate(cases.items()):
        pgm = output / (name + ".pgm")
        # Do not inherit synthetic controls from a previous shell invocation.
        env = {k: v for k, v in os.environ.items() if not k.startswith("SMART_PLANT_")}
        env.update(extra, SMART_PLANT_VALUES=values, SMART_PLANT_OUTPUT=str(pgm),
                   ESPHOME_PREFDIR=str(output / "prefs"))
        result = subprocess.run([str(executable)], cwd=output, env=env,
                                check=True, capture_output=True, text=True, timeout=10)
        match = re.search(r"PROOF us=(\d+) writes=(\d+)", result.stdout)
        if not match:
            raise ValueError(f"no proof result for {name}")
        with Image.open(pgm) as image:
            image.save(output / (name + ".png"))
            sheet.paste(image.convert("RGB").resize((592, 256), Image.Resampling.NEAREST), (0, i * 296 + 40))
        draw.text((8, i * 296 + 10), name, fill="black")
        results.append({"case": name, "host_render_us": int(match[1]), "pixel_writes": int(match[2])})
    sheet.save(output / "preview.png")
    report = {
        "scope": "Synthetic inputs; ESPHome host display/font/image implementation; no physical panel",
        "host_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                          for name in SOURCES},
        "fixture_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in sorted(output.glob("*.yaml"))},
        "measurements": results,
        "limits": "Host timings are not ESP32 timings or energy measurements. No live acquisition or sleep proof.",
    }
    (output / "render-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Rendered {len(cases)} cases: {output / 'preview.png'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/drawn-display/integrated")
    parser.add_argument("--icon-font", type=Path, required=True,
                        help="Existing Material Symbols Outlined TTF (no network font lookup)")
    parser.add_argument("--render-host", type=Path, help="Run a previously built host proof executable")
    args = parser.parse_args()
    prepare(args.output, args.icon_font)
    if args.render_host:
        render_cases(args.output, args.render_host)
