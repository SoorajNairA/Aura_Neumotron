# Layout clean-up, real File menu, editable Wiring view — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reference layout (☰ before File, view switch in viewport corner, toasts, full-height sidebars), File menu with real save/open/copy/import/export, and a wiring view where parts and wire bends can be dragged, renamed, undone and saved.
**Architecture:** Server gains a `schematic_layouts` store, layout GET/PUT, ZIP export/import and copy, all reusing `graph_to_dict`/`graph_from_dict`, `save_commit` and `RepresentationService.persist_specs`. Front end gains a pure `wiringLayout.ts` (apply layout to circuit JSON + undo/redo reducer), a `FileMenu`/`OpenDialog`, and a `Toast`; the schematic viewer stays read-only and receives circuit JSON with the layout already applied — dragging is our own pointer handling.
**Tech Stack:** FastAPI + SQLite/Postgres, Python `zipfile`; React/TS, `@tscircuit/schematic-viewer` 2.0.76, vitest, Playwright (msedge).
**Spec:** `docs/superpowers/specs/2026-10-29-layout-file-menu-wiring-edit-design.md`

## Global Constraints
- Branch `AURA-nemotron_test1`; never main. GitNexus impact before editing a symbol; detect-changes before each commit.
- ZIP never contains API keys, model profiles, env values or logs. Import limit 20 MB; only known paths; `../` and absolute paths rejected.
- Electrical connections never change from wiring-view edits; internal ids and pin identities never change on rename.
- Shareable link: disabled menu row, title "Sharing needs a hosted server with access control; not available in this build".
- Toast auto-dismiss 6000 ms, `role="status"`, close button `aria-label="Dismiss notification"`.
- Layout autosave 1000 ms after the last edit. ZIP `manifest.json` `{format:"aura-project",version:1,...}`.
- Keep ivory/sage styling tokens already in `styles.css`; no new dependencies.
- After front-end changes: `npm run build` (bundle is committed under `src/aura/workspace/web/representation/`).

## Review Focus
1. Import of a hostile ZIP (path traversal, huge member, bad JSON, wrong version) → clear 4xx code, nothing written.
2. Switching project with unsaved layout edits → Save/Discard/Cancel prompt; Cancel keeps the user where they were.
3. Regeneration after a graph change → layout entries for parts/wires that still exist re-applied; others pruned, no crash.
4. Dragging a part in Select mode never pans; Pan mode never moves parts; keyboard users can still reach every control.
5. Toast never covers the view switch, FAB or composer; sidebars scroll independently at 900 px height and 1280 px width.

---

### Task 1: Layout clean-up
**Files:** `src/WorkspaceApp.tsx`, `src/MenuBar.tsx`, create `src/Toast.tsx`, `src/styles.css`, `e2e/layout.spec.ts`, specs that click View/Components/Tools menus or the old switch.
**Produces:** `MenuBar` prop `leading?:Menu` rendered before the first menu with trigger `aria-label="Open component library"`, label "☰"; `<Toast message={string|undefined} onDismiss/>`.
- [ ] Failing e2e (layout.spec): ☰ trigger is the first button in "Application menu" nav and its menu has items Component library, Fit, Explode, X-ray, Show all, Developer panel, Model settings, Code and compile, Connect device; menubar has exactly File, Edit, Project, Help after it; the "Design view" group sits inside `.viewport` within 80 px of its top-left; `.narration-card` count 0; after a narration/status change a `role=status` toast appears and is gone after Dismiss click and after 6.5 s; left rail and inspector bottoms equal window height (±2 px) and their content has `overflow-y:auto`; welcome screen after File ▸ New shows no "BUILDING" text.
- [ ] Run `npm run build; $env:AURA_E2E_MOCK_ONLY=1; npx playwright test e2e/layout.spec.ts --reporter=line` → FAIL on the new assertions.
- [ ] Implement: ☰ becomes MenuBar `leading` menu (Component library item keeps `aria-expanded`-tracked library toggle; existing tests that click "Open component library" now open ☰ then the item — update them); move the view switch into the old ☰ spot; drop View/Components/Tools menus; replace narration card with Toast fed by the newest narration id or status change; `resetWorkspace` also clears `status`; CSS: rails `height: calc(100vh - header)`, `overflow-y:auto` on content; composer stays in the centre column.
- [ ] Re-run layout.spec + `npx playwright test e2e/studio.spec.ts e2e/production.spec.ts e2e/library.spec.ts --reporter=line` → PASS (except known OPEN clash); `npm test` → PASS.
- [ ] Commit `Layout: hamburger in menu bar, view switch in viewport, toasts, full-height sidebars`.

