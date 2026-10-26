# Engineering Studio Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle and restructure the AURA workspace into the light "engineering studio" of the concept image: Design/Code/Simulation/Build spaces, grouped components with thumbnails, a pin-aware inspector, a simulation preview, and a realistic studio-lit 3D stage for the ESP32 fan workflow.

**Architecture:** Keep `WorkspaceApp.tsx` as the state owner and keep its layout regions (topbar, rail, engineering-space, inspector, dock). Pull new UI pieces into small components (`StudioRail.tsx`, `ComponentCard.tsx`, `CodeView.tsx`) fed by pure helpers in `studio.ts`. Do the 3D work inside `HolographicScene` (lighting and materials), plus a new `studioModels.ts` for the procedural part models and thumbnails.

**Tech Stack:** React 18 + TypeScript, Three.js 0.185 (`RoomEnvironment`, `RoundedBoxGeometry`), vitest, Playwright (msedge).

**Spec:** `docs/superpowers/specs/2026-10-27-engineering-studio-redesign-design.md`. Reference image: `AURA desk fan engineering studio (1).png`.

## Global Constraints

- Light theme only. Tokens are exactly spec §4: `--bg #f4f1ea`, `--surface #ffffff`, `--surface-muted #f7f5f0`, `--line #e5e0d6`, `--text #1e2722`, `--text-soft #4c5650`, `--text-dim #7a837d`, `--accent #2f5d4a`, `--accent-soft #e6efe9`, `--warn #d26a2c`, `--pass #2e8b57`, `--fail #c0392b`. Card radius 10px, control radius 8px.
- Fonts, offline only: heading `"Sitka Heading", Georgia, "Times New Roman", serif`; body `"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif`; mono `"Cascadia Mono",Consolas,monospace`.
- Disabled-feature tooltips, verbatim:
  - Build tab: "Coming next: USB upload, live telemetry"
  - Connect device: "Coming next: USB serial upload and telemetry"
  - Add component: "Coming next"
- The simulation label stays verbatim: "Behavioral simulation — control logic only. Not electrical verification, not firmware execution."
- Wire colors by net role: power `#c8372d`, ground `#1d1f21`, data/signal `#e3b505`, control `#2e8b57`.
- Keep every existing `data-testid`. Existing e2e specs change only where a visible label changes.
- The demo path must work after every commit: "Build a temperature-controlled desk fan", then Design, Simulation, Code/Compile.
- Before every commit: `npx tsc --noEmit -p .`, `npm test`, `npm run build`, then GitNexus `detect-changes`. Rebuilt `representation/` assets are committed with the source.
- Cut order if Day 2 runs late: (1) extra model detail, (2) KiCad models (procedural only), (3) thumbnails (family icons).

## Review Focus

1. **Non-fan projects** (robotic arm, an Arduino design, `build_incomplete` with 0 parts): every panel must render empty states. Grouping, connection rows, thumbnails and the preview card must not throw. Tested in Tasks 2 and 4.
2. **A component with no controller link** (fan, enclosure): the inspector shows only its real ports (rail or GND), never an invented GPIO. Tested in Task 2.
3. **Long names and many parts** (a 14-part solar tracker): the rail and inspector truncate, scroll and stay keyboard-reachable. Tested in Task 4.
4. **Revision change while on Code or Simulation**: views refresh to the new firmware and never show the old sketch as current. Tested in Task 6.
5. **WebGL context or thumbnail render failure**: thumbnails fall back to family icons and the main scene keeps working. Tested in Task 10.

---

### Task 1: Light theme foundation

**Files:**
- Modify: `src/aura/workspace/web/frontend/src/styles.css`. Replace the `:root` token blocks and the "Professional polish" block, and convert hard-coded dark colors in existing rules to tokens.

- [ ] **Step 1: Rewrite tokens and base rules.** Set the Global Constraints tokens and fonts. Set `body`/`.aura-shell` background to `var(--bg)`. Panels (`.topbar`, `.systems-rail`, `.contextual-inspector`, overlays, dialogs) use `var(--surface)` with a `1px var(--line)` border and a soft shadow (`0 1px 2px rgba(30,39,34,.06), 0 8px 24px rgba(30,39,34,.06)`). Buttons are white with a `--line` border; primary buttons are filled `--accent` with white text. Text and focus rings use the tokens. Remove `.ambient-grid`. Set `color-scheme: light`.
- [ ] **Step 2: Replace remaining dark literals.** Sweep `#0x…`/`rgba(…dark…)` backgrounds across rules for the work view, overlays, schematic chrome and the simulation panel. Keep the schematic paper (`#edf0ee`) as is.
- [ ] **Step 3: Build and screenshot.** Run `npm run build`, restart the backend, and screenshot the fan project at 1600×950. Expected: a light UI everywhere with no dark panels and readable contrast.
- [ ] **Step 4: Run the existing suites.** `npm test` (50 pass). With `AURA_E2E_MOCK_ONLY=1`, run `npx playwright test e2e/simulation.spec.ts e2e/production.spec.ts`. Expected: same pass/fail as before.
- [ ] **Step 5: Commit.** Message: `Switch workspace to the light studio theme`.

