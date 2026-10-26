# AURA Engineering Studio Redesign (Concept B, Light Theme)

**Date:** 2026-10-27 · **Status:** approved design, awaiting spec review · **Branch:** `AURA-nemotron_test1`
**Reference concept:** `AURA desk fan engineering studio (1).png` (repo root).
**Deadline context:** Nebius hackathon submission 2026-10-30 17:00 UTC. The demo path (Build a temperature-controlled desk fan → Design → Simulation → Code/Compile) must never break; commits stay demoable.

## 1. Goal

Restyle and restructure the workspace to match the concept: a light, warm "engineering studio" with Design / Code / Simulation / Build spaces, a grouped component list with thumbnails, a pin-aware inspector, a simulation preview, a "Build it together" composer, and a realistic, studio-lit 3D stage for the ESP32 fan workflow. It reuses the existing graph, verification, firmware, compile and simulation behavior. The redesign adds no new engineering claims.

## 2. Decisions

| Decision | Choice |
|---|---|
| Scope | Concept B: layout, theme and realistic 3D models with thumbnails |
| Theme | Light only. The dark theme is removed, not kept as a toggle. |
| 3D realism | Hybrid: procedural Three.js for large parts, plus open KiCad 3D models for small parts (converted once to GLB), studio lighting and PBR materials |
| Model switching | Deferred. A read-only badge for now; the full feature is the last item, done only if time remains |
| Unbuilt features | Shown disabled and labeled "coming next" (Build tab, Connect device, Add component, model picker) |

## 3. Layout

