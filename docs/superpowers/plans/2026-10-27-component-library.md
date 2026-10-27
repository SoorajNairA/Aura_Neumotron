# Component Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A ☰ component library in the Design space to browse, multi-add, configure, connect and bench-test parts, every change going through propose → verify → commit.

**Architecture:** Three new deterministic proposal builders in `modifications.py` (add components, set parameter, connect) return `ModificationProposal`s that the existing shared commit route applies, verifies and makes undoable. Frontend gets one panel component plus small pure helper modules with vitest tests. Test benches are pure frontend behavioral helpers.

**Tech Stack:** FastAPI, Engineering Graph, pytest; React 18 + TS, vitest, Playwright; Vite bundle committed to `src/aura/workspace/web/representation/`.

**Spec:** `docs/superpowers/specs/2026-10-27-component-library-design.md`

## Global Constraints

- The library never writes the graph directly; every change is a `ModificationProposal` committed via `POST /api/projects/{id}/modification-proposals/{proposalId}/commit`.
- A part without a dated price shows exactly `price unavailable`. No invented ratings or prices.
- Generic proxies stay labelled; no new 3D geometry.
- Bench label, exact copy: `Behavioral model — not hardware`. Unsupported parts: `No test bench yet`.
- Added part without a generator, exact Code-view copy: `Pin assigned — no generated driver yet`.
- Strapping GPIOs `(0, 2, 5, 12, 15)` are never auto-assigned; allocate from `ESP32_OUTPUT_GPIOS` in ascending order.
- Error codes: `UNKNOWN_COMPONENT` 404, `NO_CONTROLLER` 409, `NO_FREE_PIN` 409, `EMPTY_SELECTION` 422, `stale_revision` 409.
- Run GitNexus `impact` before editing an existing symbol (warn on HIGH/CRITICAL, UNKNOWN = unresolved) and `detect-changes --scope all` before every commit.
- Python tests: `export PATH="/d/Aura/Aura_Neumotron/.venv/Scripts:$PATH"; python -m pytest -q -p no:cacheprovider --ignore=tests/test_runtime_optimizations.py --ignore=tests/test_xtts_backend.py`. Frontend unit: `npm test`. Browser: `npx playwright test`. Rebuild bundle with `npm run build` before committing frontend.

## Review Focus

1. Adding a part to the fan demo must keep firmware `supported: true` and compile using the same sketch — pinned in Task 2.
2. Adding the same definition twice yields two distinct ids and two distinct GPIOs — pinned in Task 2.
3. Allocation must read the *current* `gpio_map` (after a pin change), not the original plan — pinned in Task 2.
4. Undo after an add removes the entity, its connection and its `gpio_map` port — pinned in Task 2.
5. A stale `baseRevision` from a second open window is rejected, not applied on top — pinned in Tasks 2, 4, 5.

---

### Task 1: Library menu (browse + search)

**Files:**
- Create: `src/aura/workspace/web/frontend/src/libraryHelpers.ts`, `src/aura/workspace/web/frontend/src/ComponentLibrary.tsx`, `src/aura/workspace/web/frontend/src/libraryHelpers.test.ts`, `src/aura/workspace/web/frontend/e2e/library.spec.ts`
- Modify: `WorkspaceApp.tsx` (☰ button in the Design header next to `view-switch`, ~line 299), `styles.css`

**Interfaces:**
- Produces: `type CatalogueItem` (shape of `GET /api/catalogue` items: `componentDefinitionId, family, manufacturer, partNumber, properties, interfaces, evidenceIds, price`); `filterParts(items:CatalogueItem[], query:string, family:string|null):CatalogueItem[]`; `priceLabel(item):string`; `<ComponentLibrary open onClose projectId baseRevision onProposal />` (onProposal used from Task 3).

