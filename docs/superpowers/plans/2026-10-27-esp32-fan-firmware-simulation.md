# ESP32 Fan Firmware and Behavioral Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For "Design a temperature-controlled desk fan", AURA plans a DS18B20 + ESP32 design with real GPIOs, generates an Arduino sketch from the graph, compiles it honestly with `arduino-cli`, and offers a labeled behavioral simulation with a temperature slider and a spinning 3D fan.

**Architecture:** The planner records a `gpio_map` on the ESP32 controller and wires the DS18B20 to the controller's new 3.3 V output with a 4.7 kΩ pull-up. A new `aura.firmware` package renders a fixed sketch template from the current graph revision and runs `arduino-cli` in a temp folder. The frontend gains a Simulation tab driven by a pure `fanControl` function mirroring the sketch's rule.

**Tech Stack:** Python 3.11 / FastAPI / pytest; React 18 + TypeScript + Three.js / vitest / Playwright; `arduino-cli` with the `esp32:esp32` core, `OneWire`, `DallasTemperature`.

**Spec:** `docs/superpowers/specs/2026-10-27-esp32-fan-firmware-simulation-design.md`

## Global Constraints

- Hysteresis: on at `T_on = threshold_c` (default 26 °C), off at `T_off = threshold_c − 2` (default 24 °C); between them keep the previous state.
- Sensor read failure (`DEVICE_DISCONNECTED_C` in firmware, `null` in simulation) → fan **on**, reported as `"fault":"sensor"`.
- Pins: DS18B20 data → GPIO4; MOSFET gate → GPIO16. Allowed output GPIOs: 4, 5, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33. Forbidden: 0, 2, 12, 15 (strapping), 6–11 (flash), 34–39 (input-only, never outputs).
- Board FQBN `esp32:esp32:esp32`; serial 115200 baud; one JSON line per second: `{"t_c":<float|null>,"fan":0|1,"rev":"<revisionId>"}` plus `"fault":"sensor"` when applicable.
- Compile statuses are exactly `passed` | `failed` | `toolchain_missing`; default timeout 180 s; CLI found via `AURA_ARDUINO_CLI` env var, else `PATH`.
- Simulation label, verbatim: **"Behavioral simulation — control logic only. Not electrical verification, not firmware execution."**
- No upload, serial, telemetry or hardware-validation claim anywhere in this slice.
- Branch `AURA-nemotron_test1`; run GitNexus `impact` before editing any existing function and `detect-changes` before every commit (CLAUDE.md).

## Deviations from the spec (approved by the user at plan review)

- Firmware is generated **on demand from the current revision** instead of being stored in the artifact store. It always matches the current revision, so it can't go stale. The last compile result is cached in memory per `(projectId, revisionId)`.
- The hysteresis truth table is tested in TypeScript (simulation) and against the C++ rule through a host `g++` harness, skipped with a reason when `g++` is absent. There is no Python mirror of the rule.
- Spec §4.5 (Nemotron explains the sketch) is deferred until after Task 8, done only if time remains before the deadline.

## Review Focus

1. **Threshold from the objective** ("…turns on above 30 degrees") must flow to the sketch and the simulation as 30/28, not 26/24. Test in Task 4 and Task 7.
2. **Non-ESP32 or non-fan projects** (Arduino Nano fan, robotic arm) must return `FIRMWARE_UNSUPPORTED` and disable the Simulation tab, never crash or emit a partial sketch. Test in Task 4 and Task 7.
3. **Exact boundary temperatures** 24.0 and 26.0 must follow the inclusive rule (≥ T_on on, ≤ T_off off). Test in Task 6.
4. **A slow or hung compile** must not block other API requests. It runs in the threadpool and is killed at the timeout. Test in Task 5.
5. **A design edited after compile** (new revision) must show the old compile result as not applying to the current revision. Test in Task 5.

---

### Task 1: DS18B20 and pull-up in the catalogue

**Files:**
- Modify: `src/aura/verification/catalogue.py` (`_SOURCES`, `_SPECS`)
- Test: `tests/test_fan_firmware_slice.py` (new; all Python tests for this plan live here)

