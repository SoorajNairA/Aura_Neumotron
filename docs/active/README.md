# AURA Active Work and Detailed Remaining Tasks

> **Current working document.** Repository consolidation and documentation organization are complete on local main; see the progress checklist's 22 October verification record and git log/status for the local commit. The next product task is **2.1: deterministic component-family/quantity correctness**. Stage 2 has not started. The independent Token Factory access preflight, 3.1, remains blocked until a real authenticated response is recorded. Do not start later engineering/provider tasks merely because their plans appear below.

**Working folder: Aura. Branch: main. GitHub repository: SoorajNairA/Aura_Neumotron.** The integration changes and current documentation are consolidated here. The old integration worktree remains a preserved source, not the working root for this iteration.

> For agentic workers: this is a documentation and handoff plan, not authorization to implement, commit, change remotes or push. When a task is separately authorized, use superpowers:executing-plans and execute only that task. Delegation requires explicit authorization.

**Prepared:** 22 October 2026. **Original integration baseline (historical):** `eb5a756b3148bb1aa50bd36da6fd9aa5aae3b2b5`, branch `hackathon-integration`, with existing uncommitted Stage 1 changes.

**Subsequent repository handoff, 22 October:** at the user's explicit request, the **Aura** working folder on **main**, already connected to the Aura_Neumotron remote, was consolidated with the integration changes for a reviewed local commit. Local consolidation is recorded in commit `1703713da12a1ea279f085e04c923b34465adc70`; section 2 identifies the current working repository. The original integration worktree remains intact. No push was made and no Stage 2 or provider implementation was started.

**Goal:** Finish one dependable, auditable engineering-design workflow using a real NVIDIA Nemotron call through Nebius Token Factory, with truthful limitations and reproducible release evidence.

**Architecture:** Keep the current planner → Engineering Graph → deterministic checks → revision transaction → schematic/3D workflow. Preserve Stage 1's independent request, software-check, evidence and representation assessments. Repair deterministic integrity before qualifying live-model output and the scoped assembly workflow.

**Tech stack:** Existing Python/FastAPI/Pydantic/SQLite, React/TypeScript/Three.js, tscircuit and optional CAD runtime. Prefer existing HTTP dependencies for Token Factory.

**Source of truth:** This is the current implementation plan. Supporting records: [progress checklist](../superpowers/plans/2026-10-05-nebius-nvidia-progress.md), [Stage 1 contract and tasks](../superpowers/plans/2026-10-05-stage-1-honest-statuses.md), [original capability audit](../audits/2026-10-05/REPORT.md). This document consolidates the remaining work and the newly reported repository handoff; it does not replace historical evidence or mark unfinished tasks complete.

## 0. Status update — 2026-10-27

Working folder is now `D:/Aura/Aura_Neumotron`, branch `AURA-nemotron_test1` (pushed through `1da669f`; later commits are local). This section supersedes older "next task" statements below.

