#!/usr/bin/env python3
"""Render a generic 296x128 label and matching display substitutions.

Gauge arcs derive from JGAguado/Label-maker Plants_labels.py. The corrected
endpoint uses the same 135-degree start angle as Smart Plant runtime needles.
Only the explicit YAML input is read; no inventory or Home Assistant access.
"""

# Original arc renderer: Copyright (c) 2021 J.G.Aguado @JGAguado.
# MIT notice: examples/multi-device/label_maker/LICENSE.Label-maker.txt
import argparse
import math
from pathlib import Path

import cairo
from PIL import Image
import yaml

if __package__:
    from .smartplant_gauge_contract import CONTRACT, angle as gauge_angle, resolve_metrics, substitutions
else:
    from smartplant_gauge_contract import CONTRACT, angle as gauge_angle, resolve_metrics, substitutions

SIZE = tuple(CONTRACT["size"])
GAUGE_ANGLE_DEG = CONTRACT["angle_degrees"]
GAUGE_RADIUS = CONTRACT["radius"]
GAUGE_THICK = CONTRACT["arc_thickness"]
GAUGES = CONTRACT["metrics"]
INK = (0.0, 0.0, 0.0)

def draw_image(ctx, image, top, left, height, width, rot=0):
    image_surface = cairo.ImageSurface.create_from_png(image)
    img_height = image_surface.get_height()
    img_width = image_surface.get_width()
    width_ratio = float(width) / float(img_width)
    height_ratio = float(height) / float(img_height)
    scale_xy = min(height_ratio, width_ratio)
    ctx.save()
    ctx.rotate(rot * math.pi / 180)
    ctx.translate(left, top)
    ctx.scale(scale_xy, scale_xy)
    ctx.set_source_surface(image_surface)
    ctx.paint()
    ctx.restore()


def plot_parameter(ctx, parameter, thick=GAUGE_THICK):
    alpha = math.radians(GAUGE_ANGLE_DEG)
    beta = 2 * math.pi - alpha

    rel_range = parameter["rel_range"]
    abs_r = parameter["abs_range"]
    left = parameter["position"][0]
    top = parameter["position"][1]
    radius = parameter["radius"]

    if rel_range[0] < abs_r[0] or rel_range[1] > abs_r[1]:
        raise ValueError(f"rel_range {rel_range} not within abs_range {abs_r}")

    endpoint = gauge_angle(sum(rel_range) / 2, abs_r)

    # Icon (centred in the ring)
    if parameter.get("icon"):
        size = radius
        draw_image(ctx, parameter["icon"],
                   top + radius - size / 2, left + radius - size / 2, size, size)

    # Filled segment: gauge start -> midpoint of recommended band
    ctx.set_line_width(1)
    ctx.set_source_rgb(*INK)
    ctx.move_to(left + radius + (radius - thick) * math.cos(math.pi / 2 + beta / 2),
                top + radius + (radius - thick) * math.sin(math.pi / 2 + beta / 2))
    ctx.arc(left + radius, top + radius, radius, math.pi / 2 + beta / 2, endpoint)
    ctx.line_to(left + radius + radius * math.cos(endpoint),
                top + radius + radius * math.sin(endpoint))
    ctx.arc_negative(left + radius, top + radius, radius - thick, endpoint, math.pi / 2 + beta / 2)
    ctx.fill()
    ctx.stroke()

    # Full 270deg contour outline
    ctx.set_source_rgb(*INK)
    ctx.move_to(left + radius + (radius - thick) * math.cos(math.pi / 2 + beta / 2),
                top + radius + (radius - thick) * math.sin(math.pi / 2 + beta / 2))
    ctx.arc(left + radius, top + radius, radius, math.pi / 2 + beta / 2, math.pi / 2 - beta / 2)
    ctx.line_to(left + radius + radius * math.cos(math.pi / 2 - beta / 2),
                top + radius + radius * math.sin(math.pi / 2 - beta / 2))
    ctx.arc_negative(left + radius, top + radius, radius - thick, math.pi / 2 - beta / 2, math.pi / 2 + beta / 2)
    ctx.stroke()


# ---------------------------------------------------------------------------

def render_label(out_path, config):
    metrics = resolve_metrics(config)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, *SIZE)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    ctx.set_source_rgb(*INK)
    ctx.select_font_face("Sans")
    ctx.set_font_size(15)
    ctx.move_to(2, 18)
    ctx.show_text(str(config.get("name", "Smart Plant")))
    ctx.set_font_size(10)
    ctx.move_to(2, 33)
    ctx.show_text(str(config.get("subtitle", "")))
    for metric, settings in GAUGES.items():
        spec = metrics[metric]
        plot_parameter(ctx, {"rel_range": spec["band"], "abs_range": spec["scale"],
                             "position": settings["position"], "radius": GAUGE_RADIUS})
        ctx.set_font_size(8)
        ctx.move_to(settings["position"][0] + 8, settings["position"][1] + GAUGE_RADIUS + 3)
        ctx.show_text(settings["label"])
    surface.write_to_png(str(out_path))
    with Image.open(out_path) as image:
        image.convert("L").point(lambda p: 255 if p >= 160 else 0, mode="1").save(out_path)
    return substitutions(metrics)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--substitutions", required=True, type=Path)
    args = parser.parse_args()
    if args.image.resolve() == args.substitutions.resolve():
        parser.error("image and substitutions need distinct paths")
    if args.config.resolve() in (args.image.resolve(), args.substitutions.resolve()):
        parser.error("output paths must differ from the input configuration")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    # Validate all ranges before writing either output.
    resolve_metrics(config)
    for path in (args.image, args.substitutions):
        path.parent.mkdir(parents=True, exist_ok=True)
    overrides = render_label(args.image, config)
    args.substitutions.write_text(yaml.safe_dump({"substitutions": overrides}, sort_keys=False), encoding="utf-8")
    print(f"Wrote {args.image} and {args.substitutions}")


if __name__ == "__main__":
    main()