**Interfaces:**
- Produces: catalogue ids `ds18b20-module` (family `temperature_sensor`) and `resistor-4k7` (family `resistor`); evidence id `evidence-analog-ds18b20`.

- [ ] **Step 1: Retrieve the DS18B20 datasheet facts.** Use WebFetch on the Analog Devices DS18B20 product page or datasheet. Record supply range (expected 3.0–5.5 V), accuracy (±0.5 °C, −10 to +85 °C), the source URL and the retrieval date. If the fetch fails, use `"assumption"` as the source key and label the values estimates.
- [ ] **Step 2: Write the failing test**

```python
def test_catalogue_has_ds18b20_with_dated_evidence_and_4k7_resistor():
    from aura.verification import catalogue
    sensor = catalogue.get("ds18b20-module")
    assert sensor.family == "temperature_sensor"
    assert catalogue.get("resistor-4k7").family == "resistor"
    record = next(r for r in catalogue.evidence_records() if r.id == "evidence-analog-ds18b20")
    assert record.url and record.retrieved  # source URL and retrieval date recorded
```

(Adjust the attribute names `id`/`url`/`retrieved` to the existing `EvidenceRecord` fields.)
- [ ] **Step 3: Run it.** `.venv/Scripts/python.exe -m pytest tests/test_fan_firmware_slice.py -q`. Expected: FAIL, `Unknown curated component: ds18b20-module`.
- [ ] **Step 4: Add the `_SOURCES` evidence record and two `_SPECS` rows** following the existing tuple format: `("ds18b20-module","temperature_sensor","Analog Devices","DS18B20","analog-ds18b20",(3.0,5.5),1.5,(15,10,5))` and a 4.7 kΩ resistor row next to `resistor-10k`.
- [ ] **Step 5: Run it.** Expected: PASS.
- [ ] **Step 6: Commit.** Message: `Add DS18B20 and 4.7 kΩ pull-up to the curated catalogue`.

### Task 2: ESP32 3.3 V output, DS18B20 power and pull-up in the planner

**Files:**
- Modify: `src/aura/engineering_graph/interfaces.py:23` (`microcontroller_board` interfaces)
- Modify: `src/aura/planner/service.py`: the `specs` dict (~line 171), `curated` map (~line 231), `connect()` and the sensor/resistor wiring (~lines 356–420)
- Test: `tests/test_fan_firmware_slice.py`

**Interfaces:**
- Consumes: Task 1 catalogue ids.
- Produces: controller interface `logic-power-out` (3.3 V output); for fan objectives a `resistor` component with `parameters.resistance_ohm == 4700` and `parameters.functional_roles == ["pull_up"]`; temperature sensor `component_definition_id == "ds18b20-module"`.

- [ ] **Step 1: Run impact.** `node .gitnexus/run.cjs impact "component_interfaces" --direction upstream --repo .` and the same for `PlannerService`. Report the risk; confirm any `UNKNOWN` with grep.
- [ ] **Step 2: Write the failing test**

```python
def test_fan_plan_powers_ds18b20_from_3v3_with_pullup():
    plan = _fan_plan()  # PlannerService().plan(ProjectRequest("Fan","Design a temperature-controlled desk fan",("Cool",),components=("microcontroller_board","temperature_sensor","fan","mosfet_driver","low_voltage_power_source")))
    by_role = {c.role: c for c in plan.components}
    sensor, controller = by_role["temperature_sensor"], by_role["microcontroller_board"]
    assert sensor.parameters["component_definition_id"] == "ds18b20-module"  # use the planner's existing key for curated ids
    pullups = [c for c in plan.components if c.role == "resistor" and "pull_up" in c.parameters["functional_roles"]]
    assert len(pullups) == 1 and pullups[0].parameters["resistance_ohm"] == 4700
    edges = {(x.source_id, x.source_interface, x.target_id, x.target_interface) for x in plan.connections}
    assert (controller.id, "logic-power-out", sensor.id, "power") in edges
    assert (sensor.id, "signal", pullups[0].id, "terminal-a") in edges
    assert (pullups[0].id, "terminal-b", controller.id, "logic-power-out") in edges
    assert not any(x.target_id == sensor.id and x.target_interface == "power" and x.source_id != controller.id for x in plan.connections)
    assert VerificationService().verify(plan).accepted
```

