# Haustür Presence

Configurable Home Assistant custom integration for classifying BLE arrival and
departure from any number of Bermuda measurement points.

The integration **does not operate a lock or door actuator**. It produces a
candidate/authorization signal that can be combined with DoorBird or camera
person detection in a normal Home Assistant automation.

## Why this exists

Two BLE distance thresholds are easy to prototype but become difficult to
maintain when:

- multiple people carry both an iPhone and a Watch,
- rooms are physically close to the entrance,
- walls and aluminium doors distort RSSI-derived distances,
- additional BLE proxies are installed later,
- every decision needs an understandable reason.

Haustür Presence compares the complete vector of available proxy distances
against measured location profiles. Adding a third or fourth point therefore
improves the model without adding another nested automation condition.

## Features

- one config entry per independently moving BLE identity,
- arbitrary Bermuda distance sensors as measurement points,
- named calibration profiles such as `WE1 Windfang`, `WE2 Windfang`,
  `Außen direkt vor Tür`, and `Außen 2 m`,
- broad classes `inside`, `outside`, and `away`,
- median-based profiles and logarithmic distance comparison,
- configurable minimum number of available points,
- departure/armed/arrival/window/cooldown state machine,
- optional Bermuda area and tracker inputs,
- safe observation mode enabled by default,
- persistent calibration through Home Assistant's supported storage API,
- diagnostic entities, events, and actions.

## Installation

### Manual

Copy:

```text
custom_components/haustuer_presence
```

to:

```text
/config/custom_components/haustuer_presence
```

Restart Home Assistant, then add **Haustür Presence** under
**Settings → Devices & services → Add integration**.

### HACS custom repository

Add this repository to HACS as an **Integration** custom repository, install it,
restart Home Assistant, and add the integration from Devices & services.

## Initial setup

Create one entry for each tracked BLE identity. An iPhone and Watch should use
separate entries because they can be left in different places. The native door
automation can later accept authorization from either identity.

Select:

1. every Bermuda `Distance to ...` sensor that should be compared,
2. the Bermuda area sensor, if available,
3. the Bermuda tracker, if available,
4. one or more inside and doorway areas using validated area selectors,
5. timing, minimum-point, profile-deviation, and confidence settings.

Keep **Observation mode** enabled initially.

Every config entry remains editable under **Settings → Devices & services →
Integrations → Haustür Presence → Configure**. The options flow offers both
validated selection fields and a complete YAML editor.

### YAML setup and editing

Choose **Import YAML configuration** while adding an identity, or **Edit as
YAML** in an existing entry. The editor validates entity IDs, HA area IDs,
unknown keys, and the configured minimum measurement-point count.

```yaml
name: Example iPhone
distance_entities:
  - sensor.example_distance_to_door
  - sensor.example_distance_to_hall
area_entity: sensor.example_area
tracker_entity: device_tracker.example_bermuda_tracker
inside_areas:
  - hallway
door_areas:
  - entrance
confirm_seconds: 1
window_seconds: 30
cooldown_seconds: 20
min_points: 2
max_distance: 30
max_profile_score: 0.5
min_confidence: 0.2
observe_only: true
allow_tracker_fallback: false
```

`inside_areas` and `door_areas` contain Home Assistant area IDs, not display
names. The selection-field editor handles these IDs automatically.

## Calibration

Calibration should contain several samples from every location that can be
confused with the entrance.

Use **Developer tools → Actions → `haustuer_presence.record_sample`**:

| Example profile | Kind |
|---|---|
| `WE1 Windfang innen` | `inside` |
| `WE2 Windfang` | `inside` |
| `Kinderzimmer türnah` | `inside` |
| `Außen direkt vor Haustür` | `outside` |
| `Außen 1 m` | `outside` |
| `Außen seitlich` | `outside` |

Recommended procedure:

1. Stand still at the location.
2. Wait until at least the configured minimum number of distance sensors have
   numeric states.
3. Record 5–10 samples over approximately 30–60 seconds.
4. Repeat with iPhone/Watch in realistic positions: hand, pocket, and wrist.
5. Review the Classification, Confidence, Phase, and Arrival candidate
   entities.

The three default capture buttons store samples in generic `inside`, `outside`,
and `away` profiles. The action supports arbitrary profile names and is better
for detailed calibration.

## Adding another measurement point

1. Add the proxy to Bermuda and wait for its per-device distance sensors.
2. Open the Haustür Presence integration options.
3. Add the new distance entity to the measurement-point list.
4. Revisit important profiles and capture new samples.

Old samples remain valid. The classifier only compares measurement points that
exist in both the current vector and a stored profile.

## Entities

- `sensor.<name>_phase`
- `sensor.<name>_classification`
- `sensor.<name>_confidence`
- `binary_sensor.<name>_arrival_candidate`
- `binary_sensor.<name>_arrival_authorized`
- calibration buttons

`arrival_authorized` is unavailable in observation mode so it cannot
accidentally be used as a live door authorization.

## Events

- `haustuer_presence_candidate`
- `haustuer_presence_authorized`

Event data includes the config entry, person name, phase, classification,
matched profile, confidence, measurement vector, and observation-mode state.

## Actions

- `haustuer_presence.record_sample`
- `haustuer_presence.clear_calibration`
- `haustuer_presence.force_arm`
- `haustuer_presence.reset`

## Safe rollout

1. Run in observation mode.
2. Collect normal inside movement and real arrival data for several days.
3. Add profiles for every false-positive location.
4. Only disable observation mode once false candidates are acceptably rare.
5. Keep the final actuator action in a native Home Assistant automation:
   require both `arrival_authorized` and DoorBird/Protect person detection,
   followed by a shared cooldown.

## Important limitation

Additional proxies improve classification but cannot make an iPhone or Watch
advertise more frequently. A missing BLE advertisement cannot be recovered by
Python, calibration, or trilateration.
