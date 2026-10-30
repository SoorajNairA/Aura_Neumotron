# Component Library and Manual Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A categorized IoT library whose catalogue owns every pin, auto-wiring on add, and manual connect/reconnect/disconnect/replace/rename/configure/delete as verified, undoable revisions.

**Architecture:** Pin templates and categories live in Python (`aura.verification.pins`, read by `catalogue.py`). Added parts carry a pin snapshot in entity metadata. Every edit is a deterministic `ModificationProposal` committed through the existing `/modification-proposals/{id}/commit` route. New edits store a before-image for one generic undo. New electrical checks extend `graph_rules.evaluate_graph`. The frontend reads pin labels from the graph and stops keeping its own map.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest; React/TypeScript, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-30-component-library-editing-design.md`

## Global Constraints

- Controller support: only `esp32-devkit-v1` is a full controller. Other boards get `support: "listed"` and are refused as controller with code `BOARD_LISTED_ONLY` and the text "Board listed — wiring and firmware not supported yet".
- Categories, exactly: `boards`, `sensors`, `actuators`, `displays`, `communication`, `power`, `breadboards`, `basic`.
- Pin roles, exactly: `power_in`, `power_out`, `ground`, `digital_in`, `digital_out`, `analog_out`, `pwm_in`, `i2c_sda`, `i2c_scl`, `spi_sck`, `spi_mosi`, `spi_miso`, `spi_cs`, `uart_tx`, `uart_rx`, `passive`.
- A new catalogue part needs a manufacturer datasheet or product page in `_SOURCES`. If its URL cannot be confirmed, skip the part and name it in the commit message.
- No edit writes the graph directly. All edits go propose → verify → commit, and stale bases return `409 stale_revision`.
- Shared CRITICAL-risk symbols (GitNexus impact, 2026-10-30): `ComponentDefinition` (266 impacted), `inverse_proposal` (197), `materialize_electrical_nets` (196), `component_interfaces` (54). Changes to them are additive only: new fields with defaults, interfaces appended after existing ones, one new branch in `inverse_proposal`. `materialize_electrical_nets` is not modified.
- Run `node .gitnexus/run.cjs impact "<symbol>" --direction upstream --repo .` before editing any existing function. Run `node .gitnexus/run.cjs detect-changes --scope all --repo .` before each commit.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- UI copy keeps the existing honesty wording: checks are "rule checks, not simulation". Parts without a 3D model stay "Generic proxy".
- **Deviation from spec §2, recorded:** UART does not take fixed GPIO16/17, because the fan and plant demos already use GPIO16. UART RX/TX use two allocator pins (the ESP32 GPIO matrix routes UART2 to any pin). Only one UART part per project.

## Review Focus

1. **Existing projects after migration.** Fan and plant demos must keep their exact wires, GPIOs and passing verification. A new logic-level or power rule that fails them is a bug in the rule, not in the demo (Task 3 migration test).
2. **I²C part powered from 5 V.** LCD1602 with PCF8574 runs at 5 V, which pulls SDA/SCL to 5 V. Adding it must fail with `ELEC_LOGIC_LEVEL` and a level-shifter hint, never pass silently (Task 6).
3. **Bus pins already taken.** If GPIO21/22 or 18/19/23 are held by a digital part, adding an I²C or SPI part must fail with `BUS_PINS_IN_USE` naming the holder, not double-assign (Task 3).
4. **Undo after delete and replace.** Undo must restore the part, its wires, its `gpio_map` entries and its name exactly. Graph equality round-trip (Task 4, used by Tasks 5, 7, 8).
5. **Old projects and ZIPs without pin snapshots.** They still render pin labels and accept edits. The server fills pins from the family template, so the client never guesses (Task 2).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/aura/verification/pins.py` (new) | `PinDefinition`, `FAMILY_PINS`, `CATEGORY_BY_FAMILY`, `PART_PIN_OVERRIDES`, `PART_SETTINGS`, `pins_for_definition()`, dump CLI |
| `src/aura/verification/catalogue.py` | New fields on `ComponentDefinition`, 15 new parts, new `_SOURCES`, `support` |
| `src/aura/engineering_graph/interfaces.py` | Append ESP32 bus/rail/extra signal ports; interfaces for new families; bus-last allocator order |
| `src/aura/workspace/autowire.py` (new) | `autowire()` – deterministic wires for one added part |
| `src/aura/workspace/edits.py` (new) | Snapshot proposals and all new edit operations |
| `src/aura/workspace/modifications.py` | `propose_add_components` uses `autowire` and adds a pin snapshot; `inverse_proposal` gains the snapshot branch |
| `src/aura/verification/graph_rules.py` | New electrical checks |
| `src/aura/workspace/server.py` | Catalogue fields and filter, graph pin fill, edit routes, `RULES_BROKEN`, prune route |
| Frontend `src/wiring3d.ts`, `src/ComponentLibrary.tsx`, `src/libraryHelpers.ts`, `src/ComponentCard.tsx`, `src/SchematicEditor.tsx`, `src/CodeView.tsx` | Read pins from the graph, library tabs and badges, inspector actions, wire editing, broken-rule UI |
| `src/aura/workspace/web/frontend/src/catalogPins.fixture.json` (generated) | Catalogue pin labels for the frontend consistency test |

