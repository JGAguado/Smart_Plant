# Smart Plant

**See how your plant is doing — on its own e-paper label and in Home Assistant.**

Smart Plant measures soil moisture, light, temperature and humidity. Place it
in your plant pot, read the measurements on the 2.9-inch e-paper display,
and connect it to Home Assistant with ESPHome.

![Five Smart Plant devices with custom plant labels and coloured enclosures](docs/source/_static/Slide%202.png)

**[Get started](https://smart-plant.readthedocs.io/en/v2r1/getting_started.html)**
· **[Create your plant label](https://github.com/JGAguado/Label-maker)**
· **[Get a board](https://www.elecrow.com/smart-plant.html)**
· **[Read the documentation](https://smart-plant.readthedocs.io/en/v2r1/)**

[![Documentation](https://readthedocs.org/projects/smart-plant/badge/?version=v2r1)](https://smart-plant.readthedocs.io/en/v2r1/)
[![Firmware tests](https://github.com/JGAguado/Smart_Plant/actions/workflows/firmware-tests.yml/badge.svg?branch=V2R1)](https://github.com/JGAguado/Smart_Plant/actions/workflows/firmware-tests.yml)
[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/license-CC_BY--NC--SA_4.0-lightgrey)](LICENSE)

## A useful label for every plant

- **Check the soil and surroundings.** Read soil moisture, ambient light,
  air temperature and relative humidity.
- **Read it at the pot.** The e-paper screen shows the last displayed readings
  while the device sleeps.
- **Make it yours.** Give each plant its own name, illustration and gauge
  background with the companion Label-maker project.
- **Connect to Home Assistant.** Choose the native ESPHome API or retained
  MQTT readings for devices that spend most of their time asleep.
- **Run on battery.** The firmware sleeps between measurement cycles.
  The hardware also supports an optional solar cell.

## Start with one plant

1. [Get a board](https://www.elecrow.com/smart-plant.html), or use the
   [hardware design files](Design/) to explore the board.
2. Follow the [getting-started guide](https://smart-plant.readthedocs.io/en/v2r1/getting_started.html)
   and [ESPHome programming guide](https://smart-plant.readthedocs.io/en/v2r1/programming.html).
3. Set your Wi-Fi credentials and calibrate the soil sensor for your setup.
4. Add your own label background, then install the firmware.

The [standalone configuration](docs/source/files/configuration.yaml) is the
starting point for a single device. Read the
[safety instructions](https://smart-plant.readthedocs.io/en/v2r1/safety.html)
before assembly and flashing.

## Create your plant label

The companion **[Label-maker](https://github.com/JGAguado/Label-maker)**
generates printable plant labels and e-paper backgrounds from JSON or YAML
templates. Use it to add a plant name and illustration to your display.

[![Example lemon-tree e-paper background](docs/source/images/programming/Lemon_tree_label_page_1.png)](https://github.com/JGAguado/Label-maker/tree/main/1_Plants)

Follow the [step-by-step label guide](docs/source/labels.rst).
Start with the [plant examples and generator](https://github.com/JGAguado/Label-maker/tree/main/1_Plants),
then follow the programming guide to use the resulting background image.
The firmware draws the live readings over that image.

## Connect one plant or several

| Setup | Starting point | During deep sleep |
| --- | --- | --- |
| One device with the native ESPHome API | [Standalone configuration](docs/source/files/configuration.yaml) | No network response; entity availability depends on Home Assistant setup. |
| Several devices with retained MQTT readings | [MQTT example](examples/multi-device/my-lemon-tree.yaml) | Last published readings remain available. |
| Shared packages with the native ESPHome API | [API example](examples/multi-device/my-lemon-tree-api.yaml) | No network response; entity availability depends on Home Assistant setup. |

The [multi-device guide](examples/multi-device/README.md) explains the shared
hardware core and transport profiles. Each device sets its identity and
credentials. Calibration and label images use shared defaults unless overridden.

## Explore the hardware

Smart Plant combines an ESP32-S2, a soil-moisture probe, environmental sensors
and an e-paper display. The repository includes board design files and
printable enclosure models.

- [Board design](Design/)
- [Enclosure models](Enclosure/)
- [Schematics and supporting files](Documentation/)
- [Technical specifications](https://smart-plant.readthedocs.io/en/v2r1/specs.html)
- [Assembly guide](https://smart-plant.readthedocs.io/en/v2r1/assembly.html)

## Questions and contributions

Use [Discussions](https://github.com/JGAguado/Smart_Plant/discussions) for
questions and ideas. Report reproducible problems in
[Issues](https://github.com/JGAguado/Smart_Plant/issues).

Contributions to firmware, documentation and examples are welcome. Describe
the problem, the change and how you verified it in your pull request.

Created by [J. G. Aguado](https://github.com/JGAguado), with contributions
from the community.

## License

This project uses [CC BY-NC-SA 4.0](LICENSE). See the license for attribution,
non-commercial use and sharing requirements.
