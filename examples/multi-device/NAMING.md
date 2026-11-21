# Device names, entity names and label text

Choose device names before the first installation. Keep technical identity
stable when a plant moves or its common name changes.

This guide describes the current shared packages on `V2R1`. The standalone
[configuration](../../docs/source/files/configuration.yaml) has its own layout.

## Know which name you are changing

| Setting or surface | Current behavior | Recommendation |
| --- | --- | --- |
| `device_name` | Supplies `esphome.name`. The core enables `name_add_mac_suffix`, so the runtime name also includes a MAC suffix. | Use a stable lowercase key, such as `plant-01`. Give configurations built together distinct names. |
| `friendly_name` substitution | Prefixes entity names, such as `Lemon Tree Temperature`. The shared core also draws it on Maintenance, Storage and low-battery pages. It does not set `esphome.friendly_name`. | Choose it before discovery. Treat later changes as entity identity changes in the current packages. |
| `device_comment` | Supplies the ESPHome device comment. Its default is `${friendly_name}`. | Use a botanical description or an installation note. It does not rename entities. |
| `mqtt_topic_prefix` | Sets the MQTT state and command namespace. The profile defaults to `${device_name}`; the example overrides it with an explicit MAC-bearing value. | Give each device a unique prefix and keep it stable. |
| Label title and subtitle | The normal page obtains these from its background image. Firmware overlays readings, needles, battery and time. | Edit the label image to change normal-page text with the current examples. |
| Home Assistant display name | A user can change the visible name in HA without editing firmware. | Use this for a local presentation change. Check dashboards that refer to names. |
| Home Assistant `entity_id` | Identifies an entity in automations and dashboards. It is separate from its visible name and MQTT discovery `unique_id`. | Treat an ID rename as a separate operation. Update its consumers. |

The MAC suffix on the runtime ESPHome name does **not** append itself to an
explicit `mqtt_topic_prefix`. Two devices using the profile's default prefix
and the same `device_name` share state and command topics, even if their runtime
names differ. The explicit prefix in `my-lemon-tree.yaml` avoids this only when
you replace the sample suffix with each device's actual value.

The upstream packages do not provide the fork's `configured_name`,
`display_name`, `screen_title` or `secondary_name` substitutions. Adding those
names to a device file alone does not add their behavior.

## Check MQTT discovery before renaming

These details were checked against ESPHome **2026.9.0**:

- The profile leaves `discovery_unique_id_generator` at its `legacy` default.
  Its ID is `ESP` + component type + entity object ID. The object ID comes from
  the entity name. The MAC is absent. Two devices with the same entity names
  can therefore advertise identical unique IDs.
- The optional `mac` generator uses the MAC, component type and a hash of the
  entity name. It distinguishes devices, but an entity rename still changes
  its unique ID.
- `discovery_object_id_generator: device_name` supplies a proposed object ID
  from the runtime node name and entity object ID. It does not migrate existing
  HA registry entries or their consumers.

See the pinned [discovery implementation](https://github.com/esphome/esphome/blob/2026.9.0/esphome/components/mqtt/mqtt_component.cpp)
and [configuration defaults](https://github.com/esphome/esphome/blob/2026.9.0/esphome/components/mqtt/__init__.py).
Recheck your ESPHome version before applying a change.

Do not change discovery generators or entity names as a cosmetic edit on an
installed device. Capture its discovery payloads, HA registry entries and
automation references first. Prepare a migration and recovery plan. Firmware
changes alone do not guarantee preservation of HA entity associations or history.

Changing `mqtt_topic_prefix` also moves retained controls and telemetry.
Old retained discovery and command messages can remain on the broker. Account
for both namespaces in a planned migration.

## A naming model for future improvements

For a future package change, keep these roles separate:

1. A stable, unique device key for hostnames, build artifacts and MQTT topics.
2. A readable plant name for people, independent of the technical key.
3. Fixed function-only entity names, such as `Temperature` and `Soil Moisture`.
4. Optional short screen text when the full plant name does not fit.

For example, two devices can have keys `plant-01` and `plant-02`, share the
human name `Lemon Tree`, and show `Lemon Kitchen` and `Lemon Terrace` on screen.
A room is useful display text, but a device can move. Keep it out of the
permanent key when possible.

Function-only names with MAC-based MQTT unique IDs would let a human name
change without changing each entity name. This needs a package change and an
explicit migration for existing installations. It is not the current default.
Do not copy only the generator settings into an existing fleet.

Normal-page titles are currently baked into the image. Moving text into
ESPHome would make names easier to maintain. Removing the generator entirely
also requires a replacement for its artwork, gauge outlines and recommendation
bands. That work remains a separate design and validation task.

Related discussions: [contribution overview #24](https://github.com/JGAguado/Smart_Plant/issues/24)
and [identity findings #42](https://github.com/JGAguado/Smart_Plant/issues/42).
