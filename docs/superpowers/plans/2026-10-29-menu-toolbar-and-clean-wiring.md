# Menu bar, viewport toolbar, view FAB, harness wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reference layout (menu bar, toolbar above the viewport, view FAB) and clean orthogonal numbered wiring.
**Architecture:** `harnessPath`/`assignLanes` in `wiring3d.ts` replace `jumperCurve`; the scene computes clearance from part boxes. New `MenuBar.tsx` and `ViewFab.tsx` reuse existing WorkspaceApp handlers; the engineering space gains a toolbar row and a `.viewport` wrapper.
**Spec:** `docs/superpowers/specs/2026-10-29-menu-toolbar-and-clean-wiring-design.md`

## Global Constraints
- Presentation only for the layout: no handler, state or API changes; same disabled rules and titles.
- Wire ends exactly on anchors; fillet radius 2 mm; lane step 2.5 mm; base clearance 8 mm; obstacle clearance 6 mm.
- No new dependencies.

## Review Focus
1. Keyboard: every menu, menu item, toolbar button and FAB action reachable and operable; Escape returns focus.
2. Nothing overlaps: FAB vs simulation column, library toggle, view switch, wire note, Code/Build views.
3. Existing e2e flows (spaces, explode, isolate, X-ray) still work through the new controls.
4. Harness routes never pass through a non-endpoint part's footprint below its top.
5. Narrow widths: no page-level horizontal overflow.

### Task 1: Harness routing
Files: `src/wiring3d.ts`, `src/wiring3d.test.ts`, `src/WorkspaceApp.tsx` (drawPinWires).
Produces: `harnessPath(a,b,height,radius=2) -> THREE.CurvePath<THREE.Vector3>`; `assignLanes(lengths:number[]) -> number[]` (lane index per wire, shorter first).
- Failing tests: path endpoints equal pins; sampled points are on vertical lines above a or b, or at `z=height` (outside fillets); horizontal points have x or y constant per segment; `assignLanes([30,5,12])` → `[2,0,1]`. Then scene uses lanes + obstacle clearance. Commit `Clean orthogonal harness wiring`.

### Task 2: Menu bar, viewport toolbar, view FAB
Files: create `src/MenuBar.tsx`, `src/ViewFab.tsx`; modify `src/WorkspaceApp.tsx`, `src/styles.css`, e2e specs that use the old controls; add `e2e/layout.spec.ts`.
- Failing e2e: menu opens on click, closes on Escape (focus back) and outside click; View ▸ Wiring switches view; Components ▸ Component library opens the library; FAB expands with four buttons, collapses on click/outside/Escape; Explode works from the FAB; toolbar Code/Simulation/Build switch spaces; no horizontal overflow at 1280 and 900 px. Commit `Menu bar, viewport toolbar and view FAB`.

### Task 3: Screenshot and docs
Screenshot vs reference (local), README/docs §0 line. Commit `Document menu bar and harness wiring`.
