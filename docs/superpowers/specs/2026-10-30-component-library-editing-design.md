# Component library and manual editing — design

**Date:** 2026-10-30. **Branch:** `AURA-nemotron_test1`. **Status:** approved in conversation; awaiting spec review.

Part 1 of 3. Part 2 adds I²C/SPI/UART firmware drivers. Part 3 makes the idea flow (Nemotron) produce a complete project from parts 1 and 2. Order: 1 → 2 → 3.

## Goal

A categorized, searchable IoT library and manual editing (add, configure, connect, reconnect, disconnect, replace, rename, delete) where every edit is a verified, undoable revision and part names, pin labels, wires and firmware stay consistent because they read one source.

## Decisions (from the user)

| Question | Decision |
|---|---|
| Catalogue scope | Curated parts only, real part numbers and evidence; new parts use the existing "Generic proxy" 3D box |
| Electrical connect | Auto-wire on add, plus hand edit of wires in the Wiring view |
| Rules using a deleted/replaced part | Rule stays, flagged broken; compile blocked until fixed |
| Boards | ESP32 (`esp32-devkit-v1`) fully supported; other boards listed only, not selectable as project controller |
| Source of pin truth | The catalogue (approach 1); frontend `INTERFACE_PINS` is deleted |

## 1. Catalogue

`src/aura/verification/catalogue.py` has 53 parts and no displays or communication modules. Keep all 53; add these 15:

| Category | Added parts |
|---|---|
| Displays | SSD1306 0.96" OLED (I²C), LCD1602 with PCF8574 backpack (I²C), MAX7219 8×8 matrix (SPI), WS2812B 8-LED stick (single data line) |
| Communication | HC-05 Bluetooth (UART), RFM95W LoRa (SPI), nRF24L01+ (SPI), u-blox NEO-6M GPS (UART), MFRC522 RFID (SPI) |
| Power | AMS1117-3.3 LDO, TP4056 Li-ion charger, single 18650 holder |
| Basic | 10 kΩ potentiometer, 5 V active buzzer |
| Breadboards | 400-point breadboard |

Each added part needs a manufacturer source in `_SOURCES` (datasheet or product page). A part without one is not added.

**Categories** (new `category` field): `boards`, `sensors`, `actuators`, `displays`, `communication`, `power`, `breadboards`, `basic`. Existing families map to a category in one table; enclosures and terminal blocks go to `basic`.

**Pins** (new `pins` field, tuple of `PinDefinition(name, role, voltage_range)`):
- `name` is the label printed on the part (`DAT`, `SDA`, `VCC`, `IO4`).
- `role` is one of `power_in`, `power_out`, `ground`, `digital_in`, `digital_out`, `analog_out`, `pwm_in`, `i2c_sda`, `i2c_scl`, `spi_sck`, `spi_mosi`, `spi_miso`, `spi_cs`, `uart_tx`, `uart_rx`, `passive`.
- Pins are defined once per family as a template; a part overrides only where it differs (e.g. BME280 has `SDA`/`SCL`, not `DAT`).
- The ESP32 board's pins come from its header map (38 pins), matching the frontend `pinout.ts` labels; a test asserts the two agree.

**Settings** (new `settings` field): per-part configurable keys with datasheet ranges, e.g. DS18B20 `threshold_c` −55…125, SG90 `min_angle`/`max_angle` 0…180, I²C parts `i2c_address` from the datasheet's allowed set. Replaces the global `CONFIGURABLE_PARAMETERS`. Ratings, identity and safety facts remain non-editable.

**Listed-only parts:** boards other than `esp32-devkit-v1` carry `support: "listed"`; the API and UI show "Board listed — wiring and firmware not supported yet" and refuse them as a project controller. Parts with no firmware driver show "No driver yet" (existing wording).

**Snapshot:** when a part enters a graph, its pins and settings schema are copied into the entity's metadata. Old projects and imported ZIPs keep their meaning if the catalogue changes. Entities without a snapshot (projects created before this change) resolve pins from the family template on the server; nothing on the client guesses.

`GET /api/catalogue` gains `category`, `pins`, `settings`, `support`, and a `category` filter.

## 2. Auto-wire on add

Deterministic, no model call. For each added part, against the project's ESP32:

- `power_in` → `3V3` if the part's range includes 3.3 V, else `5V` (VIN) if it includes 5 V, else no wire and a FAIL "needs an external supply".
- `ground` → `GND`.
- `analog_out` → a free ADC1 GPIO (existing allocator).
- `i2c_sda`/`i2c_scl` → GPIO21/GPIO22, shared by all I²C parts on one bus.
- SPI → VSPI shared bus (GPIO18 SCK, 23 MOSI, 19 MISO) and a free GPIO per part for `spi_cs`.
- UART → UART2 (GPIO16 RX, 17 TX); a second UART part fails with "UART2 already used".
- `digital_in`/`digital_out`/`pwm_in` → `allocate_gpio`.