- [ ] **Step 3: Run it.** Expected: FAIL on the curated id.
- [ ] **Step 4: Implement.**
  - Add `("logic-power-out","electrical_power_out")` to the `microcontroller_board` interfaces, using the existing power-output kind name if one exists.
  - Map `temperature-sensor` to `ds18b20-module` in `curated`.
  - Add a `pull-up` spec (`"Data-line pull-up"`, role `resistor`, `resistance_ohm: 4700`, `functional_roles:["pull_up"]`) included once per temperature sensor when the controller has `logic_voltage_v == 3.3`.
  - In `connect()`, add kinds `logic-power` → `("logic-power-out","power")` and `pull-up` → `("terminal-b","logic-power-out")`.
  - Skip the generic 5 V `power` edge for that sensor.
- [ ] **Step 5: Run the new test and the regression set.** `pytest tests/test_fan_firmware_slice.py tests/test_bounded_planner_repair.py tests/test_workspace_server.py -q`. Expected: all pass. Then run the full suite: `pytest -q -p no:cacheprovider --ignore=tests/test_runtime_optimizations.py --ignore=tests/test_xtts_backend.py`. Expected: only the known `test_startup_boundaries` failure.
- [ ] **Step 6: Commit.** Message: `Power DS18B20 from ESP32 3.3 V with a 4.7 kΩ pull-up`.

### Task 3: GPIO map and pin check

**Files:**
- Modify: `src/aura/planner/service.py` (after connections are built)
- Modify: `src/aura/verification/service.py` (new check `ELEC_GPIO`)
- Test: `tests/test_fan_firmware_slice.py`

**Interfaces:**
- Produces: `controller.parameters["gpio_map"]: dict[str, int]`, keyed by controller interface name (e.g. `{"signal-1": 4, "signal-2": 16}`), present only for `esp32-devkit-v1`. Verification check id `ELEC_GPIO` (critical, FAILED) for duplicate GPIOs, forbidden GPIOs, or an input-only GPIO on a `control` connection.

- [ ] **Step 1: Run impact** on `VerificationService.verify`.
- [ ] **Step 2: Write the failing tests**

```python
def test_fan_plan_assigns_gpio4_sensor_and_gpio16_gate():
    plan = _fan_plan(); controller = _role(plan, "microcontroller_board")
    gpio = controller.parameters["gpio_map"]
    sensor_if = _controller_interface_to(plan, "temperature_sensor")  # controller-side interface on the sensor edge
    driver_if = _controller_interface_to(plan, "mosfet_driver")
    assert gpio[sensor_if] == 4 and gpio[driver_if] == 16

def test_gpio_check_rejects_duplicate_and_strapping_pins():
    for bad in ({"signal-1": 4, "signal-2": 4}, {"signal-1": 4, "signal-2": 0}, {"signal-1": 4, "signal-2": 34}):
        result = VerificationService().verify(_with_gpio_map(_fan_plan(), bad))
        assert any(f.check == "ELEC_GPIO" and f.state.value == "failed" for f in result.findings)
```

- [ ] **Step 3: Run it.** Expected: FAIL with `KeyError: 'gpio_map'`.
- [ ] **Step 4: Implement the assignment.** Temperature sensor → 4, MOSFET driver → 16. Every other controller-connected component gets the next unused pin from the allowed list, in connection order. Implement the check against the Global Constraints lists.
- [ ] **Step 5: Run the tests, then the full suite.** Expected: pass, except the known `test_startup_boundaries` failure.
- [ ] **Step 6: Commit.** Message: `Record ESP32 GPIO assignments and verify pin safety`.

### Task 4: Sketch generator — `aura.firmware`

**Files:**
- Create: `src/aura/firmware/__init__.py`, `src/aura/firmware/sketch.py`, `src/aura/firmware/fan_sketch.ino.tmpl`
- Modify: `pyproject.toml` `[tool.setuptools.package-data]` (ship `*.tmpl`)
- Test: `tests/test_fan_firmware_slice.py`