- Done since 2026-10-24: 2.1, 2.2, 3.1 (Nebius key + Nemotron with thinking disabled), 3.2 (Nebius adapter); repair truncation and catalogue-dump fixes (`fae5825`); fan redundant-motor fix (`e57a75c`).
- ESP32 fan slice (spec `docs/superpowers/specs/2026-10-27-esp32-fan-firmware-simulation-design.md`, plan `docs/superpowers/plans/2026-10-27-esp32-fan-firmware-simulation.md`): DS18B20 on the controller 3V3 rail with a 4.7 kΩ pull-up, ESP32 `gpio_map` (GPIO4 sensor, GPIO16 gate) with `ELEC_GPIO` checks, generated sketch, `/firmware` and `/firmware/compile` endpoints, and a behavioral Simulation tab.
- Evidence (2026-10-27): Python 419 passed / 1 pre-existing failure (`test_startup_boundaries`) / 3 skipped (real compile: arduino-cli absent; two opt-in live cloud tests); frontend unit 50 passed; browser 41 passed / 6 failed / 1 skipped, the same 6 failing at the pre-slice baseline `0c7ea3e`; C++ fan rule executed under g++ against the shared truth table.
- Live: "Build a temperature-controlled desk fan" planned by Nemotron via Nebius → `ready_with_limitations`, 8 components, firmware supported, compile `toolchain_missing`.
- Engineering studio redesign (2026-10-27; spec `docs/superpowers/specs/2026-10-27-engineering-studio-redesign-design.md`, plan `docs/superpowers/plans/2026-10-27-engineering-studio-redesign.md`): light studio theme, Design/Code/Simulation/Build spaces (Build and Connect device disabled as "coming next"), grouped component rail with thumbnails, pin-aware inspector card, shared simulation preview, Code space with sketch and compile, "Build it together" composer, studio lighting and realistic procedural models for the ESP32 fan parts. KiCad models skipped (cut item). Model switching deferred; the model badge is read-only. Evidence: Python 422 passed / 1 pre-existing failure / 2 skipped (real ESP32 compile passing, 275,820 bytes, arduino-cli 1.5.1 + esp32 3.3.12); frontend unit 65 passed; browser 54 passed / same 6 baseline failures / 1 skipped.
- Phases 1–3 of the conversational roadmap (2026-10-27; spec `docs/superpowers/specs/2026-10-27-idea-conversation-model-settings-pin-sync-design.md`, plan `docs/superpowers/plans/2026-10-27-idea-conversation-model-settings-pin-sync.md`): idea conversation with deterministic scope/family gate, proposal card (catalogue alternatives, dated prices for 5 fan parts, estimate total) and approve-from-proposal; model profiles (Nebius / OpenAI-compatible / Ollama local, keyring keys, connection test, explicit active profile, no silent fallback); pin changes as verified revisions with graph-level `ELEC_GPIO`; editable `fanControl` block; Code view load-error state. Live: two Nemotron idea runs ended `ready_with_limitations`. Serial log moved to Phase 7 (needs hardware).
- Phase 4 component library (2026-10-27; spec `docs/superpowers/specs/2026-10-27-component-library-design.md`, plan `docs/superpowers/plans/2026-10-27-component-library.md`): ☰ library in the Design space (search, family filter, dated price or "price unavailable"), multi-select add as one verified proposal with safe GPIO allocation and undo, part settings and mechanical mounting through proposals, Code view lists added parts with "Pin assigned — no generated driver yet", behavioral test benches for DS18B20 and the fan only. Electrical wiring between arbitrary parts is not offered (interface rules reject it); added parts get no firmware driver.
- Phases 5–6 for new projects (2026-10-28; spec `docs/superpowers/specs/2026-10-28-new-project-firmware-simulation-views-design.md`, plan `docs/superpowers/plans/2026-10-28-new-project-firmware-simulation-views.md`): shared GPIO allocator (analog → ADC1; fixes soil sensor on strapping GPIO5), IO model + Nemotron rule list validated deterministically, generic ESP32 sketch from fixed drivers (one truth table shared by g++-run C++ and the TS evaluator), rules on the proposal card, rule-driven simulation with fault injection, DevKitC header pin labels/wire endpoints/highlighting, breadboard on approve, detailed module models.
- Live (2026-10-28, Nemotron via Nebius): "water my plant when the soil is dry" → plan rejected by verification (servo not mechanically connected; reported, not hidden). "water my plant with a small pump when the soil moisture sensor reads dry" → rules from the live model (pump on below 30 %, off above 70 %, min 10 s), soil on GPIO32 (ADC1), pump on GPIO16, breadboard added, firmware `generic` compiled with arduino-cli: passed, 278 660 bytes. No hardware run.
- Phase 7 hardware (2026-10-28; spec `docs/superpowers/specs/2026-10-28-hardware-upload-serial-live-design.md`, plan `docs/superpowers/plans/2026-10-28-hardware-upload-serial-live.md`): port listing, gated USB upload, serial monitor with telemetry parsing and wrong-revision banner, hardware evidence rule (3 current-revision lines from a non-fake port), Build space, Live board view with a 3-line rule agreement check, fake board behind `AURA_FAKE_BOARD=1`.
- Fake-board check (2026-10-28, running backend): plant project → upload before compile refused (`COMPILE_REQUIRED`) → compile passed (278 664 bytes) → upload to `FAKE0` → telemetry streamed (pump on while soil low) → no evidence written → upload while monitoring refused (`PORT_BUSY`) → stop left no `arduino-cli` process. `arduino-cli monitor` also started on the real COM1 (nothing attached). **Not tried on hardware: no ESP32 board connected.**
- Readable 3D (2026-10-28; spec `docs/superpowers/specs/2026-10-28-readable-3d-boards-and-wires-design.md`, plan `docs/superpowers/plans/2026-10-28-readable-3d-boards-and-wires.md`): named pin anchors on every studio model (ESP32 38 header pins at 2.54 mm from `pinout.ts`), silkscreen text, pin-to-pin numbered colour-coded jumpers from the graph (`wiring3d.ts`), dashed approximate routes for parts without anchors, GTAO studio lighting with fallback. Real fan project: 14 wires, every end 0.000 mm from its pin, 0 approximate routes; screenshots in `workspace/screenshots/readable-3d/` (local).
- Menu bar + viewport toolbar + view FAB and orthogonal harness wiring (2026-10-29; spec `docs/superpowers/specs/2026-10-29-menu-toolbar-and-clean-wiring-design.md`): lanes per wire (short low), clearance over other parts, tags spread along runs, pin labels only when close. Fan project: 14 wires, ends 0.000 mm from pins.
- Not done: hardware validation (no board yet), OTA/Wi-Fi (no hardware). Known: a stale `build_incomplete` project blocks re-planning the identical objective "Design a temperature-controlled desk fan".

