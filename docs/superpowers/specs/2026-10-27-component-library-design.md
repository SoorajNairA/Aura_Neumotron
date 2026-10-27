# Component library (roadmap phase 4) — design

Date: 2026-10-27 · Branch: `AURA-nemotron_test1` · Deadline: 2026-10-30 17:00 UTC
Scope: roadmap phase 4 — hamburger menu, searchable component library, multi-select, configuration,
placement, connection tools, supported component test benches. Built in five independently shippable
steps; if time runs out we stop after the last finished step.

## Goals

The user can open a library of the 52 catalogue parts from the Design space, find parts, add one or
more to the current design, configure them, wire them, and try supported parts on a test bench —
without ever bypassing verification.

## Global constraints

- AI proposes; deterministic verification decides. The library never writes the graph directly:
  every change is a `ModificationProposal` that goes through the existing propose → verify → commit
  path and is undoable.
- Never invent component ratings or prices. A part without a dated price shows "price unavailable".
- Label estimates, assumptions and generic proxies. Parts without a shaped model render as the
  existing family proxy, labelled as such.
- Never claim hardware validation. Test benches are labelled "Behavioral model — not hardware".
- Firmware is generated only for the fan workflow parts. An added part without a generator shows
  "Pin assigned — no generated driver yet" in the Code view; no code is fabricated for it.
- Strapping GPIOs (0, 2, 5, 12, 15) are never auto-assigned.

## Step 1 — Library menu

- A ☰ button in the Design space header opens a side panel ("Component library").
- Data: existing `GET /api/catalogue` (no backend change).
- Search box matches part name, part number, manufacturer and family (case-insensitive).
- Family filter chips built from the families present in the catalogue.
- Each row: name, manufacturer, family, key specs (voltage range, current, dimensions), price with
  source + retrieval date or "price unavailable", evidence source label.
- Keyboard accessible; Esc closes; focus returns to the ☰ button.

## Step 2 — Add parts (multi-select)

- Rows have checkboxes; "Add N to design" sends
  `POST /api/projects/{id}/component-proposals {baseRevision, componentDefinitionIds: [...]}`.
- New `propose_add_components(graph, base, definition_ids)` in `modifications.py`, kind
  `add_component`, returns one `ModificationProposal` for the whole selection:
  - one COMPONENT entity per part (`component-user-<family>-<hex>`), metadata carries
    `componentDefinitionId`, family, catalogue dimensions and default parameters;
  - placement: positioned beside the controller, offset so added parts do not overlap each other
    (no manual 3D drag in this phase);
  - parts whose family takes a controller signal get the lowest free GPIO from
    `ESP32_OUTPUT_GPIOS` minus strapping pins minus pins already in `gpio_map`, recorded as a new
    `gpio_map` port and an electrical relationship to the controller;
  - errors: `UNKNOWN_COMPONENT` (404), `NO_CONTROLLER` (409, signal part but no controller),
    `NO_FREE_PIN` (409), `stale_revision` (409, existing convention).
- The UI shows the proposal card (parts, assigned pins, verification), then Commit or Reject via the
  existing commit/delete proposal routes.

## Step 3 — Configure a part

- The component card lists the part's editable parameters (from the entity's `parameters`).
- Editing one sends the existing `set_parameter` modification; verification decides; errors show
  inline on the card.

## Step 4 — Connection tool

- In the component card, "Connect…" lets the user pick one of this part's interfaces, then another
  component and one of its interfaces.
- Sends `POST /api/projects/{id}/connection-proposals {baseRevision, sourceId, sourceInterface,
  targetId, targetInterface}`; the backend reuses the `_attach` interface-compatibility rules and
  rejects incompatible pairs (`incompatible_attachment_interfaces`) or occupied interfaces.
- Controller pin changes keep using the existing pin picker.

## Step 5 — Test benches

- Only for parts AURA can actually model: DS18B20 temperature sensor and the 5 V fan (+ its MOSFET
  driver). Every other part shows "No test bench yet".
- DS18B20 bench: temperature slider → reading quantised to the sensor's 12-bit 0.0625 °C step within
  its −55…125 °C range; a "disconnect" toggle shows the fault reading the firmware treats as a sensor
  fault.
- Fan bench: gate on/off → fan running/stopped; current shown only if the catalogue has a value,
  labelled as a curated estimate.
- Benches reuse `fanControl.ts` logic; no new physics.

## Testing

- pytest: `propose_add_components` (pin allocation skips strapping + used pins, `NO_FREE_PIN`,
  `NO_CONTROLLER`, unknown id, stale revision, commit then undo), connection-proposal route.
- vitest: library search/filter helper, bench quantisation helper.
- Playwright: open menu, search, multi-select add → proposal → commit; configure; connect rejection;
  DS18B20 bench.
- GitNexus impact before editing existing symbols; detect-changes before each commit.

## Out of scope

Manual 3D placement drag, firmware drivers for added parts, benches for unmodelled parts, live
hardware.
