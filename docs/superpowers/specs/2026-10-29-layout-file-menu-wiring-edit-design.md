# Layout clean-up, real File menu, editable Wiring view — Design

Date: 2026-10-29 · Branch: AURA-nemotron_test1 · Deadline: 2026-10-30 17:00 UTC
Reference: user screenshot (crossed-out View/Components/Tools, hamburger arrow, revision banner) and File dropdown image.

## Scope (agreed order)
1. Layout clean-up.
2. File menu with real actions.
3. Editable Wiring view, reduced: drag parts, drag wire bends, rename, saved layout, undo/redo.
   Out of scope now (listed as limitations): reconnecting wire endpoints between pins, firmware pin sync from the wiring view,
   shareable URLs (no sharing server with access control exists).
Also: the welcome screen shows a stale "BUILDING 3D..." status before anything is typed — clear status on New design.

## 1. Layout
- Component-library toggle (☰) moves out of the viewport to the menu bar, immediately before File. Same handler, same aria.
- The 3D view / Wiring / Split switch moves to the toggle's old spot (viewport top-left). The bottom/top floating copy is removed.
- Menus View, Components, Tools are removed. Their useful items move into the ☰ menu, which now opens a small menu:
  Component library, Fit, Explode/Assemble, X-ray/Solid, Show all, Developer panel, Model settings, Code and compile, Connect device.
  (3D view/Wiring/Split are already on the switch.) Menu bar keeps File, Edit, Project, Help.
- The persistent narration card on the canvas is removed. New narrations (and status messages that were shown there)
  appear as a toast: bottom-left of the viewport, auto-dismiss after 6 s, close button, `role="status"`. One at a time, newest wins.
- Both side columns run to the bottom of the window; each column's content scrolls on its own. The agent composer stays
  under the centre viewport only.

## 2. File menu
Dropdown styled like the reference: plain rows, shortcut hints on the right, separators, ▸ for submenus.
- **New** — the existing new-design screen (guarded, see below).
- **Open… (Ctrl+O)** — dialog: search box, list of projects (name, status, updated), "Create new project" row. Enter/click opens.
- **Save (Ctrl+S)** — the graph is already committed on every change; Save flushes the pending wiring layout and reports
  "Saved" with time. Unsaved-state indicator in the header reflects layout edits not yet saved.
- **Make a copy** — server duplicates the project into a new project id (graph, representations re-generated or copied,
  firmware edit, control rules, wiring layout). Opens the copy.
- **Export ▸** — "Project ZIP" downloads `aura-<name>.zip`; "Shareable link" is shown disabled with the reason
  "Sharing needs a hosted server with access control; not available in this build".
- **Import ▸** — "Project ZIP…" file picker; server validates and creates a new project; clear errors for wrong format,
  unsupported version, corrupt file, too large.
- **Save local copy** — same restorable ZIP as Export, named `aura-<name>-local-<date>.zip`.
- Switching project (New/Open/Import/Copy) with unsaved layout edits asks: Save, Discard, Cancel.

### ZIP format (version 1)
`manifest.json` {format:"aura-project", version:1, exportedAt, projectId, objective, appVersion}
`graph.json` (Engineering Graph), `project.json` (status, planning mode, representations metadata),
`artifacts/<id>.<ext>` (schematic, CAD specs), `firmware/` (generated source + user edit block when present),
`layout.json` (wiring layout), `control-rules.json`, `hardware-evidence.json` when present.
Never included: API keys, model profiles, environment, logs. Import and Make a copy share one server path: `graph_from_dict` → rewrite project id → `save_commit` as a new project
→ `RepresentationService.persist_specs` regenerates the 3D and schematic artifacts (artifacts are not copied byte-for-byte).
Layout lives in a new `schematic_layouts(project_id, payload, updated_at)` table (SQLite and Postgres), same pattern as
`control_rules`. Import trusts nothing: size limit 20 MB, only known paths,
JSON parsed and graph validated by the existing graph validation, new project id assigned, provenance marks it "imported".

## 3. Editable Wiring view
- Toolbar on the wiring view: **Select** (default) / **Pan** toggle, Undo, Redo. Space-drag pans in Select mode too.
- **Drag parts:** uses the schematic viewer's own editing mode (`editingEnabled`, `onEditEvent`, `editEvents`), which
  moves the component and its ports. Edits are stored as offsets keyed by the component's stable semantic id.
- **Wire bends:** an overlay draws a handle on each wire segment's midpoint for the selected wire; dragging it moves that
  segment perpendicular to itself (orthogonal bend). Stored per wire id as a list of segment offsets. Electrical
  connections never change.
- **Rename:** inspector gets a "Display name" field for the selected component or net. Stored as a label override in the
  layout; internal ids and pin identities unchanged. Shown in the wiring view, 3D labels, inspector and component list.
- **Undo/redo:** a stack of layout edits (move, bend, rename), Ctrl+Z / Ctrl+Shift+Z inside the wiring view;
  graph undo (Edit ▸ Undo last change) stays as is.
- **Persistence:** `layout.json` per project on the server (GET/PUT `/api/projects/{id}/layout`), autosaved 1 s after the
  last edit and on Save. Keyed by semantic ids and wire ids, so after a regeneration any entries whose part/wire still
  exist are re-applied and the rest are dropped.

## Testing
- Unit: layout reducer (move/bend/rename/undo/redo, prune on regeneration), ZIP manifest validation.
- Python: export → import round-trip gives an equal graph and layout; bad ZIPs rejected with clear codes; copy creates a
  new id; no secrets in the ZIP.
- e2e: ☰ before File and its menu; switch at viewport top-left; no View/Components/Tools; toast shows and dismisses;
  side columns reach the bottom and scroll; File ▸ Open dialog search; Save; unsaved-changes prompt; drag a part,
  reload, position kept; bend a wire; rename shows everywhere; undo/redo.

## Limitations to report
Reconnecting endpoints, firmware pin sync from the wiring view, and shareable links are not built. Bends are per
segment, not free-form. Layout offsets apply to the schematic only, not the 3D placement.