- [ ] **Step 1: failing vitest** `libraryHelpers.test.ts`:
  - `filterParts(items,"ds18",null)` returns only the DS18B20 item; match is case-insensitive over partNumber, manufacturer, family, componentDefinitionId.
  - `filterParts(items,"","fan")` returns only family `fan`.
  - `priceLabel({price:null})==="price unavailable"`; `priceLabel({price:{usd:3.95,source:"s",retrieved:"2026-10-27"}})==="$3.95 (retrieved 2026-10-27)"`.
- [ ] **Step 2:** `npm test` → FAIL (module missing).
- [ ] **Step 3:** implement helpers; `ComponentLibrary` fetches `/api/catalogue` once, renders search input (`aria-label="Search parts"`), family chips, rows (`data-testid="library-row"`) with name, family, voltage range, current, dimensions, `priceLabel`. Panel is `role="dialog" aria-label="Component library"`; Esc closes and focus returns to the ☰ button (`aria-label="Open component library"`).
- [ ] **Step 4:** `npm test` → PASS.
- [ ] **Step 5: e2e** `library.spec.ts` (mocked `/api/catalogue`, open the fan project like `studio.spec.ts` does): open ☰, type `ds18`, exactly one `library-row`; an unpriced row shows `price unavailable`; Esc closes. Run `AURA_E2E_MOCK_ONLY=1 npx playwright test e2e/library.spec.ts` → PASS.
- [ ] **Step 6:** `npm run build`, detect-changes, commit `Component library menu with search and family filter`.

### Task 2: Backend — add components proposal

**Files:**
- Modify: `src/aura/workspace/modifications.py`, `src/aura/workspace/server.py` (body model + route next to `pin-proposals`)
- Test: `tests/test_add_components.py`

**Interfaces:**
- Consumes: `CATALOGUE`/`BY_ID` (`aura.verification.catalogue`), `ESP32_OUTPUT_GPIOS`, `ESP32_STRAPPING_GPIOS`.
- Produces: `SIGNAL_FAMILIES: frozenset[str]` = `{temperature_sensor, environmental_sensor, distance_sensor, light_sensor, motion_sensor, orientation_sensor, soil_moisture_sensor, relay_module, mosfet_driver, motor_driver, servo, indicator, switch}`; `propose_add_components(graph, base:int, definition_ids:list[str]) -> ModificationProposal` (mode `"add_component"`); route `POST /api/projects/{id}/component-proposals` body `ComponentProposalBody{baseRevision:int, componentDefinitionIds:list[str]}` → `proposal.to_dict()`, stored with `_remember_bounded(application.modification_proposals, ...)` exactly like pin-proposals.

Entity shape per added part: id `component-user-{family}-{hex8}`, `EntityKind.COMPONENT`, name = part number, metadata `{"family": family, "role": family, "component_definition_id": id, "dimensions": {"width":w,"length":l,"height":h}` (from the `dimensions` property when present, mm), `"parameters": {"component_definition_id": id, "component_definition_version": CATALOGUE_VERSION}}`. For a `SIGNAL_FAMILIES` part also: port `"{entity_id}_signal"` added to the controller's `parameters.gpio_map` with the lowest free allowed GPIO, a CONNECTION entity `connection-user-wire-{hex8}` with metadata `{source_id: controller, target_id: part, source_interface: port, target_interface: "signal", connection_type: "electrical"}` and an `"electrical"` Relationship carrying `connection_id`. Controller = the component whose `parameters.gpio_map` exists. Placement: no stored position; `engineering_assembly` lays the new part out (assert it appears in the candidate assembly). Add one verification check `{"state":"WARNING","message":"Single signal pin assigned; bus parts (I2C/SPI) need wiring review."}` when any added part is a sensor family.