### Task 2: Server — layout store, export, import, copy
**Files:** `src/aura/infrastructure/persistence/project_repository.py`, `postgres_repository.py`, `src/aura/workspace/server.py`, create `src/aura/workspace/project_package.py`, `tests/test_project_package.py`.
**Produces (HTTP):**
- `GET /api/projects/{id}/layout` → `{layout:{parts:{},wires:{},labels:{}},updatedAt|null}`; `PUT` same body → 200 `{updatedAt}`; 422 on non-object fields.
- `GET /api/projects/{id}/export` → `application/zip`, `Content-Disposition: attachment; filename="aura-<slug>.zip"`.
- `POST /api/projects/import` (raw body `application/zip`) → 201 project payload; errors 400 `{detail:{code,message}}` with codes `NOT_A_ZIP`, `NOT_AN_AURA_PROJECT`, `UNSUPPORTED_VERSION`, `UNSAFE_PATH`, `TOO_LARGE`, `CORRUPT_GRAPH`.
- `POST /api/projects/{id}/copy` → 201 project payload of the new project.
**Produces (Python):** `project_package.build_zip(application, project_id) -> bytes`; `project_package.read_zip(data: bytes) -> PackageContents` (validated, raises `PackageError(code,message)`); `WorkspaceApplication.restore(contents, origin:"imported"|"copied") -> StoredProject` (new id `project-<uuid hex>`, graph id rewritten, `save_commit`, `persist_specs`, layout/control rules/firmware edit restored).
- [ ] Failing pytest: layout PUT/GET round-trip and 404 for unknown project; export of the fan fixture project contains `manifest.json`, `graph.json`, `project.json`, `layout.json`, `firmware/main.ino` (when firmware supported) and no string matching the configured API key or `api_key`; import of that ZIP gives a new id whose `graph_to_dict` entities/relationships equal the original's (ids compared after project-id rewrite) and same layout; copy ditto; each bad-ZIP code above triggered by a crafted ZIP; 21 MB body → `TOO_LARGE`.
- [ ] Run `python -m pytest -q -p no:cacheprovider tests/test_project_package.py` → FAIL.
- [ ] Implement: `schematic_layouts` table (migration + fresh schema + Protocol + Postgres) copying `control_rules`; package module; endpoints.
- [ ] Re-run the new tests and the full Python suite (command in project memory) → PASS.
- [ ] Commit `Project ZIP export/import, copy, and saved wiring layout`.

### Task 3: File menu
**Files:** create `src/FileMenu.tsx` (menu content + `OpenDialog`), `src/MenuBar.tsx` (separator, shortcut hint, submenu support), `src/WorkspaceApp.tsx`, `src/styles.css`, `e2e/file-menu.spec.ts` (mocks for the Task 2 endpoints).
**Consumes:** Task 2 endpoints. **Produces:** `MenuItem` gains `shortcut?:string`, `separatorBefore?:boolean`, `items?:MenuItem[]` (submenu opens on hover/ArrowRight, closes on ArrowLeft/Escape).
- [ ] Failing e2e: File menu rows New, Open Ctrl+O, Save Ctrl+S, Make a copy, Export ▸ (Project ZIP, Shareable link disabled with the constraint title), Import ▸ (Project ZIP…), Save local copy; Ctrl+O opens dialog "Open project" with search filtering the mocked list and a "Create new project" row; Save calls layout PUT and shows "Saved" toast; Make a copy POSTs copy and navigates to the new id; Export triggers a download named `aura-*.zip`; Import with a mocked 400 `UNSUPPORTED_VERSION` shows its message; with unsaved layout edits, Open ▸ other project shows Save/Discard/Cancel and Cancel keeps the current project.
- [ ] Run it → FAIL. Implement. Re-run + layout.spec → PASS. Commit `File menu: new, open, save, copy, import, export`.

### Task 4: Editable wiring view
**Files:** create `src/wiringLayout.ts`, `src/wiringLayout.test.ts`; modify `SchematicViewport` in `src/WorkspaceApp.tsx` (or extract to `src/SchematicEditor.tsx`), inspector rename field, component list + 3D label overrides; `e2e/wiring-edit.spec.ts`.
**Consumes:** Task 2 layout endpoints; Task 3 Save hook (`flushLayout(): Promise<void>` and `layoutDirty: boolean` exposed from the editor state).
**Produces:** `type WiringLayout={parts:Record<string,{dx:number;dy:number}>;wires:Record<string,number[]>;labels:Record<string,string>}`; `applyLayout(circuit:any[],layout:WiringLayout,mapping:Record<string,string>)->any[]` (moves `schematic_component` center and its `schematic_port`s by the part offset, moves trace edge endpoints attached to moved ports, shifts each trace segment i perpendicular by `wires[id][i]`, keeping segments orthogonal and connected, replaces component display names with labels); `layoutReducer(state,{type:"move"|"bend"|"rename"|"undo"|"redo"|"load"|"prune",...})`; `pruneLayout(layout, partIds:Set<string>, wireIds:Set<string>)`.
- Wire id: the graph connection id carried on the circuit's `aura_electrical_connection`/trace record when present, else `schematic_trace_id`.
- Drag: Select mode — pointerdown on a component (`data-schematic-component-id`) starts a part drag; on a trace path selects the wire and shows segment midpoint handles; Pan mode or Space held — pans. Convert screen delta to circuit units via the rendered SVG's `getScreenCTM()` inverse combined with the camera zoom.
- [ ] Failing unit tests: move shifts component, its ports and attached trace endpoints by (dx,dy); bend of segment 1 by +2 keeps the trace connected and orthogonal; rename sets the component name only (ids unchanged); undo/redo order; prune drops unknown ids.
- [ ] Failing e2e: Select/Pan toggle present; dragging a component in Select changes its rendered position and not `data-camera`; Pan drag changes `data-camera` and not the component; selecting a wire shows handles and dragging one moves that segment; rename in inspector shows in schematic, component list and inspector title; Ctrl+Z / Ctrl+Shift+Z undo/redo; reload restores positions/bends/labels from mocked layout GET; layout PUT sent ≤1.5 s after the last edit.
- [ ] Run → FAIL. Implement. Re-run unit + e2e + layout/file-menu specs → PASS; `npm run build`.
- [ ] Commit `Editable wiring view: drag parts and wire bends, rename, undo, saved layout`.

### Task 5: Docs
README + `docs/active/README.md` line for the new behaviour and the limitations list from the spec. Commit `Document file menu and wiring editing`.
