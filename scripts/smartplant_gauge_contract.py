"""Explicit label geometry and display scales, without fleet-owned data."""
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = yaml.safe_load((ROOT / "examples/multi-device/label_maker/gauge-contract.yaml").read_text())


def pair(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must contain two numbers")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError(f"{name} must contain finite numbers")
    return list(map(float, value))


def resolve_metrics(config):
    if not isinstance(config, dict) or not isinstance(config.get("metrics"), dict):
        raise ValueError("configuration needs a metrics mapping")
    if set(config["metrics"]) != set(CONTRACT["metrics"]):
        raise ValueError("configuration needs exactly moisture, illuminance, temperature and humidity")
    resolved = {}
    for metric, geometry in CONTRACT["metrics"].items():
        spec = config["metrics"][metric]
        if not isinstance(spec, dict):
            raise ValueError(f"{metric} needs a mapping")
        scale = pair(spec.get("scale", geometry["scale"]), f"{metric} scale")
        band = pair(spec.get("band"), f"{metric} band")
        if not scale[0] <= band[0] <= band[1] <= scale[1] or scale[0] >= scale[1]:
            raise ValueError(f"{metric} band is outside its increasing display scale")
        if metric == "moisture" and scale != [0, 100]:
            raise ValueError("the firmware moisture scale is fixed at 0-100")
        if metric == "illuminance" and scale[0] != 0:
            raise ValueError("the firmware illuminance scale starts at zero")
        resolved[metric] = {"scale": scale, "band": band}
    return resolved


def angle(value, scale):
    """Clockwise screen angle, identical to the runtime's 270-degree needle."""
    minimum, maximum = scale
    sweep = math.radians(CONTRACT["angle_degrees"])
    start = math.pi / 2 + (2 * math.pi - sweep) / 2
    return start + (min(max(value, minimum), maximum) - minimum) / (maximum - minimum) * sweep


def substitutions(metrics):
    return {
        "light_max": str(metrics["illuminance"]["scale"][1]),
        "temp_min": str(metrics["temperature"]["scale"][0]),
        "temp_max": str(metrics["temperature"]["scale"][1]),
        "hum_min": str(metrics["humidity"]["scale"][0]),
        "hum_max": str(metrics["humidity"]["scale"][1]),
    }