## 1. Current position

| Area | Verified position | What it does not establish |
|---|---|---|
| Stage 0: audit | Report, reproduction artifacts and baseline preserved | Defects repaired |
| Stage 1: honest statuses | Tasks 1.1–1.5 consolidated on local main | Physical validity, dependable synthesis or production readiness |
| Stage 2: correctness | Tasks 2.1–2.6 not started | Safe electrical compatibility or exact candidate/commit equivalence |
| Stage 3: Nemotron | 3.1 blocked at last preflight; 3.2–3.4 not started | Authenticated Token Factory access or measured planning quality |
| Environment setup | Nebius key/base URL/model fields prepared in this checkout; active provider preserved | A Nebius adapter, a valid key or a successful inference |
| Stages 4–6 | Scoped workflow, repair qualification and release work not started | A qualified end-to-end hackathon submission |
| Repository consolidation | Local main includes the Stage 1 work at `1703713`; no push was performed | Publication of this local commit on GitHub |

### Stage 1 achieved

The original request is retained as an independently derived obligation ledger. Revision-bound assessments distinguish request fulfillment, actual software-check coverage, property evidence and representation kind. Create/get/list/verification agree, and supported edit/scenario/undo/recovery paths preserve assessment freshness. The UI exposes missing and unassessed requirements and labels mechanical proxies honestly.

All six archived objectives were reproduced in deterministic mode against a fresh database. All six remained PARTIAL. The wrong slider had five missing and four unassessed obligations; the wrong gripper had six missing and four unassessed obligations. They remained usable diagnostic artifacts rather than verified engineering successes. See the progress checklist's Task 1.5 evidence record.

### Historical validation, not tests run today

| Gate recorded on 6 October | Result |
|---|---|
| Focused Python | 191 passed |
| Full Python | 401 passed, 2 opt-in live tests skipped |
| Frontend unit tests | 47 passed |
| Type check and build | Passed |
| Fresh six-objective and semantic-net selection cases | 7 passed |
| Combined selected Stage 1 browser cases | 39 passed |
| Separately reproduced What-If lifecycle cases | 4 passed, 1 failed |
| Existing opt-in runtime rehearsal | 1 skipped |

The Discard overlay failure remains. Its later Apply/stale assertions were not reached. The previously intermittent Node schematic timeout did not recur in the final Stage 1 gate; that is not a guarantee against future timeouts. Product tests and live inference were not rerun while writing this document.

## 2. Working repository

Use **`C:/Games/Aura`**, branch **`main`**, with origin **`https://github.com/SoorajNairA/Aura_Neumotron.git`**. Aura_Neumotron is the GitHub repository name; the working folder remains Aura.

Commit `1703713da12a1ea279f085e04c923b34465adc70` consolidates Stage 1 and the documentation on local main. The original integration workspace was preserved. No push was performed; remote publication is not established by the local commit. The earlier migration instructions are obsolete and have been removed. Do not repeat repository initialization or rename the working root.

Inspect the current Git log/status before each separately authorized task. Publication and submission remain separate owner actions.

## 3. Global constraints and review focus

- Keep operational readiness independent from request fulfillment. Do not introduce new StoredProject status strings to encode an unfulfilled request.
- A graph-rule success is not request fulfillment or physical verification. Empty findings without proven execution/applicability coverage remain unknown/NOT_RUN.
- Procedural geometry remains a concept proxy. CAD evaluation, mechanical validity and manufacturing suitability require separate evidence.
- Preserve original obligations/digest and revision binding through every accepted change. Rejected candidates and previews must not mutate the baseline.
- Keep declarations, curated information, retrieved documents and measurements distinct. Neither planner confidence nor a descriptor hash proves a physical property.
- Preserve existing workspace changes, contracts and APIs. Follow module ownership and coordinate shared code through integration.
- Before product symbol edits, inspect GitNexus impact and source/call sites. HIGH/CRITICAL risk must be reported; UNKNOWN/partial/truncated results remain unresolved.
- Use test-first changes for deterministic defects. Record exact commands, executed counts, failures and skips. Do not weaken archived regressions to make a gate pass.
- Use isolated databases, explicit source paths and external build/test outputs. Do not rely on the editable installation resolving to the correct checkout.
- Keep all keys private. No logs, screenshots, source examples or URLs may contain credentials. Do not treat a deterministic cache hit as fresh live-model work.

Review the following five input classes in the owning task: **ambiguous/model-number text** (2.1), **missing/nonfinite/unit-bearing values** (2.2), **unknown or overloaded channels** (2.3), **stale topology/evidence after edits** (2.4/2.5), and **provider/cache/revision failures** (3.2/3.3/5.3).