---

### Task 1: Catalogue categories, pins, settings, new parts

**Files:**
- Create: `src/aura/verification/pins.py`
- Modify: `src/aura/verification/catalogue.py`, `src/aura/workspace/server.py` (`get_catalogue`, ~line 946)
- Test: `tests/test_catalogue_library.py`

**Interfaces:**
- Produces:
  - `PinDefinition(name: str, label: str, role: str, voltage_range: tuple[float, float] | None = None)`, a frozen dataclass with `to_dict() -> {"name","label","role","voltageRange"}`. `name` is the graph interface name (`power`, `ground`, `signal`, `sda`, …). `label` is the printed text.
  - `pins_for_definition(definition_id: str | None, family: str) -> tuple[PinDefinition, ...]`.
  - `CATEGORY_BY_FAMILY: dict[str, str]`.
  - `PART_SETTINGS: dict[str, dict[str, dict]]` (definition id → key → `{"min","max"}` or `{"choices": [...]}`).
  - `ComponentDefinition` gains `category: str = "basic"`, `pins: tuple[PinDefinition, ...] = ()`, `settings: dict = {}` (use `field(default_factory=dict)`), `support: str = "full"`. `to_dict()` adds `category`, `pins`, `settings`, `support`.
  - `GET /api/catalogue?category=displays` filters by category.

- [ ] **Step 1: Write failing tests** in `tests/test_catalogue_library.py`:

```python
from aura.verification.catalogue import BY_ID, CATALOGUE
from aura.verification.pins import ROLES, CATEGORIES

def test_every_part_has_category_pins_source_and_known_roles():
    for d in CATALOGUE:
        assert d.category in CATEGORIES, d.component_definition_id
        assert d.evidence_ids, d.component_definition_id
        assert all(p.role in ROLES for p in d.pins), d.component_definition_id
        if d.family not in {"enclosure", "breadboard", "terminal_block"}:
            assert d.pins, d.component_definition_id

def test_new_categories_filled():
    by_cat = {c: [d for d in CATALOGUE if d.category == c] for c in CATEGORIES}
    assert {d.component_definition_id for d in by_cat["displays"]} >= {"ssd1306-oled-128x64", "lcd1602-i2c", "max7219-matrix", "ws2812b-stick-8"}
    assert {d.component_definition_id for d in by_cat["communication"]} >= {"rfm95w-lora", "nrf24l01-plus", "neo6m-gps", "mfrc522-rfid"}

def test_only_devkit_is_full_board():
    boards = [d for d in CATALOGUE if d.category == "boards"]
    assert {d.component_definition_id for d in boards if d.support == "full"} == {"esp32-devkit-v1"}

def test_bme280_overrides_signal_with_i2c_pins():
    roles = {p.label: p.role for p in BY_ID["bme280-i2c-module"].pins}
    assert roles["SDA"] == "i2c_sda" and roles["SCL"] == "i2c_scl"

def test_ds18b20_threshold_setting_range():
    assert BY_ID["ds18b20-module"].settings["threshold_c"] == {"min": -55.0, "max": 125.0}

def test_api_filters_by_category(client):  # reuse the TestClient fixture pattern from tests/test_add_components.py
    items = client.get("/api/catalogue", params={"category": "displays"}).json()
    assert items and all(i["category"] == "displays" for i in items)
    assert {"pins", "settings", "support"} <= set(items[0])
```

Also add `test_esp32_labels_match_pinout_ts`. It parses the `J2`/`J3` arrays from `src/aura/workspace/web/frontend/src/pinout.ts` with a regex and asserts that every ESP32 `PinDefinition.label` is in them.

- [ ] **Step 2: Run** `.\.venv\Scripts\python.exe -m pytest tests/test_catalogue_library.py -q`. Expected: FAIL with ImportError on `aura.verification.pins`.

- [ ] **Step 3: Implement `pins.py`.**
  - `FAMILY_PINS` gets one template per family. It reuses the exact interface names from `component_interfaces`. Labels come from today's `INTERFACE_PINS` in `wiring3d.ts`, so 3D anchors keep matching.
  - The `signal` role follows the family: `analog_out` for soil/light; `digital_out` for temperature, motion and switch; `digital_in` for relay, mosfet, motor driver and indicator; `pwm_in` for servo.
  - ESP32 board pins are `3V3` (`vcc-out`, power_out), `5V` (`power`, power_out), `GND`, the bus ports from Task 2, and `signal-N`. Their labels resolve from `gpio_map` at render time, so their template label is the port name.
  - `PART_PIN_OVERRIDES` replaces `signal` with `sda`/`scl` for the I²C parts: bme280-*, aht20, bh1750, mpu6050, vl53l0x, ssd1306, lcd1602. SPI parts (`max7219`, `rfm95w`, `nrf24l01`, `mfrc522`) get `sck`/`mosi`/`miso`/`cs`, where MAX7219 has `DIN`/`CLK`/`CS` and no MISO. UART parts get `tx`/`rx`. The WS2812B gets `DIN` (`digital_in`).
  - `PART_SETTINGS` carries `threshold_c` for DS18B20, `min_angle`/`max_angle` 0–180 for the servos, and `i2c_address` choices: SSD1306 `[60, 61]`, LCD1602 `[32..39]`, BME280 `[118, 119]`, BH1750 `[35, 92]`, MPU6050 `[104, 105]`, AHT20 `[56]`, VL53L0X `[41]`.
  - `main()` for `python -m aura.verification.pins --dump PATH` writes `{family: {name: label}}` plus per-part overrides as JSON.

