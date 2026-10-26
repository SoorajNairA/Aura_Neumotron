# ESP32 Temperature-Controlled Fan: Firmware and Behavioral Simulation

**Date:** 2026-10-27 · **Status:** approved design, awaiting spec review · **Branch:** `AURA-nemotron_test1`
**Deadline context:** Nebius hackathon submission 2026-10-30 17:00 UTC. This is the "fan slice" of the larger IoT goal (Design / Code / Simulation / Build spaces, digital twin, diagnostics). Everything outside the slice is listed under *Out of scope*.

## 1. Goal

For the objective "Design a temperature-controlled desk fan", AURA produces, from the authoritative Engineering Graph:

1. a design whose controller ports carry real ESP32 GPIO assignments;
2. an Arduino sketch generated from those assignments, bound to the graph revision it came from;
3. an honest compile result from `arduino-cli` (or an explicit "toolchain not installed");
4. a behavioral simulation of the control rule with an adjustable temperature, visibly linked to the 3D fan.

No hardware exists yet. Nothing in this slice may claim upload, telemetry, electrical verification or hardware validation.

## 2. Agreed decisions

| Decision | Choice | Reason |
|---|---|---|
| Firmware source | Deterministic template filled from the graph (approach 1) | Compiles reliably; pins cannot drift from the graph. Nemotron-generated firmware rejected for this deadline (compile risk, pin drift). |
| Simulation | Same control rule evaluated in the browser, labeled behavioral | Instant slider response; no emulator dependency. Wokwi/QEMU emulation rejected for now. |
| Temperature sensor | DS18B20 (1-Wire) | One data line matches the existing single `signal` interface. Replaces the BME280 pick, which is I2C and was wired as one line (existing model inconsistency). |
| Control law | On/off with hysteresis | On at the graph threshold `threshold_c` (default 26 °C), off at `threshold_c − 2` (24 °C). PWM speed control deferred. |

## 3. Reference parts (assumptions until confirmed by the user)

| Role | Part | Notes |
|---|---|---|
| Controller | ESP32 DevKit V1 (ESP32-WROOM-32) | FQBN `esp32:esp32:esp32` |
| Temperature sensor | DS18B20 (TO-92 or waterproof probe) | 3.0–5.5 V supply; needs a 4.7 kΩ pull-up from DQ to 3.3 V. Datasheet facts to be cited with retrieval date at implementation (Analog Devices DS18B20 datasheet). |
| Pull-up | 4.7 kΩ resistor | New graph component, connected DQ ↔ 3.3 V |
| Fan | 5 V DC brushless fan, ≈0.2 A (curated `dc-fan-5v` keeps its existing 0.5 A budget) | |
| Switch | Logic-level N-MOSFET module (curated `logic-mosfet-module`) | Gate driven at 3.3 V; must be specified for 3.3 V gate drive |
| Protection | 1N4007 flyback diode across the fan | Already produced by the planner |
| Supply | USB 5 V | |

Values not sourced from a cited datasheet are labeled estimates in the UI and in generated code comments.

## 4. Design

### 4.1 Pin assignment in the graph (planner)

- When the controller resolves to `esp32-devkit-v1`, the planner records a GPIO number on each controller interface it connects, e.g. `metadata.gpio` on the connection or an interface→GPIO map on the controller parameters (`gpio_map`). The implementation plan picks one after reading `serialization.py`; the graph remains the only source of pin truth.
- Fixed assignment for this slice: temperature sensor data → **GPIO4**; MOSFET gate → **GPIO16**. Both are general-purpose, non-strapping, input/output-capable pins on WROOM-32.
- A deterministic check rejects a GPIO used twice or a pin outside an allow-list (no strapping pins 0/2/12/15, no flash pins 6–11, no input-only pins 34–39 for outputs).
- Catalogue: add `ds18b20` (`temperature_sensor`) with its evidence record; map planner `temperature-sensor` to it; add the 4.7 kΩ pull-up component and its connection. Existing BME280 `environmental_sensor` entries stay.

### 4.2 Firmware module — `src/aura/firmware/`