## 4. Dependency order and immediate actions

The engineering sequence remains **2 → 3 → 4 → 5 → 6**, with Stage 1 protected throughout. Task 3.1 is an independent account-access preflight and may be completed while Stage 2 proceeds. Repository handoff protects/publishes completed work; it does not itself improve capabilities.

Immediate sequence:

- [x] Consolidate the integration work on local main in Aura. Remote publication remains pending; no push was performed.
- [ ] Implement **2.1 only** as the next product task: family/quantity collisions and explicit unsupported mechanisms.
- [ ] Separately rerun **3.1** after credentials are supplied privately; no adapter implementation is needed for the preflight.
- [ ] Complete and review each subsequent correctness task before starting live-provider qualification.

No date-based promise replaces an acceptance gate. Use the verified task gates below rather than elapsed calendar dates to judge completion.

## 5. Stage 2: deterministic correctness

### 2.1 — Component families, model identifiers and quantities

**Starting failures:** "servo-driven" can select a mobile-drive family; NEMA 17/frame identity is confused with missing or numeric component intent; the lead-screw slider is represented by a servo platform and the gripper by a chassis.

**Existing interfaces:** `src/aura/planner/service.py` (`_semantic_plan`, `_named_component_count`, `_resolve_component_intent`), `src/aura/capabilities.py`, and the Stage 1 ledger in `src/aura/workspace/assessment.py`.

- [ ] Add failing paraphrase/family-boundary tests in existing `tests/test_semantic_generation_correctness.py`; preserve the archived obligation tests.
- [ ] Distinguish quantities from component/model identifiers and restrict family matching to supported semantic roles.
- [ ] Make an unsupported mechanism explicit instead of substituting a visually plausible unrelated family.
- [ ] Run the semantic, request-assessment and workspace-creation regressions; document residual unassessed language.

**Acceptance:** NEMA 17 is not seventeen motors; required stepper/rail/jaw intent is not fulfilled by servo/wheel metadata; supported existing concepts still compile. No project-name or six-prompt exception branches.

**Still unsupported:** actual general slider/gripper synthesis. **No-go:** unrelated substitutions are still accepted as supported designs.

### 2.2 — Voltage, dimensions and units

**Starting failures:** explicit 12 V becomes default 5 V; 1 cm may render as 1 mm; missing/null dimensions can silently default or raise TypeError.

**Existing files:** planner service/schemas; `src/aura/engineering_graph/model.py`; `src/aura/verification/units.py`; `src/aura/workspace/assembly.py` (`engineering_assembly`); `representation_service.py` (`representation_specs`). Depends on 2.1.

- [ ] Reproduce explicit-versus-default voltage, centimetre conversion, zero/negative/null/malformed/nonfinite dimension cases.
- [ ] Establish one canonical conversion boundary while retaining original values, units and target roles in the ledger.
- [ ] Preserve explicit constraints or return a structured unsupported/clarification result. Do not invent dimensions to satisfy the request.
- [ ] Verify graph → assembly → representation values with `test_engineering_invariants.py`, `test_physical_assembly.py` and request-assessment tests.

**Acceptance:** 1 cm equals 10 mm at every representation boundary; explicit 12 V cannot disappear into a 5 V default; invalid required dimensions produce useful errors rather than an unhandled 500.

**Still unsupported:** arbitrary geometry from any dimensioned natural language. **No-go:** graph and visible scale disagree.

### 2.3 — Supply, branch and driver-channel ratings

**Starting failure:** four 0.6 A motors draw 2.4 A through a 1.2 A driver output, yet a 3.4 A supply-total check can pass. Existing voltage properties do not consistently match the range contract used by graph rules.

**Existing files:** `src/aura/verification/graph_rules.py`, `catalogue.py`, planner port metadata and graph property/interface contracts. Depends on 2.2.

- [ ] Add failing overload cases independently of total supply capacity in `test_verification_real_world.py` and `test_goal8_verification.py`.
- [ ] Separate supply, channel/switch and load ratings; define continuous versus startup/stall assumptions explicitly.
- [ ] Add explicit input/output voltage-range and missing-rating cases. Unknown ratings cannot support a safety claim.
- [ ] Report which specific declared/curated/sourced properties each numerical conclusion uses.

**Acceptance:** 2.4 A on a 1.2 A channel fails regardless of a sufficient upstream supply; unknown channel/stall data remains unknown. **No-go:** numerical PASS conceals an unevaluated branch or assumed rating.

### 2.4 — Candidate nets must equal committed nets

**Starting failure:** removing a supply relationship can pass against old net entities, while the rematerialized committed graph fails.

