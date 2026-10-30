# COEX API and client notes

These notes describe the bundled client's behavior and historical MX40 Pro
observations, not a promise that every COEX model implements the same API.
The [hardware matrix](HARDWARE-VERIFICATION.md) distinguishes physical verification
from simulated tests.

## Transport and errors

The controller exposes HTTP/JSON on TCP port 8001 without authentication. Replies
use an envelope such as:

```json
{"code": 0, "message": "Success", "data": {}}
```

The client accepts codes 0 and 200. Other codes raise `CoexApiError`, with a code,
message and endpoint. An error message containing `locked` raises
`CoexDeviceLocked`; close VMP to release the exclusive session. HTTP failures,
timeouts, malformed JSON and missing/invalid response codes raise
`CoexConnectionError`. The default per-request timeout is five seconds.

A supplied `aiohttp.ClientSession` remains owned by the caller. Without one, use
`async with CoexClient(...)` or call `close()` to release the client's session.
Hosts are bare IP addresses or hostnames; IPv6 literals are bracketed in URLs.

## Sources and firmware differences

Protocol work used [NovaStar's API reference](https://api.coex.novastar.tech/en/),
the older 2023 COEX API manual, NovaStar's `@novastar-dev/coex` JavaScript client,
and direct observations on MX40 Pro V1.5.0 in September 2026. They disagree in
several places. The behavior below prioritizes recorded hardware results; it is
not a fresh validation of every vendor endpoint.

Notable differences:

- MX40 Pro display-mode reads match writes: **0 normal, 1 blackout, 2 freeze**.
  The reference consulted during development reversed the last two read values.
- The tested screen working-mode endpoint uses **0 Send-Only, 1 All-in-One**.
  The client also parses older read values 2/3. The legacy device-level mode write
  was accepted but did not change the screen's working mode.
- Brightness on the tested MX40 Pro is a **0–1 ratio**, while the JavaScript client
  used 0–100. The Python interface always accepts percentages.
- Input routing requires a screen ID and layer list on the tested firmware;
  a body containing only a source group ID was rejected.

## Reads

| Client method | GET path | Parsed result |
| --- | --- | --- |
| `get_screens()` | `/api/v1/screen` | Screens, canvas IDs, processing modes and layers |
| `get_display_params()` | `/api/v1/screen/displayparams` | Per-screen raw brightness, color temperature and gamma |
| `get_display_state()` | `/api/v1/screen/output/display/state` | Display modes and mapping state by canvas ID |
| `get_presets()` | `/api/v1/preset` | Preset slots, names and active flags, scoped to screens |
| `get_input_sources()` | `/api/v1/device/input/sources` | Source names, connector IDs and group IDs |
| `get_monitor_info()` | `/api/v1/device/monitor/info` | Temperatures, runtime, fan speeds, voltages and cabinet count |
| `get_cabinets()` | `/api/v1/device/cabinet` | Raw cabinet records |

`get_status(include_monitor=True)` aggregates these reads except the cabinet-list
endpoint. Screens are required. Unsupported or unreachable optional endpoints
leave their part empty; a VMP lock always propagates. The HA coordinator caches
monitoring between scheduled reads and clears it if a scheduled read fails.

`displayparams.list` can be an object or a list. With cabinets unpowered, the
captured MX40 Pro returned empty display parameters and cabinet lists; the
controller itself remained reachable. Preset parsers accept `screenPresets` and
older `screenPresetList`/`presetList` spellings. Optional/missing fields remain
unknown rather than being replaced with invented measurements.

## Screen controls

| Method | Request | Notes |
| --- | --- | --- |
| `normal()`, `blackout()`, `freeze()` | `PUT /api/v1/screen/output/displaymode` with `value` and `screenIdList` | Empty screen list affects all screens. Values 0/1/2. |
| `set_display_mode_canvases()` | `PUT /api/v1/device/displaymode` with `value`, `canvasIDs` | Requires a nonempty canvas list. |
| `set_brightness(percent, screen_ids=None)` | `PUT /api/v1/screen/brightness` with `brightness`, `screenIdList`, `screenIds` | Percent argument is 0–100; both list spellings are sent for compatibility. |
| `set_color_temperature(kelvin, screen_ids=None)` | `PUT /api/v1/screen/colortemperature` with `colorTemperature`, `screenIdList` | 1700–15000 K; write needs hardware verification. |
| `set_gamma(gamma, screen_ids=None)` | `PUT /api/v1/screen/gamma` with `gamma`, `screenIdList` | 1.0–4.0; write needs hardware verification. |
| `set_working_mode(mode, screen_id=None)` | `PUT /api/v1/screen/mode` with `screenID`, `workingMode` | `WorkingMode.SEND_ONLY` = 0, `ALL_IN_ONE` = 1. |
| `apply_preset(sequence_number, screen_id=None)` | `POST /api/v1/preset/current/update` with `screenID`, `sequenceNumber` | Existing slot, numbered from 1; application needs hardware verification. |
| `select_input(source, screen_id=None)` | `PUT /api/v1/screen/layer/input` with `screenID`, `layers: [{id, source}]` | Exact source name or group ID; main layer = lowest ID in the active mode. |
| `switch_layer_source(screen_id, layers)` | Same layer endpoint | Explicit layer list for advanced callers. |

Omitting a screen for working mode, preset or input selects the **first reported
screen**. Omitting screen IDs for brightness, color temperature or gamma resolves
all configured screens. Home Assistant always supplies the entity's screen ID.

The current input is read from `layersInWorkingMode` for the current mode, not
inferred from the last command. If no layer is reported, the client uses layer 0
for routing; support for that fallback depends on the controller.

## Brightness units

`brightness_scale="auto"` assumes a ratio until a read of display parameters
reveals the unit: a value above 1 indicates percent firmware, while a value between
0 and 1 indicates ratio firmware. Exactly 0 or 1 is ambiguous, so the last known
scale is retained (ratio on a fresh client). Call `get_status()` or
`get_display_params()` before writes when using the standalone client. Home
Assistant does this during setup and exposes the scale as the brightness entity's
`wire_scale` attribute.

For firmware known to use a different unit, standalone callers can force
`brightness_scale="percent"` or `"ratio"`; the CLI has `--brightness-scale`.
The HA UI does not currently expose that override. Percent-firmware brightness
below 1 is inherently ambiguous; report the model and sanitized readings before
using it for unattended brightness automation.

The tested MX40 Pro acknowledged brightness changes while cabinets were off but
did not apply them. A success response is not evidence of changed output.

## Additional client-only controls

The library also exposes per-input HDR mode (`set_hdr_mode`), controller identify,
LCD beacon, controller naming and the legacy device working-mode endpoint. These
have no corresponding HA entities. `set_cabinet_mapping()` resolves all cabinets
unless explicit cabinet IDs are provided; the HA mapping control affects the
whole controller. Mapping is a servicing aid, not a power control.

Reboot, soft standby, EDID, calibration, output-gamut configuration and power-relay
sequencing are outside this integration. They are deliberately not included in
installation examples. A normal display state cannot establish that a source is
rendering frames or that downstream cabinets are powered.

## CLI

```bash
uv run coex --host 192.0.2.10 status
uv run coex --host 192.0.2.10 brightness 30
uv run coex --host 192.0.2.10 blackout --screen '<screen ID>'
uv run coex --host 192.0.2.10 normal --screen '<screen ID>'
uv run coex --host 192.0.2.10 mode all-in-one --screen '<screen ID>'
uv run coex --host 192.0.2.10 input 'HDMI2.0 1' --screen '<screen ID>'
```

Replace the documentation address and IDs with those reported by your controller.
Run `coex --help` for all commands. Writes change the physical display immediately.
CLI failures print an error to stderr and return exit code 2.