- `generate_sketch(graph) -> FirmwareArtifact` reads controller, sensor and driver components plus their GPIO assignments and `threshold_c`, and fills one fixed template.
- The sketch: reads the DS18B20 via `OneWire` + `DallasTemperature`; applies hysteresis (on ≥ T_on, off ≤ T_off); drives the MOSFET gate pin; prints one JSON line per second over Serial at 115200 baud: `{"t_c":..,"fan":0|1,"rev":"<revision id>"}`; treats a sensor read error (`DEVICE_DISCONNECTED_C`) as fault → fan on (fail-safe for a cooling fan) and reports `"fault":"sensor"`.
- `FirmwareArtifact` holds source text, revision id, board FQBN, library list with pinned versions, and the pin table. Stored through the existing artifact store against the project revision; a newer revision marks it stale (same freshness rule as other representations).
- Unsupported graphs (no ESP32, no temperature sensor, no switched fan) return a clear `FIRMWARE_UNSUPPORTED` reason instead of a partial sketch.

### 4.3 Compile endpoint

- `POST /api/projects/{project_id}/firmware/compile` → generates (or reuses the fresh) sketch, runs `arduino-cli compile --fqbn esp32:esp32:esp32` in a temporary sketch folder with a timeout, returns `{status: "passed"|"failed"|"toolchain_missing", errors: [{file,line,message}], sizeBytes, revisionId, compiledAt}`.
- `GET /api/projects/{project_id}/firmware` returns source, pin table, freshness and the last compile result.
- `arduino-cli` is located via `AURA_ARDUINO_CLI` or `PATH`. Missing CLI, missing ESP32 core or missing libraries are reported as `toolchain_missing` with the exact missing item; never as a pass.
- Compiler output is parsed into file/line/message; raw output is kept in the artifact for the developer panel.

### 4.4 Simulation view (frontend)

- New workspace tab **Simulation** (`ViewMode` gains `"simulation"`).
- Inputs: temperature slider (10–40 °C) and a "sensor disconnected" fault toggle.
- Outputs: fan state, which threshold applies, an event log with timestamps, and the 3D fan spinning only while the simulated output is on.
- The rule is a pure function `fanControl(prevOn, tempC | null, tOn, tOff) -> {on, reason}` mirrored from the firmware template; thresholds come from the same graph values the firmware uses.
- Permanent label: **"Behavioral simulation — control logic only. Not electrical verification, not firmware execution."** The 3D spin is labeled an animation.

### 4.5 Nemotron's role

Nemotron explains the generated sketch and answers questions about it in the existing narration/inspector style. It does not author or edit firmware in this slice.

## 5. Error handling

| Case | Behavior |
|---|---|
| Graph lacks a supported fan topology | `FIRMWARE_UNSUPPORTED` with reasons; Simulation tab disabled with the same reasons |
| GPIO conflict / disallowed pin | Verification failure on the design; no sketch generated |
| arduino-cli / core / library missing | `toolchain_missing` naming the missing item and the install command |
| Compile error | `failed` with parsed errors; artifact still saved for inspection |
| Compile timeout (default 180 s) | `failed` with a timeout reason |
| Design changed after generation | Firmware marked stale; compile regenerates first |

## 6. Testing

| Level | Test |
|---|---|
| Unit | ESP32 pin assignment and allow-list check; DS18B20 + pull-up planned for the fan objective; sketch contains graph GPIOs and thresholds; unsupported graph → `FIRMWARE_UNSUPPORTED`; hysteresis truth table (rising, falling, inside band, sensor fault) for Python and TS mirrors with the same table |
| API | `/firmware` and `/firmware/compile` with a stub runner; real compile test runs only when `arduino-cli` and the ESP32 core are present, otherwise **skipped with reason** |
| Browser (Playwright) | Simulation tab: move slider across 26 °C → fan on; back below 24 °C → off; fault toggle → fan on with fault label; behavioral label visible |
| Regression | Full Python suite, frontend unit tests, existing browser suite |

Results are reported as software-tested or simulated only. No hardware validation is claimed.

## 7. Out of scope (this slice)

Upload, serial monitor, live telemetry, digital twin, fault diagnosis, PWM speed control, Nemotron-authored firmware, model/provider configuration UI, network connectivity, retry of `build_incomplete` projects, the "plant watering" classification defect.

## 8. Open items for the implementation plan

- Choose the GPIO storage shape (`gpio_map` on the controller vs. connection metadata) after reading graph serialization and representation code.
- Confirm `arduino-cli` installation path on this machine and pin ESP32 core and library versions.
- Confirm DS18B20 datasheet values and record source + retrieval date in the catalogue evidence.