### Task 2: Studio helpers

**Files:**
- Create: `src/aura/workspace/web/frontend/src/studio.ts`, `src/aura/workspace/web/frontend/src/studio.test.ts`

**Interfaces (Produces):**
```ts
export type ComponentGroup="Controller"|"Sensors"|"Actuators"|"Power"|"Other";
export function componentGroup(family:string|undefined):ComponentGroup;
export type ConnectionRow={port:string;label:string;value:string;tone:"data"|"supply"|"ground"|"control"};
export function connectionRows(componentId:string,graph:{entities:any[]}):ConnectionRow[];
export type CheckRow={id:string;title:string;detail:string;tone:"pass"|"warn"|"fail"};
export function checksForComponent(componentId:string,findings:any[]):CheckRow[];
export function partNumber(entity:any|undefined):string;   // catalogue part number, else humanized family
export function modelBadge(project:any|undefined):string;   // "Nemotron · Nebius" | "<model> · <provider>" | "Offline fallback" | "Deterministic"
```

- [ ] **Step 1: Write the failing tests.** Build a fan graph fixture as a literal object in the test, with a controller (`gpio_map {"signal-1":4,"signal-2":16}`), a DS18B20, a driver, a fan, a pull-up and connection entities whose metadata matches the real graph: `source_id, target_id, source_interface, target_interface, connection_type`. Assert:
  - `componentGroup("microcontroller_board")==="Controller"`, `"temperature_sensor"` gives `"Sensors"`, `"mosfet_driver"` and `"fan"` give `"Actuators"`, `"low_voltage_power_source"` gives `"Power"`, `"resistor"` and `undefined` give `"Other"`;
  - `connectionRows(sensorId)` deep-equals `[{port:"signal",label:"Data (DQ)",value:"GPIO 4",tone:"data"},{port:"power",label:"Supply (VDD)",value:"3.3 V",tone:"supply"},{port:"ground",label:"Ground (GND)",value:"GND",tone:"ground"}]`;
  - `connectionRows(fanId)` has no `GPIO`;
  - `connectionRows("missing")` returns `[]`;
  - `checksForComponent` maps finding state `passed`/`source_verified` to pass, `estimated`/`conceptual` to warn, `failed` to fail, and keeps only findings whose `entity_ids` or `semanticIds` include the id;
  - `modelBadge({planningMode:"live_model",assessment:{planningOrigin:{provider:"nebius",model:"nvidia/nemotron-3-super-120b-a12b"}}})==="Nemotron · Nebius"`;
  - `modelBadge({planningMode:"deterministic_fallback"})==="Offline fallback"`.

  First read the real shapes from `GET /api/projects/{id}` and `/verification` on the live fan project, and use those field names.
- [ ] **Step 2: Run them.** `npx vitest run src/studio.test.ts`. Expected: FAIL, module missing.
- [ ] **Step 3: Implement.** Port labels come from the counterpart:
  - controller `signal-*` edge to a sensor: "Data (DQ)" for a DS18B20, otherwise "Signal";
  - edge to a driver: "Gate (IN)";
  - `regulated-power` from `vcc-out`: "Supply (VDD)" with `3.3 V` when the controller `logic_voltage_v` is 3.3;
  - `power` from the source: its `voltage_v`;
  - ground: "Ground (GND)".
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `Add studio helpers for grouping, pin rows and checks`.

### Task 3: Top bar and space tabs

**Files:**
- Modify: `src/aura/workspace/web/frontend/src/WorkspaceApp.tsx`:
  - `ViewMode` adds `"code"|"build"`;
  - the topbar JSX (lines ~224–234);
  - the tabs (~229).
- Modify: `styles.css`. Modify e2e specs that click old tab labels.

**Interfaces:** `space(mode)`: `assembly|schematic|split` map to `"design"`; `code`, `simulation` and `build` map to themselves; `work` maps to `"design"` (Work opens from settings).