**Interfaces:**
- Consumes: `gpio_map` (Task 3), `threshold_c` on the temperature sensor.
- Produces:

```python
@dataclass(frozen=True)
class FirmwareArtifact:
    source: str; revision_id: str; fqbn: str           # "esp32:esp32:esp32"
    libraries: tuple[str, ...]                          # ("OneWire@2.3.8", "DallasTemperature@3.9.0"); confirm the latest versions at execution
    pins: dict[str, int]                                # {"temperature_data": 4, "fan_gate": 16}
    t_on_c: float; t_off_c: float
class FirmwareUnsupported(ValueError): reasons: tuple[str, ...]
def generate_fan_sketch(graph: EngineeringGraph) -> FirmwareArtifact
```

- [ ] **Step 1: Write the failing tests:**
  - `test_sketch_uses_graph_pins_thresholds_and_revision`: source contains `ONE_WIRE_PIN 4`, `FAN_PIN 16`, `T_ON_C 26.0`, `T_OFF_C 24.0` and the revision id; `pins == {"temperature_data": 4, "fan_gate": 16}`.
  - `test_sketch_threshold_follows_objective`: objective "Design a desk fan that turns on above 30 degrees" gives `T_ON_C 30.0`, `T_OFF_C 28.0`.
  - `test_unsupported_graphs_raise_firmware_unsupported`: a robotic-arm graph and an "Arduino Nano desk fan" graph each raise `FirmwareUnsupported` with non-empty `reasons`.
  - `test_cpp_rule_matches_truth_table`: skips with a reason if `shutil.which("g++")` is None. Otherwise it compiles `tests/fixtures/fan_rule_harness.cpp`, which `#include`s the rule function extracted from the template, and runs it over `tests/fixtures/fan_hysteresis_cases.json`.
- [ ] **Step 2: Run them.** Expected: FAIL, `ModuleNotFoundError: aura.firmware`.
- [ ] **Step 3: Write the template.** It holds the rule as a standalone function `bool fanControl(bool prevOn, float tC, bool valid, float tOn, float tOff)`, plus `setup()` (Serial 115200, sensor begin, gate pin OUTPUT LOW) and a `loop()` that emits the JSON line every 1000 ms. Generated-code comments label the reference parts as assumptions. `generate_fan_sketch` fills `{{ONE_WIRE_PIN}}`, `{{FAN_PIN}}`, `{{T_ON_C}}`, `{{T_OFF_C}}` and `{{REVISION_ID}}` with `str.replace`. No templating dependency.
- [ ] **Step 4: Create `tests/fixtures/fan_hysteresis_cases.json`** with rows `[prevOn, tempC|null, expectOn]` for tOn=26, tOff=24: `[false,25,false]`, `[false,26,true]`, `[true,25,true]`, `[true,24,false]`, `[true,23.9,false]`, `[false,null,true]`, `[true,null,true]`, `[false,40,true]`, `[true,10,false]`.
- [ ] **Step 5: Run the tests.** Expected: PASS, with the g++ test passed or skipped and its reason shown.
- [ ] **Step 6: Commit.** Message: `Generate ESP32 fan sketch from the Engineering Graph`.

### Task 5: Compile runner and API

**Files:**
- Create: `src/aura/firmware/compile.py`
- Modify: `src/aura/workspace/server.py` (routes next to `/work`, ~line 975)
- Test: `tests/test_fan_firmware_slice.py`

**Interfaces:**
- Consumes: `generate_fan_sketch`, `FirmwareArtifact`, `FirmwareUnsupported`.
- Produces:

```python
@dataclass(frozen=True)
class CompileResult:
    status: str                      # "passed" | "failed" | "toolchain_missing"
    errors: tuple[dict, ...]         # {"file": str, "line": int|None, "message": str}
    size_bytes: int | None; revision_id: str; compiled_at: str; raw_output: str; missing: str | None
def compile_sketch(artifact: FirmwareArtifact, *, cli: str | None = None, timeout_s: float = 180.0,
                   run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> CompileResult
```