**Existing interfaces:** `VerificationService._with_authoritative_nets` / `verify_modification`, `src/aura/engineering_graph/electrical.py` (`materialize_electrical_nets`), graph patches, workspace bridge and server edit/Apply transaction. Depends on 2.3.

- [ ] Reproduce the archived [net-commit mismatch](../audits/2026-10-05/backend-probes/net-verification-commit-mismatch.json) before changing transaction behavior.
- [ ] Verify the normalized actual candidate after authoritative net materialization.
- [ ] Commit exactly that candidate, or prove equivalent topology/signature inside the existing revision transaction.
- [ ] Test rejected edits, accepted edits, Apply, retries and optimistic revision conflicts in graph-integrity/repository/lifecycle tests.

**Acceptance:** disconnecting required supply connectivity rejects before commit and preserves baseline revision/assessment; accepted candidate and committed electrical signatures match. **No-go:** any accepted edit produces different checked versus persisted nets.

### 2.5 — Replacement properties and evidence

**Starting failures:** a 12 V replacement pump can retain old 5 V facts; evidence associated with old assumptions/descriptors may appear source-verified without fact-level retrieval.

**Existing interfaces:** `src/aura/workspace/modifications.py` (`_replace`), verification service, `src/aura/verification/evidence.py` (`EvidenceRecord`), catalogue property facts. Depends on 2.2/2.4.

- [ ] Reproduce [replacement rating/provenance evidence](../audits/2026-10-05/backend-probes/production-replacement-rating-provenance.json) in replacement/provenance tests.
- [ ] Replace or invalidate affected ratings, dimensions, interfaces and evidence coherently; retain unchanged facts only with an explicit basis.
- [ ] Bind property evidence to the actual value/entity/revision and invalidate stale support after property changes.
- [ ] Assert assumptions never become retrieved/measured evidence and unknown replacement ratings cannot authorize compatibility.

**Acceptance:** old 5 V facts cannot qualify a 12 V replacement; stale evidence cannot support a current check. Stage 1's conservative projection already prevents some overclaims; this task repairs underlying facts/rules rather than relabeling them.

**Still unsupported:** automatic authoritative sourcing of arbitrary components. **No-go:** evidence provenance is inferred from a model declaration or identity string.

### 2.6 — Proxy versus CAD lifecycle

**Starting failures:** READY-to-GENERATING requests can return 409 for proxies; a stored mechanical spec being ready is confused with CAD execution; orientation/scale/display defects remain.

**Existing files:** `src/aura/workspace/representations.py`, `representation_service.py`, frontend `src/WorkspaceApp.tsx`, generators and representation runtime. Coordinate representation/UI/shared owners. Depends on 2.2 and the preserved Stage 1 contract.

- [ ] Add lifecycle tests distinguishing proxy artifact readiness from actual CAD evaluation.
- [ ] Avoid CAD transitions for procedural proxies; retain explicit execution/failure states for evaluated representations.
- [ ] Repair only scoped orientation/scale defects needed by the qualified workflow; label generic/degraded fallbacks.
- [ ] Run `test_representations.py`, frontend status tests and a real browser flow without status-posting storms.

**Acceptance:** no family proxy claims evaluated CAD or produces repeated unnecessary 409s. **Still unsupported:** manufacturing CAD, general kinematics, contact simulation and arbitrary mechanical generation.

**Stage 2 gate:** 2.2–2.5 are mandatory for electrical/edit integrity claims. Reduce supported families instead of bypassing these checks. Optional CAD execution may be excluded while proxies remain explicit.

## 6. Stage 3: actual Nemotron through Nebius

### 3.1 — Unblock and verify account access

**Last evidence, 7 October:** `NEBIUS_API_KEY` absent in the checked AURA environment. One unauthenticated POST to Token Factory returned HTTP 401 in 792.29 ms: "Couldn't authenticate. Reason: token is not present". This is an endpoint rejection, not generated model output or account permission evidence.

Prepared integration configuration:

