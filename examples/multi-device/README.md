# Multi-device ESPHome packages

The example separates hardware and measurement behavior from the Home
Assistant transport:

- `smart_plant_core.yaml` contains the board, sensors, display, Wi-Fi and deep
  sleep behavior.
- `smart_plant_profile_mqtt.yaml` publishes retained MQTT state, so the last
  readings remain visible while the device sleeps.
- `smart_plant_profile_api.yaml` uses only the native ESPHome API. It is simpler,
  but entities become unavailable during deep sleep.

Start from `my-lemon-tree.yaml` for MQTT or `my-lemon-tree-api.yaml` for the
native API, set its substitutions and compose the core with exactly one
transport profile. Keep credentials in the local `secrets.yaml`; remote package
files contain no secrets.

The MQTT example preserves an explicit topic prefix. Treat that prefix as a
stable identity after Home Assistant discovery, because changing it creates new
entities.