- `GET /api/projects/{project_id}/firmware` → `{supported, reasons, source, pins, fqbn, libraries, tOnC, tOffC, revisionId, lastCompile: CompileResult|null, lastCompileCurrent: bool}`.
- `POST /api/projects/{project_id}/firmware/compile` → `CompileResult` as camelCase JSON. Returns 422 `{"code":"FIRMWARE_UNSUPPORTED","reasons":[…]}` for unsupported graphs. Runs via `run_in_threadpool`.

- [ ] **Step 1: Run impact** on `create_app`.
- [ ] **Step 2: Write the failing tests:**
  - `test_compile_reports_toolchain_missing_without_cli`: `cli=None` and no CLI on PATH (monkeypatch `shutil.which` to return None) → `status == "toolchain_missing"`, `missing == "arduino-cli"`.
  - `test_compile_parses_errors_from_stub_runner`: the stub returns code 1 with stderr `sketch.ino:12:5: error: 'x' was not declared` → `failed`, `errors[0] == {"file":"sketch.ino","line":12,"message":"'x' was not declared"}`.
  - `test_compile_timeout_is_failed_not_hang`: the stub raises `subprocess.TimeoutExpired` → `failed` with "timed out" in the message.
  - `test_missing_core_is_toolchain_missing`: stub stderr contains `platform not installed` → `toolchain_missing`, `missing == "esp32:esp32 core"`.
  - `test_firmware_api_lifecycle`: memory app, deterministic fan project. GET gives `supported` true with pins 4/16. POST with a monkeypatched stub runner gives `passed`. A modification that creates a new revision makes GET return `lastCompileCurrent` false.
  - `test_firmware_api_unsupported_for_arm`: POST returns 422 `FIRMWARE_UNSUPPORTED`.
  - `test_real_compile_when_toolchain_present`: skips with a reason unless `arduino-cli` and the `esp32:esp32` core are installed. Otherwise the generated sketch compiles with `passed`.
- [ ] **Step 3: Run them.** Expected: FAIL (module or route missing).
- [ ] **Step 4: Implement `compile_sketch`.** Write the sketch to `<tmp>/aura_fan/aura_fan.ino`. Run `[cli, "compile", "--fqbn", fqbn, "--warnings", "default", dir]`. Parse errors with `^(?P<file>[^:\n]+):(?P<line>\d+):(?:\d+:)? error: (?P<message>.+)$`. Read the size from the `Sketch uses (\d+) bytes` line. Cache results in a module-level dict keyed by `(project_id, revision_id)` inside the server.
- [ ] **Step 5: Run the tests, then the full suite.** Expected: pass, with the real compile test passed or skipped and its reason shown.
- [ ] **Step 6: Commit.** Message: `Add firmware and compile endpoints with honest toolchain status`.

### Task 6: `fanControl` simulation rule (TypeScript)

**Files:**
- Create: `src/aura/workspace/web/frontend/src/fanControl.ts`, `src/aura/workspace/web/frontend/src/fanControl.test.ts`

**Interfaces:**
- Produces: `export function fanControl(prevOn: boolean, tempC: number | null, tOn: number, tOff: number): {on: boolean; reason: "above_on" | "below_off" | "in_band" | "sensor_fault"}`

