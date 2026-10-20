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

## Build the checked-out contribution

The example device files fetch remote packages from the production fork's
`V2R1` branch. They do not select this staging contribution automatically.
To validate this checkout, replace the `packages` block in your local device
configuration with local includes. Keep the core and transport from the same
checkout:

```yaml
packages:
  core: !include packages/smart_plant_core.yaml
  transport: !include packages/smart_plant_profile_api.yaml
```

For MQTT, use `packages/smart_plant_profile_mqtt.yaml` as the transport instead.
Keep the device file beside the `packages` directory. Supply its local secrets
and label image before validation. Keep those settings out of commits.

```sh
esphome config examples/multi-device/my-lemon-tree-api.yaml
esphome compile examples/multi-device/my-lemon-tree-api.yaml
```

Use `my-lemon-tree.yaml` for the MQTT variant. These commands validate and build
the selected local packages. They do not upload firmware.

Both profiles use the released `waveshare_epaper` driver and wait for the
panel's physical BUSY cycle before deep sleep. They deliberately keep the
captive portal and Improv Serial recovery paths from the original example; the
captive portal also enables ESPHome's browser-based recovery upload surface.
Deployments that do not need local fallback provisioning can remove
`captive_portal`, `improv_serial`, and the Wi-Fi `ap` block together.

## Low-battery protection

Both transport profiles use the same battery policy. Below 30%, the normal
page changes to white marks on a black background. At or below 15%, the device
shows a critical battery page and sleeps for 24 hours. It keeps this protection
until a valid reading reaches 22% or more. The latch survives deep sleep and
power loss. Charging or changing the battery releases it on the next valid
reading. Missing and non-finite readings do not change the latch.

Override the defaults in the device substitutions:

```yaml
substitutions:
  low_batt_crit_pct: "15"
  low_batt_exit_pct: "22"
  low_batt_warn_pct: "30"
  low_batt_sleep_duration: "24h"
```

Thresholds must satisfy `0 <= critical < exit < warning <= 100`. An invalid
order fails compilation. The long sleep also applies after a panel BUSY fault.
The normal sleep remains one hour. Both paths keep OTA image confirmation and
the existing display completion or emergency reset sequence before sleep.
This feature does not require MQTT or Home Assistant commands.

This upstream staging contribution keeps the baseline's explicit
`safe_mode.mark_successful` action before both sleep paths. It does not declare
the production fork's ESPHome `>=2026.8.0` requirement. Production can rely on
native image confirmation under that requirement. The offline tests check the
explicit action's ordering; they do not simulate bootloader confirmation.
Complete local API and MQTT builds verify action availability with ESPHome
2026.9.0. Older ESPHome versions were not compiled in this review.