- [ ] **Step 4: Add the 15 parts** to `_SPECS`, with a `_SOURCES` entry for each. Confirm each URL resolves with `curl -sI -o /dev/null -w "%{http_code}" URL`. If a URL is dead, find the manufacturer page; if there is none, skip the part.

| id | family | category | V range | mA | dims mm | source URL |
|---|---|---|---|---|---|---|
| ssd1306-oled-128x64 | oled_display | displays | 3.0–5.0 | 20 | 27,27,4 | https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf |
| lcd1602-i2c | character_display | displays | 4.5–5.5 | 30 | 80,36,20 | https://www.nxp.com/docs/en/data-sheet/PCF8574_PCF8574A.pdf |
| max7219-matrix | led_matrix | displays | 4.0–5.5 | 330 | 32,32,15 | https://www.analog.com/media/en/technical-documentation/data-sheets/MAX7219-MAX7221.pdf |
| ws2812b-stick-8 | addressable_led | displays | 3.5–5.3 | 480 | 51,10,3 | https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf |
| hc05-bluetooth | bluetooth_module | communication | 3.6–6.0 | 40 | 37,16,4 | manufacturer page required, else skip |
| rfm95w-lora | lora_module | communication | 1.8–3.7 | 120 | 16,16,2 | https://www.hoperf.com/modules/lora/RFM95.html |
| nrf24l01-plus | rf_module | communication | 1.9–3.6 | 14 | 29,15,4 | https://www.nordicsemi.com/Products/nRF24-series |
| neo6m-gps | gps_module | communication | 2.7–3.6 | 67 | 25,35,8 | https://www.u-blox.com/en/product/neo-6-series |
| mfrc522-rfid | rfid_module | communication | 2.5–3.6 | 100 | 60,40,5 | https://www.nxp.com/docs/en/data-sheet/MFRC522.pdf |
| ams1117-3v3 | ldo_regulator | power | 4.5–15 | 800 | 10,7,2 | http://www.advanced-monolithic.com/pdf/ds1117.pdf |
| tp4056-charger | battery_charger | power | 4.0–8.0 | 1000 | 26,17,4 | https://dlnmh9ip6v2uc.cloudfront.net/datasheets/Prototyping/TP4056.pdf |
| holder-18650 | battery | power | 3.0–4.2 | 2000 | 77,21,19 | https://www.keyelco.com/product.cfm/product_id/918 |
| pot-10k | potentiometer | basic | 0–5.5 | 1 | 9.5,10,6 | https://www.bourns.com/docs/Product-Datasheets/ptv09.pdf |
| buzzer-active-5v | buzzer | basic | 3.5–5.5 | 30 | 12,12,9.5 | https://www.puiaudio.com/products/ai-1223-twt-5v-r |
| breadboard-400 | breadboard | breadboards | 0–50 | 0 | 82,55,9 | https://www.busboard.com/BB400 |

  - The SSD1306 and LCD1602 entries list voltage ranges for the **module** (with its regulator), not for the bare chip. Give the LCD1602 a `logic_voltage` property of 5.0 V (it is used in Task 6).
  - Use the existing `breadboard-830` construction pattern for the 400-point breadboard.
  - Set `support="listed"` for every board except `esp32-devkit-v1`.

- [ ] **Step 5: Expose the new fields** in `get_catalogue`: add an optional `category` query parameter and filter on it.

- [ ] **Step 6: Generate the fixture.** Run `.\.venv\Scripts\python.exe -m aura.verification.pins --dump src/aura/workspace/web/frontend/src/catalogPins.fixture.json`. Add `test_fixture_is_current`, which regenerates the dump to a temp file and compares it with the committed one.

- [ ] **Step 7: Run** `pytest tests/test_catalogue_library.py tests/test_add_components.py tests/test_ideas_api.py tests/test_idea_pricing.py -q`. Expected: all PASS, with the existing tests unchanged.

- [ ] **Step 8: Commit** with the message `Catalogue: categories, pin templates, settings, 15 display/comms/power parts`.

---

### Task 2: Board ports, new-family interfaces, pin snapshot on graph read

**Files:**
- Modify: `src/aura/engineering_graph/interfaces.py`, `src/aura/workspace/server.py` (`GET /api/projects/{id}/graph`)
- Test: `tests/test_board_ports.py`

