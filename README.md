
[![Documentation Status][documentation-shield]][documentation]
[![License][license-shield]](LICENSE)
[![Project Maintenance][maintenance-shield]][maintenance]
[![buyit][buyit-shield]][buyit]

# Smart Plant
The Smart Plant is a board that can be plugged directly on the soil, close to the plant, that allows the measurement of the environment (soil moisture, environment temperature & illuminance), and presents the information on an ePaper display.

<p float="left">
   <img src="./Documentation/Images/Top.png" width="49%">
   <img src="./Documentation/Images/Bottom.png" width="49%">   
</p>

## Project tree

<li><a href="./Design/">Design</a></li>
<li><a href="./Documentation/">Documentation</a></li>

<li><a href="./README.md">README.md</a></li>

## ESPHome firmware paths

- The [programming guide](./docs/source/programming.rst) and its standalone
  configuration are the simplest starting point for one device using the
  native ESPHome API.
- The [multi-device example](./examples/multi-device/my-lemon-tree.yaml) and
  [shared package](./examples/multi-device/packages/smart_plant_base.yaml)
  demonstrate retained MQTT telemetry for deployments where values should
  remain visible while devices sleep.



[documentation-shield]: https://readthedocs.org/projects/smart-plant/badge/?version=v2r1&style=for-the-badge
[documentation]: https://smart-plant.readthedocs.io/

[license-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg?style=for-the-badge

[maintenance-shield]: https://img.shields.io/badge/maintainer-J.%20G.%20Aguado-2e48a7.svg?style=for-the-badge
[maintenance]: https://github.com/JGAguado

[buyit-shield]: https://img.shields.io/badge/get%20it%20on-elecrow-399BD7.svg?style=for-the-badge
[buyit]: https://www.elecrow.com/smart-plant.html
