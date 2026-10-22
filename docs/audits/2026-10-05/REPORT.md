# AURA: current capability and limitation audit

Audited 5 October 2026. Repository: repository, branch main, HEAD eb5a756b3148bb1aa50bd36da6fd9aa5aae3b2b5.

**AURA currently demonstrates a persistent, interactive workspace for bounded low-voltage mechatronic concepts. The evidence does not establish production-grade general engineering generation or engineering-valid assemblies.** It has useful graph, UI, persistence and workflow behavior. Its visible mechanical output is predominantly handwritten procedural family geometry. Verification can report success for a design that does not satisfy the request, and the creation and modification verification paths have materially different coverage.

This audit made no source changes, dependency installations, commits, pushes, deployments, or fixes. Existing AGENTS.md modifications and untracked .claude/ and CLAUDE.md were preserved. All audit projects, probes, builds, reports and primary evidence are outside the repository. No feature roadmap or Nemotron integration plan is included. Your later instruction to assess production software, without curated examples, is reflected here: prompts are stress cases, not endorsements or a demo script.

## Evidence and classification

Every capability is classified using these categories:

- **D — Works reliably and demonstrated:** observed in this local audit, or a specific deterministic software behavior established by passing tests. This does not imply production load, hardware or cloud validation.
- **B — Works only for specific prompts or component families.**
- **T — Uses prepared assets or project-specific templates:** includes handwritten visual templates and static compiler rules, not just imported model files.
- **P — Produces procedural geometry from rules.**
- **G — Attempts general generation but gives poor or inconsistent results.**
- **C — Exists in code but is untested or inaccessible in this environment.**
- **O — Planned or documented only:** no current integrated execution evidence.

High confidence means direct source plus actual output or a targeted reproduction. Medium means source/test evidence with the relevant external execution unverified. “Not verified” is used for missing execution evidence.

Primary evidence: [screenshots gallery](gallery.html), [six request results and full objectives](prompt-results.json), [compact results](compact-results.json), [failure probes](failure-probes/results.json), [lifecycle operations](lifecycle/results.json), [backend evidence notes](backend-probes/backend-audit-notes.md). Source hashes are in [source manifest](audited-source-hashes.json).

### How it was run

The documented backend and browser workflow was runnable using existing dependencies. A separate SQLite database and local artifact directory were used on port 8877. No existing user projects were changed.

The virtual environment's editable installation points to another checkout, other-checkout\src. Audit commands explicitly set PYTHONPATH to this repository. A second full Python run used a fresh external bytecode cache to remove copied-cache ambiguity; its skip paths correctly reference current tests. Normal launch scripts were not used because they can install dependencies and rebuild tracked files.

The normal served frontend bundle was exercised first. Current source was independently type-checked and built outside the repository. That fresh build was also loaded through an audit transport that served its files while retaining the real backend API; no API responses were mocked in these six-request probes. Fresh-source and committed-bundle meshes had identical object and triangle counts on these requests, and the same visible defects. WebSocket behavior through that audit transport is not counted as production evidence.

Live creation and replacement What-If requests failed explicitly with Vertex IAM 403, missing aiplatform.endpoints.predict. Therefore all six completed assemblies used the API's explicit **deterministic_test** mode. Real live-model output quality is **not verified**. The UI creation error replaced the actual authentication diagnosis with an instruction to refine the requested mechanism; [API error](live-solar-response.json), [UI error and response](live-create-ui.json), [error screenshot](live-create-error.png).

## System map: natural language to views