**Interfaces:**
- Consumes: `pins_for_definition` (Task 1).
- Produces:
  - `microcontroller_board` interfaces gain `i2c-sda`, `i2c-scl`, `spi-sck`, `spi-mosi`, `spi-miso` and `signal-9`…`signal-16`. All are appended **after** `vcc-out`, with kind `control_output`.
  - Each new family has an interface entry in `component_interfaces` whose names match its `FAMILY_PINS` or override names.
  - `BUS_GPIOS = {"i2c-sda": 21, "i2c-scl": 22, "spi-sck": 18, "spi-mosi": 23, "spi-miso": 19}`.
  - `allocate_gpio` keeps its pool but moves the `BUS_GPIOS` values to the end.
  - The `GET /graph` response gives each component a `metadata.pins` list. It is the stored snapshot if one exists, otherwise `pins_for_definition(...)` as dicts. Nothing is written back.

- [ ] **Step 1: Write failing tests:**
  - `test_existing_board_port_positions_unchanged`: the first 11 interfaces of `component_interfaces("microcontroller_board", …)` keep the same names and positions as before. Capture them in the test from today's code, before editing.
  - `test_bus_ports_appended`.
  - `test_every_catalogue_pin_name_is_a_family_interface`: for every part, each `pin.name` is in `component_interfaces(d.family, dims)` names.
  - `test_allocator_prefers_non_bus_pins`: `allocate_gpio("motion_sensor", None, {4,13,14,16,17})` is not in `BUS_GPIOS.values()`.
  - `test_graph_route_fills_pins_for_legacy_entities`: on the deterministic fan project, every component in `/graph` has `metadata.pins`, and the temperature sensor's `signal` label is `DAT`.

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement** the interface additions and the allocator ordering. In the graph route, fill pins on a copy of each entity dict.

- [ ] **Step 4: Run** `pytest tests/test_board_ports.py tests/test_gpio_allocation.py tests/test_fan_firmware_slice.py tests/test_irrigation_vertical_slice.py tests/test_engineering_invariants.py -q`. Expected: PASS. If `test_gpio_allocation` shows changed picks, they must involve only bus GPIOs. Any other change is a bug.

- [ ] **Step 5: Commit** with the message `Board bus ports, new-family interfaces, pins on graph read`.

---

### Task 3: Auto-wire on add

**Files:**
- Create: `src/aura/workspace/autowire.py`
- Modify: `src/aura/workspace/modifications.py` (`propose_add_components`, lines 424–486)
- Test: `tests/test_autowire.py`, and update `tests/test_add_components.py::test_every_add_warns_power_and_ground_are_unwired_and_switch_is_an_input`

**Interfaces:**
- Consumes: `PinDefinition`, `BUS_GPIOS`, `allocate_gpio`, `component_interfaces`.
- Produces:
  - `Wire(connection_id: str, source_id: str, source_interface: str, target_id: str, target_interface: str, connection_type: str)`: a frozen dataclass with `to_ops() -> list[GraphOperation]`, which yields the same connection entity and `-edge` relationship shape `propose_add_components` uses today.
  - `autowire(graph: EngineeringGraph, controller: EngineeringEntity, entity_id: str, pins: tuple[PinDefinition, ...], gpio_map: dict[str, int], free_ports: list[str]) -> tuple[list[Wire], list[dict]]`. It returns the wires plus check dicts (`{"state","message"}`), mutates `gpio_map` and consumes `free_ports`. It raises `ModificationError` with `BUS_PINS_IN_USE`, `UART_IN_USE`, `NO_FREE_PIN` or `NEEDS_EXTERNAL_SUPPLY`.
  - Added entities store `metadata["pins"] = [p.to_dict() for p in pins]`.

Rules, from spec §2:
- **power_in:** wire to `vcc-out` (3V3) when the range includes 3.3. Otherwise wire to `power` (5V) when it includes 5.0. Otherwise raise `NEEDS_EXTERNAL_SUPPLY` with the message "{part} needs {lo}–{hi} V; add a supply first".
- **ground:** wire to `ground`.
- **I²C:** the first I²C part claims `i2c-sda`/`i2c-scl` in `gpio_map`, after checking that 21/22 are not used by another port. Later I²C parts wire to the same board ports.
- **SPI:** shared ports, same pattern; each part's `cs` takes a `signal-N` port via the allocator.
- **UART:** two allocator pins on `signal-N` ports. A second UART part raises `UART_IN_USE`.
- **Everything else:** the existing per-family path, with unchanged port order.
- **Connection types:** `power` for power wires, `ground` for ground wires; `signal` when the part drives the board, `control` when the board drives the part.
- **No full controller in the project:** this means no entity with `gpio_map`, or one that is listed-only. The part is added without wires; `autowire` is not called, and the proposal carries the WARNING "No supported controller — {part} added unwired." This replaces today's `NO_CONTROLLER` 409. Add a test, `test_add_without_controller_is_unwired_with_warning`, and update `test_add_components.py::test_errors` to match.

