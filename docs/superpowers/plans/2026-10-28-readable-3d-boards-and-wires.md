# Readable 3D boards and pin-to-pin wires — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detailed, labelled board models with named pin anchors, cables routed pin to pin with colours and numbers, and studio lighting.

**Architecture:** Models gain invisible `pin:<name>` anchors and silkscreen text planes (`silkscreen.ts`). A pure resolver (`wiring3d.ts`) maps graph connections to anchor pairs via `gpio_map` and a per-family interface→pin table, and builds jumper curves. The scene draws these wires (recomputed on explode/isolate), number tags, hover tooltips, and falls back to dashed "approximate route" lines. Lighting uses RoomEnvironment + ACES + soft shadows + GTAOPass with automatic fallback.

**Tech Stack:** Three.js r15x (`three/examples/jsm`), React/TS, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-28-readable-3d-boards-and-wires-design.md`

## Global Constraints

- No new dependencies. No logos/trademarks.
- Pin names from `pinout.ts`; ESP32 anchors at 2.54 mm pitch, J2 left / J3 right, pin 1 at antenna end.
- Wire colours: power red `0xd23a2f`, ground black `0x1c1e20`, signal yellow `0xe8b923`, control orange `0xe07a1f`, switched load blue `0x2f6fd0`.
- Unresolvable ends → dashed line labelled "approximate route"; footer copy "Illustrative routing — not a measured cable layout".
- Silkscreen ≥ 8 px/mm; canvas text only when `document` exists (tests read `userData.text`).
- Effects off when frame time > 33 ms for 30 frames, no WebGL2, or `prefers-reduced-motion`.

## Review Focus

1. Every drawn wire end lies on its anchor in assembled and exploded views.
2. A connection whose end has no anchor is never drawn as a solid wire.
3. GPIO changes (pin picker) move the wire to the new header pin.
4. Performance: wires/labels must not break picking, selection styling or disposal (no leaks on project switch).
5. Post-processing fallback keeps rendering when GTAO fails.

---

### Task 1: Pin anchors and silkscreen on models
Files: create `src/silkscreen.ts`; modify `src/studioModels.ts`, `src/studioModels.test.ts`.
Produces: `anchor(group, name, at)`; `pinAnchors(group) -> Record<string, THREE.Object3D>`; `silkscreen(builder, lines:{text,at,size,rotate?}[], z)`.
- Failing tests: ESP32 exposes 38 `pin:*` anchors incl. `pin:IO4`, `pin:3V3`, three `pin:GND`-family names (`GND`, `GND.2`, `GND.3`); `pin:IO4` is 2.54 mm from `pin:IO16` along the header (J3 13 vs 12); DS18B20 `VCC/DAT/GND`; MOSFET `IN/VCC/GND/V+/V-/OUT+/OUT-`; relay, soil, light, PIR, LED, button, servo, fan, power, resistor, diode anchors per spec; silkscreen text objects include `ESP32-DevKitC` and `IO4`. Commit `Pin anchors and silkscreen on studio models`.

### Task 2: Wire resolver and jumper geometry
Files: create `src/wiring3d.ts`, `src/wiring3d.test.ts`.
Produces: `INTERFACE_PINS` table; `pinFor(entity, iface, gpioMap) -> string|null`; `resolveWires(graph) -> {number, connectionId, role, color, from:{part,pin}, to:{part,pin}, label}[]`; `unresolved(graph)`; `jumperCurve(a:Vector3, b:Vector3) -> CatmullRomCurve3` (rise 6 mm, arc height `clamp(dist*0.35, 12, 60)` mm).
- Failing tests: fan graph → DS18B20 `DAT` ↔ ESP32 `IO4`, VDD ↔ `3V3`, GND ↔ `GND`, MOSFET `IN` ↔ `IO16`, colours/roles, numbers 1..n stable by connection id; changing `gpio_map` moves the end to `IO17`; unknown interface → in `unresolved`, not in wires; curve starts/ends exactly at a/b and peaks above both. Commit `Resolve graph connections to pin-to-pin wires`.

### Task 3: Scene integration
Files: modify `src/WorkspaceApp.tsx` (scene: `setGraph`, `drawPinWires`, tags, hover tooltip, dashed approximate lines, explode/isolate recompute, dispose), `ComponentCard.tsx` (wire numbers in rows), `styles.css`, `e2e/studio.spec.ts`.
- Failing e2e: `window.__auraWires()` returns wires each with `distanceFromAnchor < 0.5` at both ends (assembled and exploded); hover tooltip text `1 · …`; connection rows show the same numbers; footer copy present. Commit `Pin-to-pin wires in the 3D view`.

### Task 4: Studio lighting with fallback
Files: modify `src/WorkspaceApp.tsx` (renderer setup), add `src/renderQuality.ts` + test.
Produces: `qualityFor({webgl2, reducedMotion, slowFrames}) -> "high"|"basic"`.
- Failing vitest for `qualityFor`; e2e: `window.__auraRenderQuality` is set and canvas renders (non-blank pixel check). Commit `Studio lighting with automatic fallback`.

### Task 5: Screenshot and docs
Playwright screenshot of the fan project next to the reference image saved under `workspace/screenshots/readable-3d/`; README capability bullet; docs/active §0. Commit `Document readable 3D boards and wires`.