- [ ] **Step 1: Write the failing e2e test** `e2e/studio.spec.ts`, reusing the `mock` from `simulation.spec.ts` (copy the fan fixtures). Assert:
  - buttons "Design", "Code" and "Simulation" exist; "Build" is disabled and its title matches the verbatim text; "Connect device" is disabled with its tooltip;
  - the model badge shows "Nemotron · Nebius" (mock project assessment origin) and the breadcrumb shows "Workspace";
  - clicking "Code" shows test id `code-view`;
  - inside Design, the "3D view", "Wiring" and "Split" buttons switch: Wiring shows test id `schematic`.
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement the topbar.**
  - Brand mark plus breadcrumb `Workspace / {projectName}` (keep the project-switch button as the breadcrumb target).
  - `Saved · rev N`.
  - The model badge from `modelBadge(project)`.
  - A settings menu button replacing the `•••` icon, with items "Work items" (`setMode("work")`), "Verification details" (`setOverlay(true)`) and "Developer panel".
  - Disabled "Connect device".
  - Space tabs Design/Code/Simulation/Build.
  - A view switch (`3D view`/`Wiring`/`Split`) floating at the bottom-center of the stage in the Design space.
  - A stage toolbar with an "Assembly" dropdown (Complete system plus each subsystem, using the existing `isolate`), a status badge from the representation status (e.g. "Concept model"), Fit and Explode.
  - Keep the `verify-status` button reachable: move it into the left checks card (Task 4), and keep `aria-label="VERIFICATION AND ASSESSMENT"` on it.
- [ ] **Step 4: Update existing e2e labels.** `SCHEMATIC` becomes `Wiring`, `SPLIT` becomes `Split`, `WORK` becomes settings then "Work items", `SIMULATION` becomes `Simulation`. Run the full browser suite. Expected: 43+new pass, with only the 6 baseline failures.
- [ ] **Step 5: Commit.** Message: `Add studio top bar, space tabs and design view switch`.

### Task 4: Component rail

**Files:**
- Create: `src/aura/workspace/web/frontend/src/StudioRail.tsx`
- Modify: `WorkspaceApp.tsx` (replace the `.rail-content` contents, ~line 238–239), `styles.css`

**Interfaces:**
- Consumes: `componentGroup`, `partNumber`.
- Produces: `<StudioRail projectName objective parts:Part[] graph selected onSelect(id) checksCount onOpenChecks thumbnails?:Record<string,string>/>`.
- Test ids: `rail-search`, `rail-group-<Group>`, `checks-card`.

- [ ] **Step 1: Write the failing e2e tests** in `studio.spec.ts`:
  - the rail shows the "ENGINEERING PROJECT" kicker and the project name as a heading;
  - groups Controller(1), Sensors(1) and Actuators(2) appear in order, each with a count;
  - typing "fan" in `rail-search` leaves only "Desk fan";
  - clicking a row selects it (`data-testid="selected"` equals its id);
  - "Add component" is disabled;
  - `checks-card` text matches `/\d+ checks? need attention/` and clicking it opens the verification overlay;
  - a mock project with 0 parts shows "No components yet" and nothing throws;
  - a 14-part mock (reuse the long fixture pattern) scrolls inside the rail.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** with family icons as thumbnails for now (Task 10 replaces them). Keep the existing isolate behavior in each row's overflow menu.
- [ ] **Step 4: Run the tests and the full e2e suite.** Expected: new tests pass, only baseline failures.
- [ ] **Step 5: Commit.** Message: `Add grouped component rail with search and checks card`.

### Task 5: Inspector card and simulation preview

**Files:**
- Create: `src/aura/workspace/web/frontend/src/ComponentCard.tsx`
- Modify: `WorkspaceApp.tsx` (the `inspectorMode==="component"` section, ~line 258), `SimulationPanel.tsx`, `styles.css`

**Interfaces:**
- Consumes: `connectionRows`, `checksForComponent`, `partNumber`.
- Simulation state moves up into WorkspaceApp: `simTemperature`, `simFault`. `SimulationPanel` gains the props `temperature`, `onTemperature`, `fault`, `onFault`, plus a new `compact?:boolean` mode used by the preview card. Test ids: `sim-preview`, `connection-rows`, `component-checks`.