- [ ] **Step 1: Write failing tests:**
  - `test_fan_and_plant_migration_unchanged`: build both deterministic demos. Assert that the connection entities' `(source_id, source_interface, target_id, target_interface, connection_type)` sets and `gpio_map` equal the values captured from `HEAD` before this task. Capture the values in a JSON fixture `tests/fixtures/demo_wires.json` in Step 1, generated from unchanged code.
  - `test_add_ds18b20_gets_power_ground_and_signal`: three wires, `power` goes to `vcc-out`.
  - `test_two_i2c_parts_share_bus_ports`.
  - `test_spi_part_gets_own_cs`.
  - `test_bus_pins_in_use_names_holder`: pin-change GPIO21 onto a signal port first, then adding the SSD1306 gives 409 `BUS_PINS_IN_USE`, and the message contains the port name.
  - `test_second_uart_part_refused`.
  - `test_12v_pump_needs_external_supply`.
  - `test_undo_add_removes_all_wires`: commit the add, then undo; the graph equals the pre-add graph, compared with `graph_to_dict` minus revisions.
  - Update the old "unwired" warning test: wired parts no longer carry the "Power and ground are not wired" warning.

- [ ] **Step 2: Run them.** Expected: FAIL (the migration test passes, being the guard).

- [ ] **Step 3: Implement** `autowire.py` and call it from `propose_add_components`. Then make the existing add-undo branch in `inverse_proposal` remove every wire the add made: record `connectionIds: [...]` on the operation and keep reading the old single `connectionId` too.

- [ ] **Step 4: Run** `pytest tests/test_autowire.py tests/test_add_components.py tests/test_pin_change.py tests/test_firmware_io.py tests/test_generic_sketch.py -q`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `Auto-wire power, ground, buses and signals on add`.

---

### Task 4: Snapshot proposals and generic undo

**Files:**
- Create: `src/aura/workspace/edits.py`
- Modify: `src/aura/workspace/modifications.py` (`inverse_proposal`: one new branch at the top)
- Test: `tests/test_snapshot_undo.py`

**Interfaces:**
- Produces:
  - `snapshot_proposal(graph: EngineeringGraph, base: int, mode: str, summary: str, patch_ops: list[GraphOperation], extra_checks: list[dict] = []) -> ModificationProposal`. Before building the proposal it records one operation `{"operation": "snapshot_edit", "mode": mode, "before": {"entities": [...], "relationships": [...]}, "addedEntityIds": [...], "addedRelationshipIds": [...]}`. The entity and relationship dicts come from the `serialization.py` helpers for every id the patch touches. `affected_ids` are the touched component ids, and `regenerate` matches `propose_add_components`.
  - `inverse_proposal` sends a revision whose `diff.changed[0].operation == "snapshot_edit"` to `_inverse_snapshot`. That builds remove ops for the added ids, plus add-or-update ops restoring `before`. Nets: drop the `electrical_net` entities that point at removed parts, the same way the existing add-undo branch does.