Each wire is a `connection` entity plus its `-edge` relationship, the existing storage form, with `from`/`to` pin names recorded. Pin allocation updates the board's `gpio_map` so firmware follows.

Parts without an ESP32 in the project (or with a listed-only board) are added without wires and the proposal says so.

## 3. Edit operations

All go through the existing path: deterministic proposal → verification → preview → accept (revision) → undo. No operation writes the graph directly.

| Operation | Behaviour |
|---|---|
| add | Existing `propose_add_components`, now auto-wired (§2) |
| connect | New wire between two pins; checked by §4 |
| reconnect | Move one end of an existing wire to another pin |
| disconnect | Remove a wire; affected required pins become "not electrically complete" warnings |
| replace | Swap the part's catalogue definition in place (same entity id). Wires move to pins with the same role; unmatched wires are removed and listed in the proposal. Rules carry over when the new part has the same IO kind (e.g. both `celsius`), otherwise they are flagged broken |
| delete | Remove the part, its wires and nets, and free its GPIOs. Rules using it are flagged broken |
| rename | Change the entity's display name as a revision; 3D labels, schematic, Code view and wiring view all show it (today rename is layout-only) |
| configure | Set a per-part setting within its catalogue range |

**Broken rules:** a rule whose input or output no longer exists, or whose IO kind changed, stays in the rule list with `broken: true` and a reason. Compile and upload return `RULES_BROKEN` until the user edits or removes it in the Code space. The proposal preview lists broken rules before accept.

**Undo:** each revision from these operations stores a before-image of every entity and relationship it added, changed or removed. One generic inverse restores it. The existing per-operation inverses (add, pin change, parameter) stay as they are.

Stale base revision returns `409 stale_revision` (existing behaviour).

## 4. Verification

New deterministic checks, run on every proposal and on commit:

| Check | Outcome |
|---|---|
| Two outputs on one net (`digital_out`, `power_out`, `uart_tx` driving each other) | FAIL |
| `power_out` → `power_in` outside the input's voltage range | FAIL |
| `ground` wired to anything but `ground` | FAIL |
| 5 V logic signal into an ESP32 GPIO (3.3 V only) | FAIL |
| GPIO used twice, strapping pin, output on input-only pin (existing `ELEC_GPIO`) | FAIL |
| Two I²C parts at the same address | FAIL |
| Sum of rated current on the 3V3 pin above the board's regulator budget | WARNING |
| Required pin left unwired | WARNING "not electrically complete" |

Codes follow the existing `ELEC_*` style. Checks are rule checks, not simulation; that wording stays in the UI.

## 5. UI

- **Library (☰ in Design):** category tabs, search across name/part number/category, badges "Listed only" and "No driver yet". Multi-select add stays.
- **Inspector:** Rename, Settings (form from the part's settings schema), Replace (catalogue parts in the same category, compatible ones first), Delete.
- **Wiring view:** click pin → pin to add a wire; drag a wire end to another pin to reconnect; select a wire and press Delete to disconnect. Removes the "no endpoint reconnection" limit.
- **3D and schematic:** pin labels and wire ends read the entity's pin snapshot. `INTERFACE_PINS` in `wiring3d.ts` is deleted.
- Every operation opens the existing proposal preview (checks, affected parts, broken rules) with Accept / Discard. Ctrl+Z undoes the last revision.

## 6. Out of scope

I²C/SPI/UART firmware drivers (part 2), non-ESP32 controllers, the idea flow (part 3), new detailed 3D models, hardware validation.

## 7. Testing

- Python, per operation: proposal contents, verification outcome, commit, and apply → undo → graph equal to before.
- Python, checks: one passing and one failing case per §4 row.
- Python, consistency: every catalogue part has a category, pins and a source; every pin role is known; ESP32 pin names equal `pinout.ts` labels; parts with a 3D model have an anchor for every pin name, others are marked proxy.
- Python, migration: the fan and plant fixtures produce the same wires (same endpoints, same GPIOs) before and after the pin migration.
- Frontend unit: wiring and 3D read pin snapshots; no `INTERFACE_PINS` import remains.
- Browser e2e: add a display, connect, reconnect, replace, delete (rule shows broken, compile blocked), undo each.

## Risks

- Migrating the 53 parts to pin templates touches 3D wiring, schematic and firmware for the fan and plant demos; the migration test above guards it.
- `component_interfaces`, `inverse_proposal` and the commit route are shared; GitNexus impact must be run on them before the plan's first edit.