- [ ] **Step 1: failing tests** in `tests/test_add_components.py` (build the fan demo graph the way `tests/test_pin_change.py` does):
  - `test_adds_one_part_and_allocates_lowest_safe_free_pin` — gpio is the minimum of `ESP32_OUTPUT_GPIOS` not in strapping and not already used.
  - `test_same_definition_twice_gets_distinct_ids_and_pins` (Review Focus 2).
  - `test_allocation_respects_pin_change` — commit a `propose_pin_change` first, then add; new pin ≠ moved pin (Review Focus 3).
  - `test_passive_part_gets_no_pin` — `resistor-4k7` adds an entity and no gpio_map entry.
  - `test_errors` — unknown id → `UNKNOWN_COMPONENT`; `[]` → `EMPTY_SELECTION`; stale base → `ValueError("stale_revision")`; signal part on a graph without controller → `NO_CONTROLLER`; filling every safe pin → `NO_FREE_PIN`.
  - API: `test_route_commit_then_undo` — POST route → 200, commit via shared route → 200, entity present; `POST /revisions/undo` → entity, connection and gpio port gone (Review Focus 4); stale `baseRevision` → 409 `stale_revision` (Review Focus 5).
  - `test_fan_firmware_still_supported_after_add` — after committing a DS18B20 add, `GET /firmware` has `supported: true` and the fanControl source unchanged (Review Focus 1).
- [ ] **Step 2:** run `python -m pytest -q tests/test_add_components.py` → FAIL (import error).
- [ ] **Step 3:** implement `propose_add_components` + route. If Review Focus 1 fails because `sketch.py` rejects extra components, fix `sketch.py` to ignore connections it has no generator for — ledger a ruling.
- [ ] **Step 4:** test file PASS; full Python suite → only the known `test_startup_boundaries` failure.
- [ ] **Step 5:** detect-changes, commit `Add catalogue parts as a verified proposal with safe pin allocation`.

### Task 3: Frontend — multi-select add flow + Code-view note

**Files:**
- Modify: `ComponentLibrary.tsx`, `WorkspaceApp.tsx`, `CodeView.tsx`, `src/aura/workspace/server.py` (firmware GET), `styles.css`
- Test: `e2e/library.spec.ts`, `tests/test_add_components.py`

**Interfaces:**
- Consumes: Task 2 route. Existing proposal card + commit flow in `WorkspaceApp` (the one used by modification proposals) — reuse it via `onProposal(proposal)`.
- Produces: firmware GET adds `addedWithoutDriver: [{semanticId, name, port, gpio}]` (controller ports whose target id starts with `component-user-`).

- [ ] **Step 1: failing tests:** pytest `test_firmware_lists_added_parts_without_driver`; e2e: tick two rows, button reads `Add 2 to design`, POST body equals `{baseRevision, componentDefinitionIds:[a,b]}`, proposal card shows both part names and their GPIOs, Commit calls the commit route; mocked 409 `NO_FREE_PIN` shows its message in `data-testid="library-error"`; Code view lists `Pin assigned — no generated driver yet`.
- [ ] **Step 2:** run both → FAIL.
- [ ] **Step 3:** implement checkboxes (`aria-label="Select {partNumber}"`), add button disabled at 0, error box, firmware field, CodeView note.
- [ ] **Step 4:** pytest + `npm test` + `AURA_E2E_MOCK_ONLY=1 npx playwright test e2e/library.spec.ts` PASS.
- [ ] **Step 5:** build, detect-changes, commit `Multi-select add from the library with proposal review`.

### Task 4: Configure a part

**Files:**
- Modify: `modifications.py`, `server.py`, `ComponentCard.tsx`, `WorkspaceApp.tsx`
- Test: `tests/test_add_components.py` (or new `tests/test_parameter_proposal.py`), `e2e/library.spec.ts`

**Interfaces:**
- Produces: `propose_parameter_change(graph, base:int, component_id:str, key:str, value:str|int|float|bool) -> ModificationProposal` — builds a `ModificationDecision(action="SET_PARAMETER", parameterKey=key, parameterValueJson=json.dumps(value), ...)` and delegates to `_set_parameter` (mode `"parameter_change"`); unknown component → `ModificationError("UNKNOWN_COMPONENT",...,404)`; stale → `ValueError("stale_revision")`. Route `POST /api/projects/{id}/parameter-proposals` body `{baseRevision, componentId, key, value}`, same error mapping as pin-proposals.
- ComponentCard: editable rows for scalar `parameters` except `component_definition_id`, `component_definition_version`, `gpio_map`; on change → `onChangeParameter(componentId,key,value)`; errors in `data-testid="param-error"`.