- [ ] **Step 1: Write the failing test.** It loads `../../../../../../tests/fixtures/fan_hysteresis_cases.json` (or copies the same 9 rows verbatim if vitest can't import outside the root) and asserts `fanControl(prev, t, 26, 24).on === expect` for every row. It also checks `reason` for 26 → `above_on`, 24 → `below_off`, 25 with prev true → `in_band`, null → `sensor_fault`.
- [ ] **Step 2: Run it.** `npm test` in the frontend folder. Expected: FAIL, module missing.
- [ ] **Step 3: Implement.** The rule is the same as the Global Constraints: null → on/sensor_fault; ≥ tOn → on; ≤ tOff → off; else keep prev/in_band.
- [ ] **Step 4: Run it.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `Add behavioral fan control rule for simulation`.

### Task 7: Simulation tab and spinning fan

**Files:**
- Modify: `src/aura/workspace/web/frontend/src/WorkspaceApp.tsx`:
  - `ViewMode` type (line ~18);
  - the tabs array (`["assembly","schematic","split","work"]`);
  - the `HolographicScene` class (line 63): new method `setSpinning(semanticId: string, on: boolean): void`, which runs its own `requestAnimationFrame` loop that rotates the fan group about its axis and calls `this.render()`, and stops when off;
  - a new `SimulationPanel` rendered when `mode === "simulation"`.
- Modify: `src/aura/workspace/web/frontend/src/styles.css` (panel styles reuse the existing tokens)
- Create: `src/aura/workspace/web/frontend/e2e/simulation.spec.ts`

**Interfaces:**
- Consumes: `GET /api/projects/{id}/firmware` (Task 5), `fanControl` (Task 6).
- Produces: test ids `simulation-panel`, `sim-temperature` (input range 10–40, step 0.5), `sim-fault` (checkbox), `sim-fan-state` (text `ON`/`OFF`), `sim-label` (the verbatim label), `sim-log`; `window.__auraFanSpinning(): boolean` for e2e.

- [ ] **Step 1: Write the failing e2e test.** Use the mocked-route style of `e2e/production.spec.ts`; mock `/firmware` with `{supported:true,tOnC:26,tOffC:24,pins:{temperature_data:4,fan_gate:16},…}`. Steps:
  - Open the project and click `SIMULATION`.
  - Expect `sim-label` to have the exact label text.
  - Set the slider to 26 → `sim-fan-state` reads `ON` and `__auraFanSpinning()` is true.
  - Set it to 25 → still `ON`. Set it to 24 → `OFF` and spinning is false.
  - Check `sim-fault` → `ON`, with the log containing `sensor fault`.
  - Second test: mock `/firmware` with `{supported:false,reasons:["No ESP32 controller"]}`. The SIMULATION tab is disabled and the reason is visible.
  - Third test: mock `tOnC:30,tOffC:28`; 29 from OFF → `OFF`, 30 → `ON`.
- [ ] **Step 2: Run it.** `npm run test:browser -- e2e/simulation.spec.ts`. Expected: FAIL, no SIMULATION tab.
- [ ] **Step 3: Implement the tab, panel, log** (the latest 50 events with local timestamps) **and `setSpinning`.** The 3D spin label reads "Animation". The panel also shows the pin table and thresholds from `/firmware`.
- [ ] **Step 4: Run the e2e test and `npm test`.** Then `npm run build`. Expected: pass and build OK.
- [ ] **Step 5: Run the existing browser suite.** `npm run test:browser`. Expected: no new failures compared with before. The known What-If Discard failure may remain; report it.
- [ ] **Step 6: Commit,** including the rebuilt `representation/` bundle. Message: `Add behavioral Simulation tab with spinning fan`.

### Task 8: Toolchain, live run and handoff

**Files:**
- Modify: `docs/active/README.md` (slice status, commands and results)
- Modify: `README.md` (one "Firmware toolchain" subsection: install commands and `AURA_ARDUINO_CLI`)

- [ ] **Step 1: Get user approval, then install the toolchain** (machine setup, not a product dependency): `winget install ArduinoSA.CLI`; `arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json`; `arduino-cli core install esp32:esp32 --additional-urls <same>`; `arduino-cli lib install OneWire DallasTemperature`. Record the installed versions and pin them in `FirmwareArtifact.libraries`.
- [ ] **Step 2: Rerun `test_real_compile_when_toolchain_present`.** Expected: PASS with the size reported.
- [ ] **Step 3: Live end-to-end.**
  - Restart the backend and create "Design a temperature-controlled desk fan" with Nebius live planning.
  - Open Simulation, compile and screenshot.
  - Record the planning mode, the compile status and size, and the simulation behavior.
- [ ] **Step 4: Run the full verification.**
  - Python suite with the two known ignores.
  - `npm test`, `npm run build`, `npm run test:browser`.
  - `git diff --check` and GitNexus `detect-changes`.
  - Report each command and its result, separating software-tested, simulated and not-done (hardware).
- [ ] **Step 5: Commit the docs.** Message: `Document fan firmware slice status and toolchain`.