### 3.1 Top bar
- Left: the AURA mark, then a breadcrumb `Workspace / <project name>`.
- Right:
  - the save state, `Saved · rev N` (from the current revision);
  - a read-only model badge, `Nemotron · Nebius`, showing the provider and model from the project's planning provenance, or "Offline fallback" when that applies;
  - a settings button that opens a menu: Work items (today's Work view), Developer panel, Verification details;
  - a **Connect device** button, disabled, with the tooltip "Coming next: USB serial upload and telemetry".

### 3.2 Space tabs
`Design · Code · Simulation · Build`
- **Design:** today's assembly view. A floating switch under the stage, `3D view · Wiring · Split`, maps to today's assembly / schematic / split modes. Toolbar: Assembly dropdown (whole system or a subsystem, reusing isolate), a status badge (e.g. "Concept model", from the representation status), Fit and Explode.
- **Code:** the generated sketch (monospace, line numbers), the pin table, the libraries and the FQBN, with **Compile** and its status (moved from the Simulation panel). Unsupported designs show the reasons instead.
- **Simulation:** today's SimulationPanel beside the 3D view, with the behavioral label kept verbatim.
- **Build:** disabled, tooltip "Coming next: USB upload, live telemetry".

### 3.3 Left panel
- An "ENGINEERING PROJECT" kicker, the project name as a large serif heading, and the objective as the subtitle.
- `COMPONENTS <count>` with a search box. Groups: **Controller, Sensors, Actuators, Power, Other**, each showing a count. A part's group comes from its family:
  - Controller: `microcontroller_board`
  - Sensors: the `*_sensor` families
  - Actuators: fan, servo, motor, pump, and also drivers
  - Power: the power source
  - Other: everything else, including passives and structure
- A part row shows a thumbnail, the name, the part number (or the family when the part isn't from the catalogue) and an overflow menu (Isolate / Show in 3D / Show in wiring).
- **Add component:** disabled, "coming next".
- A **"N checks need attention"** card (warning tone) opens today's verification overlay; N = blocking plus warning findings.

### 3.4 Right inspector (selected component)
- A header with the name, part number, a role chip, a one-line description and a large thumbnail.
- **Connection:** one row per electrical port, read from graph connections:
  - controller-linked ports show `GPIO <n>` from `gpio_map`;
  - the rail port shows its supply (e.g. `3.3 V` from `vcc-out`, otherwise the source voltage);
  - ground shows `GND`.
  - These rows are read-only in this phase.
- **Design checks:** this component's findings. Pass is green ("Pin assigned · Connected to GPIO 4"); estimated or unverified is orange (e.g. "Physical wiring unverified"); failed is red.
- **Show connections:** highlights this part's wires in 3D.
- A **Simulation preview** card at the bottom, on supported designs only: a compact slider, the fan status and the threshold note. It shares its state with the Simulation tab.

### 3.5 Composer
Today's command dock, restyled as "Build it together" ("Your concept is ready. What would you like to refine?"). Its behavior (modification proposals, preview, apply) is unchanged.

## 4. Theme

- **Tokens:**
  - `--bg` #f4f1ea, `--surface` #ffffff, `--surface-muted` #f7f5f0, `--line` #e5e0d6;
  - `--text` #1e2722, `--text-soft` #4c5650, `--text-dim` #7a837d;
  - `--accent` #2f5d4a (deep green), `--accent-soft` #e6efe9;
  - `--warn` #d26a2c, `--pass` #2e8b57, `--fail` #c0392b.
- Radius 10px for cards, 8px for controls. Soft shadows.
- **Fonts** (all offline):
  - headings: `"Sitka Heading", Georgia, "Times New Roman", serif`;
  - body: `"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif`;
  - mono: `"Cascadia Mono", Consolas, monospace`.
- Contrast is at least 4.5:1 for body text, focus rings are visible, and `prefers-reduced-motion` is honored.

## 5. 3D stage

- **Background and lighting:**
  - a warm light gradient background and a light ground plane with a soft contact shadow;
  - `RoomEnvironment` from three/examples for image-based lighting, `ACESFilmicToneMapping`, sRGB output;
  - shadows on the key light only.
- **Materials:** PCB solder mask (green, clearcoat), gold or tin pads, a brushed-metal RF shield, matte black plastic, a black anodized heatsink, a blue terminal block, a sage-green fan housing, cream ABS for the fan base.
- **Fan-workflow models:**

  | Part | How it is built |
  |---|---|
  | ESP32 DevKit | Procedural: PCB, WROOM shield and antenna, 2×19 headers, micro-USB, buttons |
  | Logic-level MOSFET module | Procedural: PCB with heatsink fins and the screw terminal |
  | Desk fan | Procedural: rounded square housing, grille ring, 9 curved blades on a named `fan-rotor` group, cream base, button |
  | DS18B20 | KiCad TO-92 body on a small breakout, or procedural |
  | Resistor / diode | KiCad axial models, or procedural |
  | Pin headers / screw terminal / USB-C | KiCad models, or procedural |
  | 5 V USB-C power module | Procedural board plus a KiCad USB-C model |

- **KiCad models:** used only after their license is verified (expected CC-BY-SA 4.0 with the KiCad design exception), and credited in `docs/third-party-notices.md`. They are converted to GLB once (repo opencascade or FreeCAD), stored under `src/aura/workspace/web/frontend/public/models/`, and kept under 300 KB each. If the license or conversion fails, the procedural version ships.
- **Wires:** colored by net role: power red, ground black, data yellow, control green. The existing graph-derived routes are kept, with a rounded tube.
- **Other designs** keep today's proxy geometry, re-lit and re-materialed.
- **Thumbnails:** each family's model is rendered offscreen once (transparent background, fixed 3/4 camera), cached as data URLs per family, and used in the left list and the inspector.
- **Simulation spin:** the existing `setSpinning` keeps working with the new rotor.

## 6. Honesty rules

- Disabled features never look active, and their tooltips say "coming next".
- The "Concept model" and representation badges keep today's honest status wording. A realistic render is not verification; the inspector checks stay finding-based.
- The model badge shows the real provider and model of the project's planning run, or "Offline fallback". It never shows a fixed label.

## 7. Testing

- **Unit (vitest):**
  - `componentGroup(family)` mapping;
  - `connectionRows(component, graph)`: GPIO, rail and GND from the fan graph fixture;
  - `checksForComponent`: tone mapping.
- **Browser (Playwright):**
  - existing specs are updated to the new labels (`DESIGN`/`Design`, `Wiring`, `Split`, the Work item in settings), with test ids kept;
  - new tests: the space tabs switch views; the Build tab and Connect device are disabled with their reasons; the inspector shows `GPIO 4` and `3.3 V` for the DS18B20; the checks card opens the verification overlay;
  - the simulation preview card and the Simulation tab stay in sync.
- **Visual:** screenshots of Design, Code and Simulation compared by eye against the concept at each milestone.
- **Regression:** the full Python suite, frontend unit tests, and the full browser suite compared with the current baseline (43 passed / 6 pre-existing failures).

## 8. Schedule and cut line

- **Day 1:** sections 3, 4 and 6 (layout, theme, panels, tabs).
- **Day 2:** section 5 (lighting, materials, models, thumbnails).
- **Day 3 AM:** polish and the full test run. **PM:** buffer.
- **Cut order:**
  1. extra model detail;
  2. KiCad models (procedural only);
  3. thumbnails (family icons instead).
- Model switching (deferred) starts only after Day 3 tests are green.

## 9. Out of scope

Model switching (until the end), editing pins from the inspector, upload, telemetry, digital twin, a dark theme, and new engineering checks.