| Variable | Meaning/current boundary |
|---|---|
| `NEBIUS_API_KEY` | Private ignored environment only; never publish or paste into chat |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1/`; prepared setting, not consumed by the current AURA adapter |
| `NEBIUS_MODEL` | `nvidia/nemotron-3-super-120b-a12b`; prepared candidate from the preflight, not freshly account-verified |
| `AURA_LLM_PROVIDER` | Still the existing supported provider; do not set `nebius` before its implementation exists |

- [ ] Confirm intended organization/project and usable credits privately in Token Factory.
- [ ] Supply its usable key privately to the process/environment for the **integration** checkout.
- [ ] Run authenticated model listing and exactly one budget-bounded completion against the documented global endpoint.
- [ ] Record model ID, endpoint type, status, latency, usage when supplied, and short sanitized nonempty output; classify failures without guessing account/credit status.

**Acceptance:** one successful real authenticated response; evidence identifies the intended account context without exposing secrets. Current credits, model access and live output remain **not verified** until then. The old Vertex `aiplatform.endpoints.predict` IAM403 belongs to Google ADC/IAM and does not block or authenticate Nebius. This documentation pass did not repeat any inference request.

### 3.2 — Implement the provider contract

**Existing files/interfaces:** `src/aura/infrastructure/llm/provider.py` (`ModelProvider`, `ModelGenerationResult`), `vertex.py`, `src/aura/planner/live.py` (`LivePlanner`, `StructuredPlannerResponse`), app config, workspace provider selection and diagnostics. Proposed new files: `src/aura/infrastructure/llm/nebius.py`, `tests/test_nebius_provider.py`; they do not exist yet.

- [ ] Establish failing tests for plain and structured generation, timeouts, 401/403/429/5xx, refusal, malformed/empty output and usage normalization.
- [ ] Coordinate the structured interface: current ModelProvider does not declare `generate_structured`, although live planner paths use it.
- [ ] Implement with existing HTTP dependencies, bounded retries/timeouts and sanitized errors; preserve the Vertex adapter.
- [ ] Wire prepared environment fields deliberately, add provider selection and test old constructors/call sites.

**Acceptance:** stable normalized results and honest errors across all planner callers, with no key/header leakage or silent deterministic success. JSON-schema support must be tested on the selected account/model, not presumed from API compatibility.

### 3.3 — Provenance, caching and attempts

Stage 1 already distinguishes cached deterministic origin. Extend that existing contract to a real Nebius provider instead of inventing another origin path.

- [ ] Ensure create/repair/edit/scenario paths record actual provider/model and bounded attempts.
- [ ] Preserve cache/reuse markers, original objective/digest and assessed revision.
- [ ] Use a fresh database or unique objective for proof of a new live call; a new request ID alone does not bypass objective reuse.
- [ ] Test model errors and cache hits through actual API/UI responses without changing fulfillment rules.

**Acceptance:** no deterministic or historical project can be presented as a fresh Nemotron run. Dependencies: 3.2; retain Stage 1 lifecycle coverage.

### 3.4 — Measure scoped planning quality

- [ ] Use at least three withheld in-scope requests, three runs each, plus one underspecified request and two outside-scope mechanism requests. Do not add exceptions for the six archived prompts.
- [ ] Evaluate original obligations, values/units, topology, provenance and output coherence independently of planner-generated requirements.
- [ ] Record completion rate, latency distribution, retries, usage/cost when available and visible defects.
- [ ] Keep bad/unknown results rejected, partial or clarification-required; do not make the evaluator more permissive to improve model scores.

**Acceptance:** every accepted result preserves mandatory scoped obligations. Nine schema-valid responses alone do not pass. Proposed live tests must be opt-in, budget-bounded and explicitly skipped/blocked without access.

**Stage 3 no-go:** no real authorized NVIDIA model runtime on Nebius, or no dependable scoped fulfillment. One model is sufficient; routing, fine-tuning and additional models are optional.

## 7. Stage 4: one credible engineering workflow

The existing target is a **low-voltage, temperature-triggered single DC fan controller design** with controller, temperature sensor, one DC fan/load, rated switching/protection/supply and a dimensioned mounting plate. This is a bounded qualification target, not a new production-readiness claim or a restriction on the eventual product vision.

| Task | Existing areas | Steps and acceptance |
|---|---|---|
| 4.1 Typed design facts | Planner schemas/live/service, verification catalogue, engineering graph interfaces | Choose exact supported parts/ranges from available facts; test changed threshold/voltage/dimensions; preserve sensor→controller→switch→fan intent and state missing hardware facts. Proposed `tests/test_fan_controller_workflow.py` must assert independent obligations, not planner self-report. |
| 4.2 Electrical topology | Authoritative nets, graph rules, representation circuit payload, tscircuit generators, schematic view | Bind required terminal/channel roles and protection to selected hardware facts; reject disconnected/wrong-function links; assert graph and schematic net membership/labels agree. Generic symbols do not prove real pinouts. |
| 4.3 Mounting proxy | `engineering_assembly`, component interfaces, representation specs, frontend generators/scene | Derive plate/mounts from dimensions/interfaces; test alignment tolerances, orientation, scale and scoped clearance; classify intended contacts explicitly. Do not waive overlaps simply because parts are mated. |
| 4.4 Independent qualification | Cross-view/API/browser tests and live quality artifacts | Compare three unseen wordings/parameter sets across original request, graph/BOM, nets, dimensions, schematic and visible assembly; verify selection, regenerate/explode/restore and reopen. Unknown physical facts stay visible. |

Dependencies: Stage 2 integrity and Stage 3 measured provider behavior; 4.2 follows 4.1, 4.3 follows 4.1/4.2, and 4.4 qualifies the combined workflow.

**Go/no-go:** matching graph, scale, terminal identities and stated clearance scope are mandatory. A smaller dimensioned electrical-design concept may be acceptable if its limitations are explicit. Firmware execution, hardware operation, thermal/EMC qualification, PCB fabrication, mechanical simulation and manufacturing-ready CAD remain unsupported.

## 8. Stage 5: bounded repair and What-If

| Task | Required work | Acceptance and exclusion boundary |
|---|---|---|
| 5.1 One repair | Existing `LivePlanner.repair`, server creation loop and assessment/check results target named failed obligations/checks; preserve the already retained original ledger | At most one repair; no scope weakening, invented facts or rejected candidate commit. Unresolved design remains incomplete/partial/clarification-required. No unbounded optimization claim. |
| 5.2 Preview and Apply | Existing modifications/scenarios plus exact normalized candidate verification from Stage 2 | Preview baseline unchanged; compatible scoped edit works; incompatible/unknown replacement cannot Apply; committed graph equals evaluated candidate and gets fresh revision-bound assessment. |
| 5.3 Interaction/concurrency | WorkspaceApp controls/events/styles plus server revision events and transactions | Fix existing Discard hit interception; test two-client revision refresh, stale/double Apply, retry and undo boundaries; conflict returns 409 without partial mutation. Reopen reproduces the committed graph/assessment. |

Existing regression areas: `tests/test_bounded_planner_repair.py`, `test_modification_ai.py`, `test_round2_scenarios.py`, `test_lifecycle_torture.py`, assessment lifecycle tests and frontend `e2e/round2-lifecycle.spec.ts`.

Backend assessment preview/Apply/undo protections implemented in Stage 1 are retained, not counted as proof of repaired electrical candidate semantics or complete UI behavior. Work-item completion is task tracking, not proof a design defect was repaired.

**Time-short cut:** qualify deterministic property edits and disable replacement Apply if replacement compatibility cannot be established. Exclude What-If from advertised/demo behavior if Discard, Apply or concurrency remains broken. Preserve the failure evidence.

## 9. Stage 6: repository, demonstration and submission

1. **6.1 Reproduce:** a clean setup/test build must resolve the intended checkout, include required assets and match the inspected source. Required V1–V4 gates must pass for the advertised workflow; report any excluded paths explicitly.
2. **6.2 Review release contents:** reconcile the new repository branch, document setup/limitations, verify license/asset rights and scan intended files/history for secrets. An MIT file is already visible in the new repository; that alone does not verify every third-party asset or the integration changes.
3. **6.3 Demonstrate:** record real scoped request → Nemotron origin → obligations/checks → graph/schematic/proxy → one qualified edit/reopen. A suggested recording budget is 20 seconds scope, 45 planning, 40 cross-view inspection, 35 edit/reopen and 25 limitations: 165 seconds total. Rehearse actual latency; labeled prerecorded output must not masquerade as a new live call.
4. **6.4 Submit:** owner reviews track, testing access, change disclosure, links and final eligibility. Publishing, promotion and submission require explicit authorization.

The [official rules](https://nebiusglobalaihackathon.devpost.com/rules), rechecked 22 October, give the deadline as **30 October 2026, 10:00 PDT / 17:00 UTC / 22:30 IST**. They require an accessible working demo/test build, public licensed source with setup instructions, a public YouTube demonstration under three minutes, track selection and disclosure of significant submission-period updates to pre-existing projects. Keep any track-specific requirements in the owner review.

The [official FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs) confirms that runtime use of an NVIDIA open model through Token Factory can meet the Nebius platform requirement; unrelated frontend/backend processing need not all be hosted there. A failed unauthenticated preflight or prepared `.env` does not satisfy runtime use.

**No-go:** required runtime use, correctness, reproducibility or submission materials are absent. Cut extra component families, optional CAD execution, additional models, packaging variants and autonomous repair before cutting those gates. This is not a promise that all remaining work fits before the deadline.

## 10. Verification and evidence protocol

These are **future execution commands**, not a claim that tests ran during documentation. Use an existing suitable interpreter/dependencies; do not install merely to make this document green.

Gate names retained by the Stage 1 contract and audit guide:

- **V1:** backend pytest, including task-specific red/green cases and the full suite.
- **V2:** frontend unit tests; inspect executed counts because exit zero with no tests is insufficient.
- **V3:** TypeScript check and frontend build.
- **V4:** browser tests against the real isolated test API; mocked tests alone do not prove integration.
- **G1:** GitNexus upstream impact before edits; inspect callers and unresolved risk.
- **G2:** complete GitNexus change analysis and diff/status review before an authorized commit.

From the Aura checkout, PowerShell:

```powershell
$auraRepo = (Get-Location).Path
$auraPython = $env:AURA_PYTHON_EXE
if (-not $auraPython) { $auraPython = Join-Path $auraRepo '.venv/Scripts/python.exe' }
$auraFrontend = Join-Path $auraRepo 'src/aura/workspace/web/frontend'
$auraOut = Join-Path (Split-Path $auraRepo -Parent) 'aura-remaining-work-verification'
New-Item -ItemType Directory -Force -Path $auraOut | Out-Null
$env:PYTHONPATH = Join-Path $auraRepo 'src'
$env:PYTHONPYCACHEPREFIX = Join-Path $auraOut 'pycache'
```

Set `AURA_PYTHON_EXE` privately to an existing interpreter if the checkout has no virtual environment. Confirm the source checkout before interpreting results.

```powershell
# First run each task's specific newly failing cases, then its relevant regressions.
# Full backend gate:
rtk proxy $auraPython -m pytest -q tests --basetemp "$auraOut/pytest" --junitxml "$auraOut/pytest.xml"
# Frontend gates, frontend cwd:
Set-Location $auraFrontend
rtk proxy npm test
rtk proxy node node_modules/typescript/bin/tsc --noEmit
$env:AURA_FRONTEND_OUT_DIR = Join-Path $auraOut 'frontend'
rtk proxy npm run build
```

For real API browser tests use installed Edge, preview 4183, isolated test API 4184 and this checkout's explicit PYTHONPATH. Preview the external build in a separate terminal so the existing Playwright configuration reuses it:

```powershell
rtk proxy node node_modules/vite/bin/vite.js preview --outDir "$auraOut/frontend" --host 127.0.0.1 --port 4183
# Another terminal, frontend cwd with the same source/Python environment:
rtk proxy node node_modules/@playwright/test/cli.js test stage1-regression.spec.ts request-assessment.spec.ts production.spec.ts audit.spec.ts narration.spec.ts --output="$auraOut/browser"
# Preserve/retest the known failure separately until 5.3 repairs it:
rtk proxy node node_modules/@playwright/test/cli.js test round2-lifecycle.spec.ts --output="$auraOut/what-if"
```

Use a fresh database/artifact root for the archived-objective audit; start the real test API with those isolated settings before Playwright reuses it. Confirm that the API's underlying database is fresh, not merely that the request UUID changed. Do not use `AURA_E2E_MOCK_ONLY=1` as evidence for real API integration. Avoid `npm run test:browser` for isolated evidence because it rebuilds default output.

For every task retain: original failure, source revision and dirty status, command/environment, exit, executed counts/skips, original objective/obligations, candidate/committed revision and signatures, numerical values/units and evidence provenance, provider/model/reuse, screenshots and remaining defects. Live quality probes need separate opt-in/budget authorization. Zero tests, skipped live tests and shape-only assertions are not successful capability evidence.

Use the compatible already-installed GitNexus runner for G1/G2 (from the repository root):

```powershell
rtk proxy gitnexus impact "symbolName" --direction upstream --repo .
rtk proxy gitnexus detect-changes --scope all --repo .
rtk proxy git diff --check
rtk proxy git status --porcelain=v1 --untracked-files=all
```

Before an authorized commit run full applicable gates, `git diff --check`, inspect tracked/untracked contents, and obtain complete GitNexus change analysis with the repository/worktree explicitly bound. The earlier MCP/index version mismatch is documented; use the compatible installed runner, not an unrelated clone's index. UNKNOWN or capped static analysis must be supplemented by source/test evidence.

## 11. Completion record and final boundaries

Update the existing progress checklist one task at a time, not this snapshot's status table. Each completion record needs the failing behavior, changed files/contracts, red/green results, broader gates, artifact locations and explicit limitations. Do not mark an entire stage complete for a partial checkpoint.

Before calling the delivery ready:

- [ ] Intended Stage 1 work is committed/reviewed and visible on the correct new-repository branch.
- [ ] 2.1–2.6 acceptance gates pass or unsupported capability is explicitly excluded without bypassing core electrical/net/property integrity.
- [ ] 3.1 has authenticated success; 3.2/3.3 implement real provenance; 3.4 measures scoped quality.
- [ ] 4.1–4.4 show one coherent cross-view workflow under unseen wording/parameter variations.
- [ ] Advertised edits/What-If pass 5.1–5.3; excluded paths remain unavailable or clearly unsupported.
- [ ] Clean setup, source/build reproducibility, release rights/secrets, actual demonstration and owner-reviewed submission meet 6.1–6.4.

Even a completed hackathon gate does not establish multi-tenant security, production reliability/SLA, manufacturing suitability, physical hardware validation or arbitrary engineering/CAD generation. Those need separate qualification. The immediate deliverable is a dependable bounded workflow with auditable limitations.