- [ ] **Step 1: failing tests:** valid scalar change → proposal with `replace_parameter` op; same value → `invalid_parameter_edit` 422; unknown key → 422; stale → 409. e2e: edit a parameter → POST body correct → proposal card shown.
- [ ] **Step 2–4:** FAIL → implement → PASS (pytest, npm test, mocked e2e).
- [ ] **Step 5:** build, detect-changes, commit `Configure part parameters through verified proposals`.

### Task 5: Connection tool

**Files:**
- Modify: `modifications.py`, `server.py`, `ComponentCard.tsx`, `WorkspaceApp.tsx`
- Test: `tests/test_connection_proposal.py`, `e2e/library.spec.ts`

**Interfaces:**
- Produces: `propose_connection(graph, base:int, source_id:str, source_interface:str, target_id:str, target_interface:str) -> ModificationProposal` — builds `ModificationDecision(action="ATTACH_TO_INTERFACE", targetSemanticId=target_id, referenceSemanticId=source_id, referenceInterface=source_interface, targetInterface=target_interface, ...)` and delegates to `_attach` (mode `"connection"`). Routes: `GET /api/projects/{id}/components/{componentId}/interfaces` → `[{name, kind, compatible:[...]}]` from `component_interfaces(_family, _dimensions, parameters)`; `POST /api/projects/{id}/connection-proposals` body `{baseRevision, sourceId, sourceInterface, targetId, targetInterface}`.
- ComponentCard: `Connect…` button → select this part's interface, then target component, then its interface (both `<select>` with aria-labels `Connect from interface`, `Connect to component`, `Connect to interface`) → `onConnect(...)`; errors in `data-testid="connect-error"`.

- [ ] **Step 1: failing tests:** compatible pair → proposal with `add_mechanical_attachment`; incompatible → 422 `incompatible_attachment_interfaces`; occupied → `attachment_interface_in_use`; stale → 409; interfaces route lists names. e2e: connect flow posts correct body; mocked 422 shows message.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** build, detect-changes, commit `Connection tool using interface compatibility rules`.

### Task 6: Test benches

**Files:**
- Create: `src/aura/workspace/web/frontend/src/benches.ts`, `benches.test.ts`, `TestBench.tsx`
- Modify: `ComponentCard.tsx`, `styles.css`
- Test: `benches.test.ts`, `e2e/library.spec.ts`

**Interfaces:**
- Produces: `benchKind(family:string): "ds18b20"|"fan"|null` (`temperature_sensor` with definition `ds18b20-module` → `"ds18b20"`; `fan` → `"fan"`; else `null`); `ds18b20Reading(tempC:number, connected:boolean): number` — disconnected → `-127`; clamp to `[-55,125]`; round to nearest `0.0625`. `<TestBench kind definition />` — DS18B20: slider + disconnect toggle + reading; fan: gate toggle → `Running`/`Stopped`, current shown only from catalogue `properties.current` labelled `curated estimate`, else `current not in catalogue`. Always shows `Behavioral model — not hardware`. `null` kind → `No test bench yet`.

- [ ] **Step 1: failing vitest:** `ds18b20Reading(25.03,true)===25.0`, `ds18b20Reading(25.04,true)===25.0625`, `ds18b20Reading(200,true)===125`, `ds18b20Reading(-80,true)===-55`, `ds18b20Reading(20,false)===-127`; `benchKind` cases above.
- [ ] **Step 2–4:** FAIL → implement → PASS. e2e: DS18B20 card bench shows label and reading changes with slider; resistor card shows `No test bench yet`.
- [ ] **Step 5:** build, detect-changes, docs (README + `docs/active/README.md` §0 one paragraph), commit `Behavioral test benches for DS18B20 and fan`.