- [ ] **Step 1: Write the failing e2e tests:**
  - select the DS18B20 mock part: `connection-rows` contains "GPIO 4" and "3.3 V", and `component-checks` shows a pass row with "Pin assigned";
  - select the fan: no "GPIO";
  - "Show connections" focuses the part's wires (existing `setFocus`);
  - `sim-preview` is visible on the fan project; setting its slider to 27 shows "Fan on", and switching to the Simulation tab shows `sim-temperature` value 27 and state ON;
  - on an unsupported mock, `sim-preview` is absent.

  Add the mock graph connection entities needed for this.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** the card from spec §3.4. Keep the existing component actions (What-If, Show in schematic) below the card. "Pin assigned · Connected to GPIO n" is a derived pass row when the part has a GPIO in `gpio_map`. This is the only derived check; all other rows come from findings.
- [ ] **Step 4: Run the tests and the full e2e suite.**
- [ ] **Step 5: Commit.** Message: `Add pin-aware inspector card and shared simulation preview`.

### Task 6: Code space

**Files:**
- Create: `src/aura/workspace/web/frontend/src/CodeView.tsx`
- Modify: `WorkspaceApp.tsx` (render it when `mode==="code"`), `SimulationPanel.tsx` (remove the compile section and add a "Compile in Code" link), `styles.css`, and `e2e/simulation.spec.ts` (move the compile test to the Code tab)

**Interfaces:** `<CodeView firmware:FirmwareInfo compile:()=>Promise<CompileInfo>/>`. Test ids: `code-view`, `code-source` (with line numbers), `fw-status`, plus the pin table and libraries.

- [ ] **Step 1: Write the failing e2e tests:**
  - the Code tab shows the sketch with a line-number gutter, the pin table rows "DS18B20 data · GPIO4" and "MOSFET gate · GPIO16", the libraries and the FQBN;
  - COMPILE shows "Toolchain missing: arduino-cli" (mocked), and the stale notice works as before;
  - an unsupported mock shows the reasons list instead of code;
  - Review Focus 4: after a mocked revision change (the project revision bumps and `/firmware` returns a new `revisionId`/`source`), the Code view shows the new source and no "Compiled for ESP32" status for the old revision.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Move the compile state out of SimulationPanel into CodeView unchanged.
- [ ] **Step 4: Run the tests and the full e2e suite.**
- [ ] **Step 5: Commit.** Message: `Add Code space with sketch, pins and compile`.

### Task 7: Composer restyle

**Files:**
- Modify: `WorkspaceApp.tsx` (`.command.dock` ~line 273, narration ~272), `styles.css`

- [ ] **Step 1: Restyle the dock as the "Build it together" card**, with a heading, the subline "Your concept is ready. What would you like to refine?", an input placeholder "Ask AURA to change your design…" and a green send button labeled "Preview" (accessible name kept). Behavior is unchanged. The narration chip sits above it.
- [ ] **Step 2: Update e2e placeholder selectors** if any spec uses the old placeholder text. Run the full e2e suite. Expected: only the baseline failures.
- [ ] **Step 3: Commit.** Message: `Restyle command dock as Build it together composer`.

### Task 8: Studio stage — lighting, materials, wires

**Files:**
- Modify: `WorkspaceApp.tsx`, `HolographicScene`: the constructor (~line 64), `mat()`, the wire build code and the background/grid.

- [ ] **Step 1: Run impact** on `HolographicScene`. It is a TS class, so if the index can't resolve it, confirm with grep. Record the risk.
- [ ] **Step 2: Implement the stage:**
  - `scene.background` becomes a warm `#efebe3` (CanvasTexture vertical gradient `#f6f3ed`→`#e9e4da`);
  - `renderer.toneMapping=THREE.ACESFilmicToneMapping`, `toneMappingExposure=1.0`;
  - `scene.environment = pmrem.fromScene(new RoomEnvironment(),0.04).texture`;
  - one directional key light casting PCF soft shadows (map 2048);
  - a ground `ShadowMaterial` plane (opacity .18), with the existing grid removed or faded to opacity .06;
  - `mat()` returns `MeshPhysicalMaterial` driven by a material-kind table (`pcb`, `pad`, `shield`, `plastic`, `heatsink`, `terminal`, `fanBody`, `fanBase`), keeping its old signature for existing callers;
  - wires use the Global Constraints colors keyed on net role.
- [ ] **Step 3: Check it visually.** Screenshot the fan project, robotic arm and solar tracker (mock fixtures in `production.spec.ts`). Expected: a light studio look, readable parts, no black scene.
- [ ] **Step 4: Run** `npm test` and the full e2e suite (the `__auraSceneMetrics` assertions must still pass).
- [ ] **Step 5: Commit.** Message: `Studio lighting, materials and role-colored wires`.

### Task 9: Realistic fan-workflow models

**Files:**
- Create: `src/aura/workspace/web/frontend/src/studioModels.ts`
- Modify: `HolographicScene.model()`, which delegates to `studioModels` for the matching families/templates and keeps today's code as the fallback for everything else.