| Step | Actual implementation | What it does |
|---|---|---|
| Browser request | [WorkspaceApp.create](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L161) | POSTs objective and live_model mode. Existing projects can reopen rather than invoke a new planner; planning provenance remains important. |
| API schema and capability filter | [CreateProjectBody](../../../src/aura/workspace/server.py#L54), [create_project](../../../src/aura/workspace/server.py#L572), [classify_objective](../../../src/aura/capabilities.py#L26) | Bounds input, rejects or clarifies some out-of-domain objectives, uses keyword classification. |
| Provider planning | [WorkspaceApplication.plan](../../../src/aura/workspace/server.py#L219), [LivePlanner.plan](../../../src/aura/planner/live.py#L50) | Attempts bounded structured model output; falls back when permitted, except actionable authentication failures. |
| Model contract | [StructuredPlannerResponse](../../../src/aura/planner/live.py#L23) | Project name, objective, requirement/assumption strings, and component-name strings. It is not a mesh, CAD-feature, detailed dimension or free-form topology schema. |
| Deterministic intent compiler | [PlannerService.plan / _semantic_plan](../../../src/aura/planner/service.py#L30), [_resolve_component_intent](../../../src/aura/planner/service.py#L516) | Converts objective/labels to supported families, fixed/default dimensions, properties, ports and connections. Named identities are resolved from a small local catalogue. |
| Plan graph contract | [ProjectPlan](../../../src/aura/planner/schemas.py#L98), [EngineeringEntity / EngineeringGraph](../../../src/aura/engineering_graph/model.py#L26) | Typed entity/relationship/revision containers with flexible metadata. Schema validity is not physical validity. |
| Verification and repair | [_create_serialized](../../../src/aura/workspace/server.py#L339), [VerificationService.verify](../../../src/aura/verification/service.py#L36) | Checks plan rules; one repair attempt; rejected architectures become build_incomplete diagnostic projects. |
| Graph commit and nets | [WorkspaceBridge.commit](../../../src/aura/workspace/bridge.py#L38), [apply_patch](../../../src/aura/engineering_graph/patches.py#L41), [materialize_electrical_nets](../../../src/aura/engineering_graph/electrical.py#L13) | Applies accepted patch, appends revision, constructs graph-owned electrical nets. |
| Durable save | [SQLiteProjectRepository.save_commit](../../../src/aura/infrastructure/persistence/project_repository.py#L170) | Transactionally saves graph/revision/events and associated verification metadata. |
| Component representation selection | [representation_specs](../../../src/aura/workspace/representation_service.py#L23) | Selects fixed CAD operation payload and circuit symbol kinds from family and metadata dimensions. Every ordinary mechanical payload is family_proxy. |
| Representation artifact | [initial_records / persist_specs](../../../src/aura/workspace/representation_service.py#L114) | Labels mechanical generator cascade-core, writes JSON spec, marks ready without CAD meshing. CircuitGeneratorAdapter invokes Node tscircuit. |
| Interfaces | [component_interfaces](../../../src/aura/engineering_graph/interfaces.py#L18) | Supplies family-defined local mounting, output, mechanical and conceptual electrical frames. |
| Placement and joints | [engineering_assembly](../../../src/aura/workspace/assembly.py#L44) | Selects compatible interface pairs, traverses directed mates, aligns frames, chooses fixed display joint angles, lays out secondary parts and wires. |
| View hydration | [loadWorkspaceData](../../../src/aura/workspace/web/frontend/src/workspaceHydration.ts#L14), [WorkspaceApp.load](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L144) | Retrieves graph, assembly, stored verification, circuit artifacts and narration. |
| Three.js rendering | [HolographicScene.model/load/positionParts](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L68) | Creates meshes from handwritten family/ID branches and applies graph-derived transforms. |
| Optional CAD rendering | [cadSource](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L33), [Cascade load loop](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L154), [addCad](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L113) | Can evaluate a few fixed CAD operations and render triangulated faces. Normal specs are proxies and are skipped; current status transition fails first. |
| Schematic rendering and selection | [SchematicViewport](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L35), [SelectionStore](../../../src/aura/workspace/web/frontend/src/selection.ts) | Renders Circuit JSON; maps symbols and semantic parts to shared IDs. |

GitNexus CLI query/context/trace was used before source inspection. The local index was tied to the current checkout/commit; the incompatible MCP graph engine was not used as evidence.

## Subsystem capability table

Claims below paraphrase README, architecture and validation documentation. Confidence is confidence in the finding, not a quality score.

| Subsystem / claimed behavior | Observed behavior and classification | Dependencies | Failure modes / limits | Confidence and evidence |
|---|---|---|---|---|
| Natural-language planning: engineering idea to system | **B/T/G:** bounded string-to-family compiler works on established families; unknown mechanisms can be transformed into the wrong known mechanism. **C:** real model output quality not verified. | Vertex credentials/model for live planning; Python/Pydantic; static compiler/catalogue | Word-pattern collisions; quantities/named hardware interpreted only by limited handlers; explicit 400 mm travel, rails, screw, NEMA17 and 60 mm opening were lost. API auth error honest, UI diagnosis generic. | High: six outputs; [semantic compiler](../../../src/aura/planner/service.py#L39); [request evidence](prompt-results.json). |
| Engineering Graph: authoritative connected model | **D:** stable semantic IDs, serialization, schema checks, isolated patches, revision tracking. **B:** metadata can describe family roles/ports/requirements but completeness is optional. | Python graph/patch types; server repository | Missing facts/dimensions can be accepted; null dimensions can throw TypeError; mechanical/electrical connection data and materialized nets can diverge during edits. | High: [Graph.validate](../../../src/aura/engineering_graph/model.py#L98), [apply_patch](../../../src/aura/engineering_graph/patches.py#L41), [failure reproduction](backend-probes/failure_probes.json). |
| 3D representation: multi-part generated mechanical assembly | **D/P/B/T:** selectable real meshes and graph-derived poses; recognizable supported family shapes. **G:** general request fidelity fails. **C:** general exact CAD output not demonstrated. | Three.js; handwritten geometry; assembly compiler; optional Cascade worker/WASM | Proxies, generic boxes, approximate frames, fixed display angles, no general kinematic/constraint solver; status409 per mechanical record. | High: renderer/source plus screenshots; [model](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L68), [browser evidence](fresh-source-browser.json). |
| Electrical schematic: generated and connected | **D:** actual Circuit JSON renders, symbols select graph components, graph-owned nets drive wire metadata. **B/T:** finite generic symbol/pin mappings. | Node; pinned tscircuit/core and schematic viewer | Generic motor/controller/module symbols are not manufacturer pinouts; traces and labels can overlap; firmware, SPICE behavior, PCB correctness and driver channels not verified. | High for rendering/identity, medium for intended electrical validity: [representation_specs](../../../src/aura/workspace/representation_service.py#L43), [rover schematic](four-wheel-rover/schematic.png). |
| Numeric electrical/physical verification | **D/B:** deterministic rules detect specified contradictions in well-described test graphs. **G:** normal generated graphs omit metadata needed for many stronger rules. | Static catalogue, supplied metadata, Pint, graph rules | Driver rating gap; no findings on fresh recheck of all six snapshots; no empirical electrical/mechanical validation. | High: [verify_graph](../../../src/aura/verification/service.py#L308), [six rechecks](backend-probes/actual-six-graph-reverification.json), [rover topology/rating](backend-probes/actual-rover-electrical-topology.json). |
| Evidence and sourced properties | **T:** curated static values with source URLs and provenance labels. **C:** fetched fact-by-fact numerical verification not integrated or demonstrated. | Local catalogue/evidence objects | Hash is descriptor hash, retrievedAt is construction time; source URLs include category/overview pages. source_verified can promote assumptions during replacement. | High: [EvidenceRecord.curated](../../../src/aura/verification/evidence.py#L33), [catalogue sources/definitions](../../../src/aura/verification/catalogue.py#L43), [replacement evidence](backend-probes/production-replacement-rating-provenance.json). |
| Free-form edits: AI proposal, preview, verify/apply | **D/B:** bounded deterministic container resize proved preview isolation, apply, idempotency, stale rejection, regeneration and undo. **C:** real AI interpretation inaccessible. | Structured provider for user-facing live/fallback projects; graph verifier | Supported operations are bounded; exact replacement retains old electrical values; preview/accept metadata can overstate checks. Test-mode phrase edits are not proof of general AI editing. | High for tested lifecycle: [lifecycle evidence](lifecycle/results.json); [LiveModificationPlanner](../../../src/aura/workspace/modifications.py#L44). |
| What-If: compare alternative components | **D/B:** property candidate isolation/apply observed; tests support model-approved/rejected candidates with a controlled provider. **C:** live replacement blocked by IAM. | Model semantic judgments for replacement; graph verifier; process memory | Confidence enum comes from model; old properties largely inherited; in-memory candidates disappear on restart; Discard overlay blocks browser lifecycle test; scenario events lack revision.committed. | High: [analyze](../../../src/aura/workspace/scenarios.py#L89), [apply_scenario](../../../src/aura/workspace/server.py#L885), [browser failure log](playwright.log). |
| Work items: persist engineering work | **D:** create/start/pause/resume/complete and reason enforcement/history/reopen observed. | SQLite; EngineeringWorkService | Completed is requested task state, not a verified deliverable or resolved engineering finding; natural-language command parser is bounded. | High: [work transitions](../../../src/aura/workspace/work_items.py#L110), [work/lifecycle output](lifecycle/results.json). |
| Revisions and undo | **D/B:** applied changes append history; duplicate commit reused rev2; stale commit409; undo appended rev3/restored dimensions. | Patch/inverse metadata; server lock/repository | Current undo only accepts latest modification; second undo409. General arbitrary revision rollback, redo and branching history not demonstrated. | High: [undo_revision](../../../src/aura/workspace/server.py#L815), [lifecycle evidence](lifecycle/results.json). |
| Persistence, events and cross-client updates | **D:** SQLite graph/work reopen, artifact storage, revision/event transactions; ordinary served UI live WebSocket observed. **C:** production multi-instance behavior not verified. | SQLite/local artifacts; optional Postgres/GCS; in-process broker | Locks/cache/fan-out are process-local; pending proposals/scenarios ephemeral. Scenario apply omits event consumed for automatic reload; bounded queue overflow removes listener. Cloud docs limit service to one instance. | High local, medium cloud: [EventBroker](../../../src/aura/workspace/server.py#L119), [save_commit](../../../src/aura/infrastructure/persistence/project_repository.py#L170), [cloud topology](../../../docs/CLOUD_DEPLOYMENT.md#L3). |
| Cross-view consistency | **D:** part/symbol selections resolve same semantic IDs; explode/assemble restored bounds for all six; views use shared graph. **B/G:** agreement with graph does not imply agreement with request or hardware. | Shared graph IDs; circuit mappings; hydration/session selection state | Gripper's views consistently depict a rover. Units/dimensional clamps differ; candidate nets versus committed nets can differ; stale clients after scenario apply not fully exercised. | High: [browser captures](prompt-results.json), [net mismatch reproduction](backend-probes/net-verification-commit-mismatch.json). |
| Narration | **D/B/T:** persisted deterministic graph/event summaries and contextual UI display. **C:** optional phrasing/voice not verified in primary workspace. | NarrationService, graph events; optional provider/TTS | “Ready” narrative is derived from software statuses, not independent engineering evidence. Voice/legacy behavior not established by these runs. | Medium: [NarrationService](../../../src/aura/workspace/narration.py#L124), [server construction](../../../src/aura/workspace/server.py#L184); saved per-project narrations.json. |
| Desktop shell and packaging | **C:** Electron integration exists; browser equivalent verified. TypeScript/build passed. Electron launch/recovery/package outputs not executed in this pass. | Electron/OS shell; backend URL | Shell smoke merely proves load, not end-to-end engineering behavior. Packaging, cold clean-machine startup and distribution reliability not verified. | Medium: [Electron createWindow](../../../src/aura/workspace/web/frontend/electron/main.cjs#L17), [package scripts](../../../src/aura/workspace/web/frontend/package.json#L7). |
| Cloud and legacy systems | **C:** adapters, deployment scripts, optional assistant/desktop/Unreal/voice systems exist. **O:** historical certification/general capability claims have no current integrated evidence. | Authorized cloud resources; optional host apps/models/audio/GPU/Unreal | Live cloud tests skipped; no production deployment or legacy host execution performed. They must not be counted as core workspace capabilities. | Medium: [optional entry points](../../../pyproject.toml#L21), [legacy boundaries](../../../docs/LEGACY.md#L3). |

## 3D inventory and generation-versus-retrieval assessment

The full recursive asset scan included ignored dependencies/build directories, excluding .git. It searched GLB, GLTF, OBJ, FBX, STL, STEP, STP, IGES/IGS, 3MF, Blender, PLY, DAE, OFF, USD variants, 3DS, BREP, X3D, WRL, DXF and DWG.

| Format | Application models | Installed dependency fixtures |
|---|---:|---:|
| GLB / GLTF / OBJ / FBX | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| STP | 0 | 47 |
| STEP | 0 | 8 |
| BREP | 0 | 1 |
| IGS | 0 | 1 |
| STL | 0 | 1 |
| Other searched formats | 0 | 0 |
| Total | **0** | **58** |

All 58 fixtures are under frontend/node_modules/occt-import-js/test/testfiles. They are upstream importer samples, not selected AURA component models. The complete path/size inventory is [3D asset manifest](3d-assets.json). There is no observed active lookup/download path selecting those fixtures.

The 21,241,345-byte cascadestudio.wasm and cascade-worker.js are prepared engine/runtime binaries, not prepared hardware model geometry. Static compiled frontend JS/CSS likewise do not imply prebuilt authored meshes. CATALOG_3D exists as an enum but the ordinary compiler emits mechanical specs and Circuit JSON, not retrieved catalogue models; [representation types](../../../src/aura/workspace/representations.py#L10), [compiler](../../../src/aura/workspace/representation_service.py#L23). Historical [representation decision](../../../docs/decisions/representation-stack.md#L14) explicitly says catalogue geometry was not committed and records a rejected bearing lookup. Current upstream/deployment retrieval availability is **not verified**.

**Prepared assets/templates (T):** the active “library” is handwritten code. It covers servo horns/housings, fan blades/frames, pump forms, controller boards, articulated links, solar panels, camera/tool platforms, sensors, batteries, frames, propellers, motors, wheels/treads/spokes, sliding panels/frames/linear drives, generic modules, containers, grippers and bases. Colors, subparts and shapes are fixed formulas/branches; some branches select by ID text. There is also an explicit irrigation fixture and legacy prototype page. Normal PlannerService.plan calls the semantic compiler, not a stored irrigation scene. [family renderer](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L68), [irrigation_benchmark_plan](../../../src/aura/planner/service.py#L549), [prototype](../../../src/aura/workspace/prototype.py).

**Procedural geometry (P):** meshes are genuinely created at runtime from primitives and supplied dimensions. Recognizable multi-part visuals are more useful than undifferentiated boxes, and interface-derived placements can compose known families. Dimension edits can change graph/spec/assembly dimensions. However, this is not evidence of a newly designed manufacturable part.

**Absent model match:** unknown families generally become rounded boxes; missing dimensions use 45×30×18 mm. Family-looking IDs can still cause a known-looking shape despite unknown metadata. Identity class “exact” means named identity resolution, not exact CAD. Renderer dimensions clamp to at least 4 mm. [dimension defaults / proxy class](../../../src/aura/workspace/assembly.py#L51), [render fallback](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L96).

**CAD capability in code (C):** cadSource supports fixed loft, pipe, filleted enclosure, box, cylinder and sphere expressions. representation_specs chooses an enclosure radius of 4, reservoir loft sections, and a fixed tube path, with other families mostly boxed. Every ordinary mechanical spec is tagged proxy=True / renderStrategy=family_proxy. The frontend skips CAD evaluation for those specs; backend READY only proves spec persistence. There is an additional normal runtime bug: frontend posts GENERATING to already READY records, but READY may transition only to STALE. All six views produced one HTTP409 per mechanical part, retained proxies, and still displayed ready-with-limitations. [proxy marker](../../../src/aura/workspace/representation_service.py#L39), [spec persistence](../../../src/aura/workspace/representation_service.py#L157), [status transitions](../../../src/aura/workspace/representations.py#L30), [CAD loop](../../../src/aura/workspace/web/frontend/src/WorkspaceApp.tsx#L154), [fresh source execution evidence](fresh-source-browser.json).

**General generation (G):** neither tested unfamiliar mechanism was generated. They were normalized into known families while still passing software verification. Live-model capability beyond this bounded compiler is **not verified** because the model request was denied. Historical loft/pipe screenshots in decision documents are historical experiments, not evidence that the current new-project path produces exact CAD.

The source contains quadcopter-specific geometry absent as literal branches in the committed served chunk; the fresh build has a different entry hash. On the six tested cases the fresh and committed meshes match. Source-specific quadcopter visual behavior has no fresh screenshot in this audit, so it is **not verified**, rather than assumed from recent commit messages.

## Placement and mechanical validity

**Demonstrated software placement (D/B/P):** engineering_assembly creates local interfaces, chooses compatible unused pairs, traverses directed mechanical relationships, aligns quaternions and origins, assigns roots, produces wire terminal coordinates and assembly/explode transforms. The browser uses those transforms and preserves semantic selection. All six explode/assemble cycles restored the exact initial rendered bounds.

**Engineering validity not verified (G/C):**

- The algorithm places along a directed traversal, skipping already placed targets. It is not a simultaneous multi-constraint or closed-loop assembly solver.
- Revolute members receive repeating 18°, −24°, 22°, −16° display angles. No demonstrated general joint-DOF motion, dynamics, inverse kinematics, actuator load sizing or driven-part simulation exists in the active view.
- Local frames are defined by family dimensions/rules, not exact shafts, splines, mounting-hole patterns, bearing fits or fasteners. Secondary electronics can receive support layout positions without real graph mounting relationships.
- Explicit quadcopter payload offsets and right-drive motor flips are manual family corrections.
- Mate diagnostics use 0.5 mm origin / 1° axis tolerances; these diagnose the compiler's frame arithmetic, not manufactured fit.
- Bounds/intersection checks use unrotated dimension boxes and ignore all directly mated pairs. “Severe intersection” requires at least 80% overlap of the smaller volume. Moderate clashes, rotated meshes, intentional-looking but invalid interpenetration and joint motion collision are not established.
- Exploded collision handling performs at most eight offset extensions; lack of a failure is not proof no overlap remains.
- Wires use orthogonal elevated routes and fixed thickness. They do not establish harness clearance, connector realism, bend radius, length or current rating.
- A direct 5 cm pump-width input passes graph validation but becomes width 5.0 in an assembly labeled mm, rather than 50 mm. Missing dimensions create default proxy geometry. The renderer clamp introduces further differences.

Evidence: [placement traversal / display joints](../../../src/aura/workspace/assembly.py#L90), [secondary layout](../../../src/aura/workspace/assembly.py#L166), [mate diagnostics](../../../src/aura/workspace/assembly.py#L212), [intersection check](../../../src/aura/workspace/assembly.py#L273), [exploded collision routine](../../../src/aura/workspace/assembly.py#L342), [electrical conceptual frames](../../../src/aura/engineering_graph/interfaces.py#L49), [dimension/unit probe](failure-probes/results.json).

## Six request results: actual views, not exception-only acceptance

These were selected from the existing runtime rehearsal plus unfamiliar mechanisms. The repository does not define one universal four-demo set: the mechanism tests define solar/pan-tilt/manipulator/sliding-door, whereas the runtime rehearsal defines five projects. After your clarification, this audit evaluates these as production stress cases. The other prompt sets are covered only by their existing tests, not claimed as additional fresh visual runs.

All six completed in deterministic_test mode, returned HTTP201 and ready_with_limitations, and the UI displayed zero failed verification checks. All had finite, selectable meshes and a rendered schematic. That is useful UI/serialization evidence, not evidence that each requested system is supported.

| Request / exact full wording in evidence | Parts / visible meshes / schematic symbols | Recognizable and coherent? | Visible/request defects and classification | Evidence |
|---|---|---|---|---|
| Two-axis solar tracker using Nano, panel and brightest-light tracking | 16 / 152 / 12 | Recognizable panel/link/servo concept; two-axis graph placements and selection work. | **B/T/P:** only one of four light sensors is mated to the panel; three appear in an external strip outside their named base footprint, not demonstrated quadrant sensing/mounting; electronics are laid out outside main mechanism; wire arches; fixed display pose; no measured solar/torque/control performance. | [assembly](solar-tracker/assembly.png), [schematic](solar-tracker/schematic.png), [graph](solar-tracker/graph.json). |
| Nano-controlled tabletop DC fan with adjustable speed | 6 / 54 / 5 | Fan, controller, driver, supply and protection recognizable. | **B/T/P:** fan is separate from electronics support; no engineered tabletop stand/mount is established; no demonstrated user speed input, working PWM firmware or dynamic fan operation; tall schematic-style wire routing. | [assembly](dc-fan/assembly.png), [schematic](dc-fan/schematic.png), [graph](dc-fan/graph.json). |
| Remote-controlled four-wheel rover, microcontroller, driver, battery, DC gear motors | 13 / 182 / 8 | Best recognizable whole-system output: chassis, four wheels/motors and top electronics. Graph and rendered quantities agree. | **B/T/P:** no proven motor channels, steering logic, gears/shaft fits or wireless behavior. Four 0.6 A motors share one output from a 1.2 A driver; zero failed checks. Generic motor symbols and schematic labels overlap. | [assembly](four-wheel-rover/assembly.png), [schematic](four-wheel-rover/schematic.png), [rating/topology](backend-probes/actual-rover-electrical-topology.json). |
| Nano soil-moisture system controlling a small DC water pump | 9 / 56 / 6 | Individual pump/controller/sensor recognizable; overall physical assembly is weak. | **B/T/P/G:** reservoir appears sideways because its Y-axis cylinder is unrotated in the Z-up scene, with separately positioned rim/cap; tube renders as a rectangular fallback, not a continuous reservoir→pump→destination path; electronics/enclosure are detached layout parts. Graph has zero mechanical mates, zero fluid relationships and no fluid ports, yet reports no physical representation limitations; fluid functionality not verified. | [assembly](soil-pump/assembly.png), [schematic](soil-pump/schematic.png), [assembly data](soil-pump/assembly.json). |
| Camera slider: 400 mm travel, 8 mm lead screw, NEMA17 stepper, two rails, limit switches, Nano, 12 V | 5 / 47 / 3 | **Not recognizable as requested slider.** Becomes servo-mounted camera platform/base. | **G:** no screw, rails, carriage, stepper, switches or 400 mm travel. Compiler recognizes camera but camera slider is outside its door/panel/drawer sliding rule; lone stepper not counted; fallback SG90 inserted. Default 5 V supply replaces requested 12 V. | [assembly](unfamiliar-lead-screw/assembly.png), [graph](unfamiliar-lead-screw/graph.json), [sliding/count rules](../../../src/aura/planner/service.py#L150). |
| Parallel-jaw gripper: 60 mm opening, two sliding jaws, guides, servo-driven rack/pinion, Nano, 5 V | 8 / 107 / 5 | **Not recognizable as requested gripper.** Becomes two-wheel motorized chassis. | **G:** no jaws, guide mechanism or rack/pinion. “servo-driven” matches mobile-drive regex, inserts chassis/wheels/motors; default servo suppressed. Requested opening is not implemented. | [assembly](unfamiliar-gripper/assembly.png), [graph](unfamiliar-gripper/graph.json), [mobile-drive regex](../../../src/aura/planner/service.py#L66). |

The gripper failure comes from the word “driven,” not an unverified “rack contains rc” theory. The code uses word boundaries for rc. The slider failure comes from family/count rules, not a CAD meshing crash.

**Editable:** semantic part and schematic symbol selection worked for all six; identities were captured. Assembly/schematic consistency was observed at this level. A separate deterministic container edit demonstrated graph/spec regeneration, apply and undo. Real AI-driven arbitrary edits for each of these six are **not verified**, and fine-grained editable meshes/CAD feature history were not demonstrated. A graph and schematic can agree perfectly about the wrong requested system.

## Verification credibility and consistency findings

The numbers used by most ordinary checks are supplied by the deterministic planner and static catalogue, or by edit inputs. They are not measurements. Pint provides real unit arithmetic for some checks, but cannot validate the truth of input values or repair the assembly-unit issue.

1. **Curated source labels are not fetched fact verification.** EvidenceRecord.curated hashes title/URL/publisher/version/property names, not document bytes or numeric values. retrievedAt is object creation time. Catalogue records attach one source to many fixed operating/current/dimension facts, including generic overview/category references. The workspace does not fetch, extract and validate those source facts during creation. The separate ResearchAgent can make web requests but is not connected to the current verification provenance path. [curated evidence](../../../src/aura/verification/evidence.py#L33), [static definitions](../../../src/aura/verification/catalogue.py#L69), [research adapter](../../../src/aura/verification/adapters/research.py#L29).

2. **Creation verification and later graph verification differ substantially.** Each of the six actual graphs has zero component property_facts. Fresh VerificationService.verify_graph accepts each as cross_checked with zero findings. Plan-level estimates/conceptual properties are not re-established, and bare string interfaces lack source/direction/required metadata needed for stronger electrical rules. This does not mean the stored GET verification view instantly loses its original findings; it means the candidate verification path used for edits can be materially weaker. [verify_graph](../../../src/aura/verification/service.py#L308), [port records](../../../src/aura/verification/graph_rules.py#L27), [evidence evaluation](../../../src/aura/verification/graph_rules.py#L284), [actual six reproduction](backend-probes/actual-six-graph-reverification.json).

3. **A real supported replacement helper keeps incompatible values.** The production _replace helper, dispatched by LiveModificationPlanner, selects micro-pump-12v but retains old parameters.voltage_v=5.0. The selected catalogue range is 9–12 V. Verification accepts, and labels the engineering-assumption source source_verified. This probe supplied a valid structured decision directly to the production helper; it did not demonstrate a real model producing that decision. [_replace](../../../src/aura/workspace/modifications.py#L264), [verify_modification](../../../src/aura/verification/service.py#L360), [before/candidate/after output](backend-probes/production-replacement-rating-provenance.json).

4. **Actual rover driver inadequacy is not flagged.** A graph driver→motor path exists; this is not a missing-edge allegation. The load is four declared 0.6 A motors on one driver output, while max_current_a is 1.2 A. Supply budgeting passes against 3.4 A but driver capacity/channel capability is not established. [plan budget](../../../src/aura/verification/service.py#L224), [graph source budget](../../../src/aura/verification/graph_rules.py#L146), [actual rover topology](backend-probes/actual-rover-electrical-topology.json).

5. **Verification and commit can see different electrical nets.** A direct GraphPatch probe removes the only source→required-load power relationship. Candidate verification preserves old materialized nets and accepts. Bridge.commit rematerializes from changed relationships; rechecking the committed graph fails ELEC_REQUIRED_PORT_UNCONNECTED. This is a public graph/verifier/bridge contract issue; the present bounded UI does not expose arbitrary deletion of an electrical relationship, so UI reachability is **not verified**. [preserved nets](../../../src/aura/verification/service.py#L343), [Bridge rematerialization](../../../src/aura/workspace/bridge.py#L48), [reproduction output](backend-probes/net-verification-commit-mismatch.json).

## Failure behavior

| Failure probe | Observed result | Classification and practical meaning |
|---|---|---|
| Unsupported social-media website | HTTP422, UNSUPPORTED with stated domain exclusion | **D:** honest domain rejection. |
| Vague “something cool” objective | HTTP422, NEEDS_CLARIFICATION with question | **D:** honest clarification. |
| Unknown “quantum flux actuator” plus Nano/5 V | HTTP201 ready_with_limitations; unknown requested actuation is not resolved | **G:** known parts can make an unknown objective look supported. |
| No component dimensions | Graph accepted; assembly supplies 45×30×18 mm | **P/G:** useful display fallback but no dimensional engineering truth. |
| Width 5 cm | Accepted graph; assembly treats raw 5 as mm | **G:** cross-view unit inconsistency demonstrated. |
| Invalid relation endpoint | ValueError identifying missing endpoint | **D:** graph invariant rejects. |
| Null dimension value | Direct graph verifier raises uncaught TypeError | **C/G:** robustness gap; normal UI route producing this input not verified. |
| Negative box width mixed with positive dimensions | Direct representation-spec validator accepts | **C/G:** insufficient spec check; validated-graph API reachability not demonstrated. |
| Missing artifact content | HTTP404 with artifact_content_not_found | **D:** explicit missing-artifact result. |
| Provider IAM error | API503 exposes exact 403 permission failure; UI asks to refine mechanism | **D/G:** backend honest, UI hides actionable diagnosis. |
| Circuit subprocess/missing upload/worker failure | Existing controlled tests exercise fallback and graph persistence | **B/C:** unit/integration evidence; not all failure modes injected into this production-like browser run. |
| Failed plan after bounded repair | Existing tests/source persist build_incomplete diagnostics rather than rejected graph | **D/B:** software gate tested; does not catch every incomplete or wrong mechanism. |

Evidence: [API/direct failure results](failure-probes/results.json), [additional graph failures](backend-probes/failure_probes.json), [incomplete build path](../../../src/aura/workspace/server.py#L274), [representation fallback tests](../../../tests/test_representations.py#L47).

## Test results and what they actually establish

| Check | Actual result | Evidence |
|---|---|---|
| Current-repository non-live Python suite, fresh external bytecode cache | **297 passed, 2 skipped**, 188.79 seconds | [full log](pytest-fresh.log), [JUnit evidence](pytest-fresh-results.xml) |
| Frontend Vitest | **14 passed across 4 files** | [unit log](frontend-tests.log) |
| TypeScript noEmit | **Exit0** | [typecheck log](typescript.log) |
| Fresh frontend production build, external output directory | **Exit0**, 712 modules | [build log](frontend-build.log) |
| Playwright browser suite | **28 passed, 1 skipped, 1 failed** | [full browser log](playwright.log), [failure artifacts](playwright-results/round2-lifecycle-real-What-74cd7-and-rejects-stale-candidate/error-context.md) |
| Source/test compileall | **Exit0**, source and test syntax compilation | [compile log](compileall.log) |
| Real six-project browser output | All rendered; selection worked; bounds restored; unexpected mechanisms and status409 observed | [results](prompt-results.json), [fresh source repeat](fresh-source-browser.json), [screenshots](gallery.html) |
| Live planning / replacement What-If | **Blocked: IAM403**, no successful real model output | [live response](live-solar-response.json), [replacement failure](failure-probes/results.json) |
| Electron packaging / cloud deployment / physical hardware | **Not verified** | No execution evidence in this audit. |

The browser failure is e2e/round2-lifecycle.spec.ts:22. The test cannot click Discard because section.scenario-target intercepts pointer events. The overlay positioning is [styles.css](../../../src/aura/workspace/web/frontend/src/styles.css#L18). Assertions later in that same test are not proven by this run. The gated runtime rehearsal was skipped; our separate six-project audit supplies actual screenshots but does not turn that skipped test into a pass.

Coverage limits matter:

- Many production.spec.ts tests mock graph/assembly/verification/project responses, including a project labeled live_model. They do not invoke a real planner. [fixtures](../../../src/aura/workspace/web/frontend/e2e/production.spec.ts#L2).
- The browser integration scenario provider is a controlled test double, not Vertex. [BrowserScenarioProvider](../../../src/aura/workspace/web/frontend/e2e/aura_test_server.py#L15).
- Backend “recognizable subparts” assertions compare metadata strings; they do not inspect manufactured shapes. [test](../../../tests/test_connected_physical_assembly.py#L74).
- Mechanical representation tests verify safe JSON specs/artifact persistence, not actual Cascade evaluation. [representation tests](../../../tests/test_representations.py#L39).
- Exact hardware tests verify identity/name/visualKind, not manufacturer geometry or pinout. [hardware identity tests](../../../tests/test_3d_engineering_credibility.py#L30).
- Evidence tests verify hash length/reference membership/persistence, not fetched content or numeric source truth. [evidence tests](../../../tests/test_goal8_verification.py#L44).
- Strong electrical graph tests use explicit port roles/ratings/facts that normal generated graphs may not provide. [graph integrity tests](../../../tests/test_verification_graph_integrity.py#L40).
- Historical t1–t26, live desktop/TITAN/XTTS and jarvis_acceptance scripts are not collected by the normal pytest filename pattern. They were not run. Live GCP/Vertex tests were skipped by their opt-in flags.

## Five most consequential limitations for a production assessment

1. **Request correctness is not established by successful creation.** Two unfamiliar engineering requests became different mechanisms while displaying verification PASS. The compiler is bounded and prompt-sensitive. This undermines any general engineering-generation claim.
2. **Verification confidence is stronger than its inputs justify.** Static supplied facts and descriptor hashes are presented as sourced evidence; fresh candidate verification loses all limitations on the actual six graphs; replacement can preserve a contradictory voltage and promote an assumption.
3. **Mechanical validity is largely visual.** Proxies and family frames yield recognizable pictures, but exact mounting, dimensions/units, collision freedom, kinematics, load capacity and actuator relationships are not generally validated. The soil-pump view visibly fails to form a physical fluid assembly.
4. **Cross-view consistency can be shallow or divergent.** Shared IDs make selection reliable, but a wrong graph produces consistently wrong views. Candidate/commit net disagreement is reproduced, and scenario apply omits the revision event consumed for automatic reload.
5. **The runnable product surface has unclosed reliability gaps.** Live model access is unavailable here; normal CAD status updates return409; the browser suite has a blocked What-If lifecycle; served assets differ from current source; clean-machine/Electron packaging, cloud/multi-process deployment and sustained production behavior remain unverified.

These are baseline findings, not a feature roadmap or a recommendation to integrate another model.

## Safely observable scope today

In response to your clarification, no curated demo script is recommended. The capabilities that can honestly be shown in a short inspection are: opening/reopening saved conceptual projects; inspecting a shared graph and its procedural family meshes; orbit/selection/isolation/explode/assemble; showing a generated schematic and semantic cross-selection; examining explicitly labeled estimates and evidence records; and managing persisted work-item state/history.

The separate deterministic test workflow also demonstrates bounded proposal/apply/undo/stale/idempotency behavior. It must be labeled a deterministic harness, not represented as successful live AI editing. Current successful real AI planning, arbitrary geometry generation, accurate source-backed component ratings, mechanically validated assemblies, working firmware/hardware, and end-to-end What-If replacement cannot safely be asserted from this audit.

## Access or environment needed for unverified claims

- **Live planning/edit/What-If:** usable ADC/IAM and authorized prediction access to the configured project/model. Permission must actually allow aiplatform.endpoints.predict. No credentials or permissions were changed.
- **Physical engineering correctness:** exact manufacturer part identification, fact-level source documents, real mounting/interface geometry, and appropriate hardware measurements or validated solvers. Existing labels/tests alone do not provide this evidence.
- **Cloud persistence/production operation:** access to the actual authorized service, PostgreSQL and artifact bucket, and opt-in live cloud checks. Multi-instance coordination cannot be inferred from single-process mocks.
- **Electron release:** a controlled desktop/clean-machine run and existing packaging tooling. The current browser audit is not a packaged-installer acceptance result.
- **Optional legacy/voice/Unreal:** the relevant local model services, audio devices, host apps and Unreal project/editor. These systems are separate compatibility paths.
- **Long-running production reliability:** a specified workload and deployed environment to observe concurrency, reconnect/restart, pending candidate lifecycle, storage recovery and resource behavior. This pass supplies local functional evidence, not a sustained production certification.

Audit is complete as reconnaissance. There is no claim that AURA is complete, production-ready, or engineering-certified.