- [ ] **Step 1: Write failing tests.** Use a tiny fake op through `snapshot_proposal` (an UPDATE of the controller's name):
  - `test_snapshot_commit_then_undo_restores_graph`
  - `test_snapshot_records_added_ids`
  - `test_undo_of_snapshot_with_removed_entity_restores_it`

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement** `snapshot_proposal` and the inverse branch. Leave the existing branches untouched.

- [ ] **Step 4: Run** `pytest tests/test_snapshot_undo.py tests/test_modification_loop.py tests/test_lifecycle_torture.py -q`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `Generic before-image undo for edit proposals`.

---

### Task 5: Wire edits: connect, reconnect, disconnect

**Files:**
- Modify: `src/aura/workspace/edits.py`, `src/aura/workspace/server.py`
- Test: `tests/test_wire_edits.py`

**Interfaces:**
- Consumes: `snapshot_proposal`, `Wire`.
- Produces:
  - `propose_wire(graph, base, action: Literal["connect","reconnect","disconnect"], *, source: tuple[str,str] | None = None, target: tuple[str,str] | None = None, connection_id: str | None = None, end: Literal["source","target"] | None = None) -> ModificationProposal`.
  - Route `POST /api/projects/{id}/wire-proposals` with body `{baseRevision, action, sourceId?, sourceInterface?, targetId?, targetInterface?, connectionId?, end?}`. It returns `proposal.to_dict()` and is stored in `modification_proposals` like `create_pin_proposal`.
  - `connection_type` is derived from the two pin roles: power_out↔power_in is `power`; ground↔ground is `ground`; anything driven by the board is `control`; otherwise `signal`.
  - Reconnect keeps `connection_id` and changes one end.
  - Errors: unknown part or pin gives 404 `UNKNOWN_PIN`. A pin that is not in the part's pins gives 422 `UNKNOWN_PIN`. An existing identical wire gives 409 `WIRE_EXISTS`.
  - Electrical validity is left to verification (Task 6), so a bad wire is a rejected commit, not a refused proposal.

- [ ] **Step 1: Write failing tests:**
  - `test_connect_adds_wire_and_commits`: for an added LED, disconnect its signal, then connect it to `signal-5`.
  - `test_reconnect_moves_one_end_keeps_id`
  - `test_disconnect_removes_wire_and_warns_unwired`: after commit, verification includes `ELEC_UNWIRED`.
  - `test_each_wire_edit_undoes_to_equal_graph`
  - `test_unknown_pin_and_duplicate_wire`
  - `test_stale_base_409`

- [ ] **Step 2: Run them.** Expected: FAIL. The unwired test passes once Task 6 lands; mark it `xfail(strict=True)` with reason "Task 6" and remove the mark in Task 6.

- [ ] **Step 3: Implement** `propose_wire` and the route.

- [ ] **Step 4: Run** `pytest tests/test_wire_edits.py -q`. Expected: PASS, except the xfail.

- [ ] **Step 5: Commit** with the message `Wire edit proposals: connect, reconnect, disconnect`.

---

### Task 6: Electrical checks

**Files:**
- Modify: `src/aura/verification/graph_rules.py` (`evaluate_graph`; new helper `_pin_role_checks(graph, components, nets, add)` called after `_gpio_assignments`)
- Test: `tests/test_pin_role_checks.py`

**Interfaces:**
- Consumes: entity `metadata.pins`, or `pins_for_definition` when it is absent, and `electrical_nets(graph)`.
- Produces these finding codes. All use `category="electrical"` and name the parts and pins in the message.

| Code | State | Blocking | Condition |
|---|---|---|---|
| `ELEC_DRIVER_CONFLICT` | FAILED | yes | A net with two or more pins of role `digital_out`, `power_out` or `uart_tx`. The board's own `power`/`vcc-out` count as power_out |
| `ELEC_SUPPLY_RANGE` | FAILED | yes | A power net whose source voltage (3.3 for `vcc-out`, 5.0 for `power`, otherwise the part's range) is outside a `power_in` member's range |
| `ELEC_GROUND_MIX` | FAILED | yes | A net containing a `ground` pin plus any non-ground, non-passive pin |
| `ELEC_LOGIC_LEVEL` | FAILED | yes | A part on the 5 V net whose `digital_out`, `uart_tx` or `i2c_*` pin shares a net with an ESP32 port. Exempt: parts with property `logic_voltage` ≤ 3.6, and `pir-hc-sr501` (3.3 V output, given a `logic_voltage` of 3.3 in Task 1). The message ends "Use a 3.3 V part or a level shifter." |
| `ELEC_I2C_ADDRESS` | FAILED | yes | Two parts on the same I²C net with the same `i2c_address`, taken from `parameters` or else the first choice in `PART_SETTINGS` |
| `ELEC_3V3_BUDGET` | WARNING | no | The sum of `current` (mA) of `power_in` pins on the `vcc-out` net is above 500 mA (ESP32-DevKitC V4 on-board regulator; cite the Espressif DevKitC guide in a comment) |
| `ELEC_UNWIRED` | WARNING | no | A part's `power_in`, `ground` or signal-role pin is on no net. The message is "{part}: {label} is not wired — not electrically complete." |

- [ ] **Step 1: Write failing tests**, one pass and one fail per row. Build the graphs with `propose_add_components` and `propose_wire` on the deterministic fan project, then call `VerificationService().verify_graph(graph)`. Also add:
  - `test_fan_and_plant_demos_have_no_new_failures`: both demos produce none of the seven codes as FAILED.
  - `test_lcd1602_on_5v_fails_logic_level`: Review Focus 2.

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement** `_pin_role_checks`. Remove the xfail from Task 5.

- [ ] **Step 4: Run** `pytest tests/test_pin_role_checks.py tests/test_wire_edits.py tests/test_engineering_invariants.py tests/test_verification_real_world.py tests/test_verification_generated_torture.py tests/test_verification_graph_integrity.py -q`. Expected: PASS.

- [ ] **Step 5: Run the full Python suite** with `.\scripts\test.ps1 -Module all`. Expected: the only failures are the ones recorded before this work (`test_startup_boundaries`). Record the counts.

- [ ] **Step 6: Commit** with the message `Pin-role electrical checks: drivers, supply, ground, logic level, I2C address, 3V3 budget, unwired`.

---

### Task 7: Rename and configure

**Files:**
- Modify: `src/aura/workspace/edits.py`, `src/aura/workspace/server.py`, `src/aura/workspace/modifications.py` (`propose_parameter_change` reads `PART_SETTINGS`; `CONFIGURABLE_PARAMETERS` is removed after a `grep -rn CONFIGURABLE_PARAMETERS src tests` shows no other user)
- Test: `tests/test_rename_configure.py`, plus the existing `tests/test_parameter_proposal.py`, which must stay green

**Interfaces:**
- Produces:
  - `propose_rename(graph, base, component_id: str, name: str) -> ModificationProposal`. The name is stripped, 1–60 characters, and has no control characters; otherwise it fails with 422 `INVALID_NAME`. Rename is a `snapshot_proposal` with `mode="rename"` and updates `entity.name`.
  - Route `POST /api/projects/{id}/rename-proposals` with body `{baseRevision, componentId, name}`.
  - `propose_parameter_change` validates against `PART_SETTINGS[definition_id][key]`, using `{"min","max"}` or `{"choices"}`. The error code stays `PARAMETER_NOT_CONFIGURABLE` / `invalid_parameter_edit` and the route is unchanged.

- [ ] **Step 1: Write failing tests:**
  - `test_rename_shows_in_graph_and_firmware_ios`: after committing a rename, `/graph` entity `name` and the `/firmware` `ios[].name` show the new name.
  - `test_rename_undo`
  - `test_rename_rejects_empty_and_long`
  - `test_servo_angle_setting_range`
  - `test_i2c_address_choice_enforced`
  - `test_rating_still_not_configurable`

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** `pytest tests/test_rename_configure.py tests/test_parameter_proposal.py -q`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `Rename as a revision; per-part settings from the catalogue`.

---

### Task 8: Delete, replace, broken rules

**Files:**
- Modify: `src/aura/workspace/edits.py`, `src/aura/workspace/server.py` (`_effective_firmware` ~1317, `compile_firmware` ~1469, new routes)
- Test: `tests/test_delete_replace.py`

**Interfaces:**
- Consumes: `snapshot_proposal`, `autowire` (to rewire pins after a replace), `Wire`.
- Produces:
  - `propose_delete(graph, base, component_id) -> ModificationProposal`. It removes the part, every connection entity and edge touching it, and its `gpio_map` ports (`mode="delete"`). The controller itself is refused with 409 `CANNOT_DELETE_CONTROLLER`.
  - `propose_replace(graph, base, component_id, definition_id) -> ModificationProposal`. It keeps the entity id and updates the family, definition id, `metadata.pins`, dimensions and the name (unless the user renamed it). Each wire moves to the new pin with the same role, otherwise it is removed. Pins with no matching wire are auto-wired. The proposal's `verification.checks` lists the removed wires.
  - Replacing with a part from a different `category` gives 422 `REPLACE_CATEGORY_MISMATCH`. Replacing with a listed-only board gives 409 `BOARD_LISTED_ONLY`.
  - Both proposals add a check listing the stored rules that become broken. Use `io_points` on the patched graph and the same moved/validate logic `_effective_firmware` uses; extract that logic into `broken_rules(stored, ios) -> list[dict]` in `server.py`.
  - **Carry-over on replace:** when both the old and the new definition are in `DRIVERS` with the same `value`, commit rewrites the stored rules' IO ids and `bindings` from the old IO id to the new one. This happens in the commit route after `save_commit`, only for `mode == "replace"`.
  - `POST /api/projects/{id}/compile` returns 422 `{"code": "RULES_BROKEN", "rules": [...]}` when `droppedRules` is non-empty. Upload is already gated on a passing compile (`COMPILE_REQUIRED`).
  - `POST /api/projects/{id}/control-rules/prune` saves the stored rules minus the broken ones and returns the firmware payload.
  - Routes: `POST /api/projects/{id}/delete-proposals` with body `{baseRevision, componentId}`, and `POST /api/projects/{id}/replace-proposals` with body `{baseRevision, componentId, componentDefinitionId}`.

- [ ] **Step 1: Write failing tests** on the plant project, which has a soil → pump rule:
  - `test_delete_sensor_flags_rule_and_blocks_compile`: compile gives 422 `RULES_BROKEN`.
  - `test_prune_unblocks_compile`: compile then returns any status other than `RULES_BROKEN`.
  - `test_delete_undo_restores_part_wires_gpio_and_rule`
  - `test_replace_soil_with_photoresistor_carries_rule`: both are `percent`, and the rule is not broken.
  - `test_replace_relay_with_servo_breaks_rule`: `bool` vs `angle`.
  - `test_replace_moves_wires_by_role_and_lists_dropped`
  - `test_replace_category_mismatch_and_listed_board`
  - `test_cannot_delete_controller`

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** `pytest tests/test_delete_replace.py tests/test_firmware_edit.py tests/test_generic_sketch.py tests/test_hardware_upload.py -q`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `Delete and replace parts; broken rules block compile until pruned`.

---

### Task 9: Frontend reads pins from the graph

**Files:**
- Modify: `src/aura/workspace/web/frontend/src/wiring3d.ts`, `src/SchematicEditor.tsx`, `src/wiringLayout.ts` (wherever `INTERFACE_PINS` or `pinFor` is used)
- Test: `src/wiring3d.test.ts`, new `src/catalogPins.test.ts`

**Interfaces:**
- Consumes: `metadata.pins` on every graph component (Task 2).
- Produces: `pinFor(entity, iface)` returns the `gpio_map` label for the board as today; otherwise it returns `entity.metadata.pins.find(p => p.name === iface)?.label ?? null`. `INTERFACE_PINS` is deleted.

- [ ] **Step 1: Write failing tests:**
  - `wiring3d.test.ts`: `pinFor` on an entity with `metadata.pins=[{name:"signal",label:"DAT",role:"digital_out"}]` returns `"DAT"`. An entity without pins returns `null`.
  - `catalogPins.test.ts`: for every family in `catalogPins.fixture.json` that has a model in `studioModels.ts`, every label is an anchor name of that model. Families with no model are skipped, because they are proxies.

- [ ] **Step 2: Run** `npm test` in `src/aura/workspace/web/frontend`. Expected: FAIL.

- [ ] **Step 3: Implement.** Confirm with `grep -rn INTERFACE_PINS src` that nothing is left.

- [ ] **Step 4: Run** `npm test` and `npm run build`. Expected: PASS. Then run `npx playwright test e2e/studio.spec.ts e2e/wiring-edit.spec.ts`; expected to PASS with the same 14 fan wires.

- [ ] **Step 5: Commit** with the message `Frontend pin labels come from the graph; drop INTERFACE_PINS`.

---

### Task 10: Library tabs and inspector actions

**Files:**
- Modify: `src/ComponentLibrary.tsx`, `src/libraryHelpers.ts`, `src/ComponentCard.tsx`, `src/CodeView.tsx`
- Test: `src/libraryHelpers.test.ts`, `e2e/library.spec.ts`

**Interfaces:**
- Consumes: `GET /api/catalogue` (`category`, `support`, `pins`, `settings`), plus the rename, parameter, replace and delete proposal routes, the `prune` route and `RULES_BROKEN`.
- Produces:
  - `filterCatalogue(items, {category, query}) -> items`. The query matches part number, manufacturer, family and category, case-insensitive.
  - `badgesFor(item, drivers: Set<string>) -> string[]` returns `"Listed only"` when `support === "listed"` and `"No driver yet"` when the id is not in the driver set. The driver ids come from the `/firmware` `ios[].supported` data already loaded.
  - **Inspector:** Rename (text field), Settings (a form built from `settings`: number inputs with min/max, selects for choices), Replace (a list from the same category, ordered with parts sharing all pin roles first), Delete. Each action opens the existing proposal preview.
  - **CodeView:** the `dropped-rules` box is renamed to "Broken rules — compile is blocked until you fix or remove them" and gains a "Remove broken rules" button that calls `prune`.

- [ ] **Step 1: Write failing tests:**
  - Unit tests for `filterCatalogue` and `badgesFor`.
  - `e2e/library.spec.ts`: the Displays tab shows the SSD1306. Adding it shows a preview with 4 wires, and accepting it puts it in the rail. Then rename it to "Status screen", which shows in the inspector and in the 3D hover label. Then delete the plant's soil sensor; Code shows "Broken rules", Compile shows `RULES_BROKEN`, "Remove broken rules" clears them, and Ctrl+Z restores the sensor.

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** `npm test`, `npm run build`, and `npx playwright test e2e/library.spec.ts`. Expected: PASS.

- [ ] **Step 5: Commit** with the message `Library categories and badges; inspector rename, settings, replace, delete; broken-rule fix`.

---

### Task 11: Wiring view wire editing

**Files:**
- Modify: `src/SchematicEditor.tsx`, `src/wiringLayout.ts`
- Test: `e2e/wiring-edit.spec.ts`

**Interfaces:**
- Consumes: `POST /wire-proposals` (Task 5) and the existing proposal preview and undo.
- Produces, in the Wiring view:
  - Click pin A, then pin B, and you get a connect proposal.
  - Drag a wire end handle onto another pin, and you get a reconnect proposal.
  - Select a wire and press Delete, and you get a disconnect proposal.
  - Esc cancels a pending pin pick.
  - Keyboard: with a wire selected (W / Shift+W, already there), `R` then arrow keys picks a target pin for reconnect.
  - Layout bends of a reconnected wire reset. Other wires keep theirs.

- [ ] **Step 1: Write failing e2e tests** in `wiring-edit.spec.ts`:
  - connect an added LED, then accept, and it appears in 3D;
  - reconnect a wire end and undo;
  - disconnect, which shows the "not wired" warning in verification;
  - wire a 5 V LCD1602 SDA to the board, which the preview shows as `ELEC_LOGIC_LEVEL` failed, and Accept is disabled.

- [ ] **Step 2: Run them.** Expected: FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** `npx playwright test e2e/wiring-edit.spec.ts e2e/file-menu.spec.ts e2e/layout.spec.ts`. Expected: PASS.

- [ ] **Step 5: Run the full gates:** `.\scripts\test.ps1 -Module all`, `npm test`, `npm run test:browser`. Expected: no failures beyond the recorded baseline (Python: `test_startup_boundaries`; browser: the 6 pre-existing failures). Record the counts.

- [ ] **Step 6: Update docs.** In `README.md`, under "Component library" and "Menu bar…", remove "no endpoint reconnection" and "Electrical wiring between arbitrary parts is not offered", and add the new operations and the broken-rule rule. In `docs/active/README.md` §0, add a dated bullet with the evidence counts.

- [ ] **Step 7: Commit** with the message `Wiring view: connect, reconnect, disconnect; docs and evidence`.
