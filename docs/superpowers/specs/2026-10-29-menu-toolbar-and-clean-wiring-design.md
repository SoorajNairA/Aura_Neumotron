# Menu bar, viewport toolbar, view FAB, and clean harness wiring — design

Date: 2026-10-29 · Branch: `AURA-nemotron_test1` · Reference: `AURA interface with streamlined toolbars.png`

## 1. Layout (presentation only)

- Top bar row 2: application menu **File, Edit, View, Project, Components, Tools, Help** replaces the space tabs.
  Items call existing handlers only:
  - File: New design, Switch project, Revision history.
  - Edit: Undo last change.
  - View: 3D view, Wiring, Split, Fit, Explode/Assemble, X-ray/Solid, Show all, Developer panel.
  - Project: Design checks (verification), Work items.
  - Components: Component library.
  - Tools: Model settings, Code (compile), Connect device.
  - Help: About AURA (version and provider text in the menu, no new dialog).
  Menus: `aria-haspopup="menu"`, `aria-expanded`, items `role="menuitem"`, close on item, outside click and Escape
  (focus returns to the trigger); ArrowDown opens, Arrow keys move between items.
- Toolbar card above the viewport: **Design, Code, Simulation, Build** on the left (same handlers, same disabled
  rules and titles, `aria-label="Workspace spaces"` kept); **Complete system** select and **Concept model** badge on
  the right. The viewport sits below the toolbar; all existing overlays keep their relative positions.
- View FAB: round button in the viewport's top-right corner (`aria-label="View controls"`, `aria-expanded`).
  Expands Fit, Explode, Solid/X-ray, Show all horizontally to the left; collapses on second click, outside click or
  Escape. Shown wherever the old canvas toolbar was shown.
- Sidebar, inspector, simulation panel, composer, palette, 3D scene and behaviour unchanged. Narrow screens: toolbar
  scrolls horizontally inside its card; menu bar wraps; no page overflow.

## 2. Clean harness wiring

- Replace the arc jumpers with orthogonal routes: vertical rise from the pin to the wire's lane height, a horizontal
  run along X, then along Y, then a vertical drop onto the other pin; corners filleted (radius 2 mm).
- Every wire gets its own lane height: `base = max(pin z) + 8 mm`, raised above any other part whose footprint the
  horizontal run crosses (part top + 6 mm), plus `lane × 2.5 mm` with lanes assigned by horizontal length (short wires
  low). No two wires share a horizontal run height.
- Number tag at the first corner; pin labels, colours, tooltip, card numbers, anchors and approximate routes unchanged.
- Ends still lie exactly on the pin anchors (tested), assembled and exploded.

## Testing

vitest: harness path starts/ends at pins, segments are axis-aligned outside fillets, horizontal parts lie at lane
height, lanes distinct and ordered by length. Playwright: menus open/close (click, outside, Escape) and run their
actions; FAB expands/collapses (click, outside, Escape) and its buttons work; space toolbar switches spaces; existing
suites updated to the new controls; wire ends within 0.5 mm.