**Interfaces:** `export function buildStudioModel(part:Part,material:(kind:string)=>THREE.Material):THREE.Group|null`. It returns null for unsupported families. Fan models must contain a child named `fan-rotor` that rotates about the fan axis.

- [ ] **Step 1: Write the failing unit test** `studioModels.test.ts` (vitest; three runs in node). For each fan part (ESP32 `visual_template:"esp32_devkit"`, DS18B20, mosfet module, fan, power module, resistor, diode), `buildStudioModel` returns a group that is non-null and non-empty. The bounding box must stay within ±15% of the part `dimensions` (or the documented real size for the ESP32 at 28×52×12). `fan.getObjectByName("fan-rotor")` exists and has 9 blades. A servo returns `null`.
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Build the models** from spec §5:
  - ESP32: PCB, WROOM shield and antenna strip, 2×19 header pins, micro-USB, EN/BOOT buttons;
  - MOSFET module: PCB, TO-220 with finned heatsink, blue 2-pole terminal;
  - fan: rounded-square sage housing, grille ring, 9 twisted blades in `fan-rotor`, cream base and button;
  - DS18B20: a TO-92 half-cylinder on a small breakout with 3 legs;
  - power module: PCB plus USB-C;
  - resistor and diode: axial bodies with bands.
- [ ] **Step 4: Run** the unit test, then screenshot against the concept and adjust proportions and colors once.
- [ ] **Step 5: Run** the full e2e suite. Simulation spin must still pass with the new rotor.
- [ ] **Step 6: Commit.** Message: `Realistic procedural models for the ESP32 fan workflow`.

### Task 10: Thumbnails

**Files:**
- Create: `src/aura/workspace/web/frontend/src/thumbnails.ts`
- Modify: `StudioRail.tsx`, `ComponentCard.tsx` (use the thumbnails), `WorkspaceApp.tsx`

**Interfaces:** `export function renderThumbnails(parts:Part[],build:(p:Part)=>THREE.Object3D|null):Promise<Record<string,string>>`. It returns data URLs keyed by family or template, uses one shared offscreen `WebGLRenderer` (128×128, alpha, studio environment), and disposes it afterwards.

- [ ] **Step 1: Write the failing e2e tests:**
  - on the fan project, every rail row's `img` has a `data:image/png` src;
  - with `window.__auraDisableThumbnails=true` (injected via `addInitScript` to simulate a render failure), rows show family icons and the 3D canvas still renders (`__auraSceneMetrics().triangles>0`).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Catch any renderer error and return `{}`; the rail falls back to icons.
- [ ] **Step 4: Run the tests, `npm test` and the full e2e suite.**
- [ ] **Step 5: Commit.** Message: `Render component thumbnails from the 3D models`.

### Task 11: KiCad model gate (optional, cut item 2)

**Files:**
- Create (only if the gate passes): `src/aura/workspace/web/frontend/public/models/*.glb`, `docs/third-party-notices.md`

- [ ] **Step 1: Check the license live.** Use WebFetch on the KiCad `kicad-packages3D` license page. Record the license text and the exception. **Ruling gate:** if the license is not CC-BY-SA 4.0 with the design exception, or if converting to GLB under 300 KB takes more than 1 hour, ledger a ruling, skip this task and keep the procedural parts.
- [ ] **Step 2: If it passes,** convert TO-92, pin header 1×19, terminal 2P 5.08 mm and USB-C to GLB with the repo's opencascade or FreeCAD, and load them through `GLTFLoader` in `studioModels.ts`. The procedural part stays as a fallback while loading or on error.
- [ ] **Step 3: Write the notices file,** then run the full verification and commit. Message: `Use KiCad 3D models for small parts`.

### Task 12: Final verification and handoff

- [ ] **Step 1: Run the full suites.**
  - Python: `.venv/Scripts/python.exe -m pytest -q --ignore=tests/test_runtime_optimizations.py --ignore=tests/test_xtts_backend.py`, with `AURA_ARDUINO_CLI` set. Expected: 422 pass, 1 pre-existing failure.
  - `npm test`.
  - The full Playwright suite, with `.venv/Scripts` on PATH. Expected: only the 6 baseline failures.
- [ ] **Step 2: Live demo path in Electron** (`AURA_PROJECT_ID` set to the fan project). Screenshot Design, Code (after COMPILE passes) and Simulation, and compare with the concept image.
- [ ] **Step 3: Update docs.** Add status, screenshots and commands to `docs/active/README.md` §0, then commit.
