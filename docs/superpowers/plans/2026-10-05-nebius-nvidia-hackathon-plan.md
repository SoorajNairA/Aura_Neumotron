# AURA Nebius x NVIDIA Hackathon Implementation Plan

> For agentic workers: when implementation is separately authorized, use superpowers:executing-plans to execute this plan task by task. Delegation requires explicit authorization. This document authorizes no implementation.

**Goal:** Deliver one dependable, auditable low-voltage engineering design workflow, powered at runtime by NVIDIA Nemotron through Nebius Token Factory, with truthful limitations and reproducible submission evidence.

**Architecture:** Preserve the existing planner → Engineering Graph → verification → bridge/persistence → schematic/assembly workflow. Add independent request assessment first; then repair deterministic correctness, connect the provider, and qualify one bounded synthesis scope. Models propose intent and bounded edits; deterministic rules evaluate declared constraints. Representation, request fulfillment and engineering validation remain separate.

**Tech Stack:** Existing Python/FastAPI/Pydantic/SQLite, React/TypeScript/Three.js, tscircuit and optional Cascade runtime. Use existing HTTP dependencies for Token Factory unless a later implementation decision establishes a real need for another dependency.

**Spec:** User's 5 October 2026 planning request; [full capability audit](../../audits/2026-10-05/REPORT.md), [portable evidence and reproduction guide](../../audits/2026-10-05/README.md), [Stage 1 detailed plan](2026-10-05-stage-1-honest-statuses.md), [progress checklist](2026-10-05-nebius-nvidia-progress.md).

## Global Constraints

- This pass produces documentation and preserves evidence only. No product code, dependency installation, commit or push.
- Baseline: main and existing hackathon-integration both at `eb5a756b3148bb1aa50bd36da6fd9aa5aae3b2b5`. Main already has modified AGENTS.md and untracked CLAUDE.md/.claude skills. [Recorded status](../../audits/2026-10-05/baseline.json). Preserve these changes; no reset, cleanup, checkout replacement or automatic promotion.
- Shared contracts, core orchestration and shared documentation are integration-owned. Apply future shared changes on hackathon-integration. UI, verification and representation work belong respectively to feature/ui, feature/verification and feature/3d, with coordinated contracts; validate combined work on hackathon-integration. Main promotion remains a human-reviewed integration-owner action.
- Before every future symbol edit: GitNexus impact plus current source/call-site inspection. Before any later commit: complete graph change analysis and git diff --check. UNKNOWN means unresolved. The audited _project_payload upstream analysis is **HIGH risk**: create_project, get_project and list_projects depend on it. Do not waive this because a shared-axis estimate is low.
- Never call a procedural proxy validated CAD, a consistent graph a fulfilled request, or software rule success physical verification. Missing facts and unevaluated requirements remain unknown.
- Every completed task records starting failure, command/result, resulting revision/commit, artifact path and remaining limitations. Proposed tests below do not exist yet unless identified as existing. Passing the current suite alone is not acceptance.
- Do not erase the audit failures by changing fixtures or removing assertions. Record expected historical failures separately from new regressions.
- Use isolated project databases and external build/test outputs. Pin PYTHONPATH to the intended checkout: the existing editable installation points to another checkout.
- No secrets in source, logs, screenshots, public evidence, URLs or configuration examples. Review provider diagnostics before publishing.

## Review Focus

Independent request evidence; voltage and branch-current semantics; authoritative nets at verification and commit; preservation of evidence provenance; truthful CAD state; status freshness across revisions; no silent deterministic substitution for live model results; usable What-If with concurrency protection. Assess visible geometry against dimensions/interfaces rather than screenshots alone.

## Scope and delivery decisions

The initial supported workflow is a **low-voltage, temperature-triggered single DC fan controller design**: controller, one temperature sensor, one DC load, a rated switching path/protection as required by the selected hardware, an isolated supply, and a simple dimensioned mounting plate. Requests may vary threshold, explicit supply voltage, fan dimensions and mounting coordinates within supported ranges. A parameter is supported only after it is preserved through graph, checks and representations; otherwise request clarification or reject that constraint.

This is a design workspace. Generating firmware, proving real hardware behavior, thermal/EMC/safety certification, manufacturing-ready PCB/CAD and general mechanism synthesis are outside the first scope. Editable graph parameters and preserved threshold intent do not establish executable controller behavior. A design using only declared/catalogue estimates must visibly retain that evidence limitation.

Choose an exact controller/sensor/fan/switch set after checking documentation and available data. Do not fabricate precise part ratings or present generic symbols as real package pinouts. Use one declared operating range; a 12 V substitution that requires redesign must be rejected until that redesign is implemented and checked.

Solar trackers, multichannel rovers, fluid systems, camera sliders and rack-and-pinion grippers remain audit regressions and honest unsupported/partial cases. Do not add a prompt-name template to make a recording work. Evaluate paraphrases, changed dimensions/ratings and withheld wording.

Dependencies: **0 → 1 → 2 → 3 → 4 → 5 → 6**. Provider account/model availability reconnaissance (3.1) may occur after 0 to expose a credential blocker early; provider integration and quality claims wait for 1/2. Stage 4 relies on Stage 2 electrical/unit fixes and Stage 3 measured planning quality. Stage 5 uses the same candidate evaluator and status contract rather than creating another verification path.

Planning checkpoints, not effort guarantees: 5–7 October baseline/status; 8–13 correctness; provider access check early and qualified integration by 16; scoped synthesis by 21; repair/What-If by 25; release evidence and submission preparation by 28. Re-estimate after each stage. If any mandatory gate is missed, reduce scope or report no-go; do not relabel failures.

The official global event deadline is 30 October 2026, 10:00 PDT (17:00 UTC / 22:30 IST). A runtime Token Factory call to an NVIDIA open model qualifies as running on Nebius; pre-existing projects require a significant update during the submission period. Recheck eligibility before submission. [Official rules](https://nebiusglobalaihackathon.devpost.com/rules), checked 5 October 2026.

## Stage 0 — Baseline and reproducible audit evidence

**Outcome/boundaries:** Preserve the complete report and relevant original artifacts durably, provide a portable sanitized repository edition, and record the starting commit/workspace. This is completed documentation work, not a claim that defects are fixed.

| Task | Starting problem/evidence | Ordered action, files/interfaces | Acceptance / verification |
|---|---|---|---|
| 0.1 | Audit report, probes and screenshots existed only in a temporary directory. | Archive original report, relevant raw probes/logs/graphs/screenshots and hashes outside temp. Record main/integration commits, branches, dirty paths and hashes of pre-existing files. | Original-file manifest matches byte-for-byte. Baseline contains both commits and preserved main status. |
| 0.2 | Report contained local absolute links and logs contained runtime paths. | Prepare docs/audits/2026-10-05: full REPORT.md, gallery, graph/verification/circuit outputs, source/evidence manifests and existing test logs. Exclude database, caches, rebuild binaries and local configuration. Scan credential patterns and machine paths; inspect screenshots. | Portable report/evidence links resolve; UTF-8 JSON parses; manifests match; zero unresolved secret/path findings. Raw archival originals remain separate. |
| 0.3 | Passing suite could conceal the wrong slider/gripper and stale-net failures. | Index six request outcomes, backend failure probes, lifecycle defects, source-pinned test commands, and original IAM403. README.md distinguishes historical results from future commands. | Reproduction instructions identify exact objective, endpoint/mode, expected defect and source commit. No live-quality claim. |

**Evidence:** [source hashes](../../audits/2026-10-05/audited-source-hashes.json), [evidence hashes](../../audits/2026-10-05/evidence-manifest.json), [six outputs](../../audits/2026-10-05/compact-results.json), [test XML](../../audits/2026-10-05/pytest-fresh-results.xml), [backend probes](../../audits/2026-10-05/backend-probes/backend-audit-notes.md).

**Baseline results:** Python 297 passed / 2 skipped; frontend 14 passed; type check/build succeeded. Browser suite 28 passed / 1 skipped / **1 failed** (What-If Discard blocked). Fresh-source six-request checks reproduced proxy output and READY→GENERATING 409s. Live Vertex requests failed IAM403; completed requests used deterministic_test.

**Commands:** Reproduction guide commands V1–V4 plus archive/evidence hash and link validation. This planning pass does not rerun the entire product suite.

**Unsupported afterward:** All baseline defects remain; live model quality, physical hardware, engineering-valid CAD and production deployment are not verified.

**Time-short decision:** GO only with intact evidence and preserved workspace. Do not start code against a guessed baseline or publish unsanitized data.

## Stage 1 — Honest request-fulfillment and verification statuses

**Outcome/boundaries:** Every project/revision exposes independent request fulfillment, rule-check coverage, engineering evidence, representation quality and planner provenance. Unknown and failed states cannot become a blanket PASS. Existing project/pipeline status retains its operational meaning: PARTIAL/UNSUPPORTED requests and FAILED checks do not by themselves rewrite it to BUILD INCOMPLETE. The UI later presents assessments separately. Do not repair synthesis, ratings, geometry or provider integration here.

| Task | Starting failure | Files/interfaces and dependency | Acceptance / command |
|---|---|---|---|
| 1.1 | Empty findings and absent API state become UI PASS. | Define pure RequestAssessment/WorkspaceAssessment types and projection in workspace/assessment.py and its tests only. Existing verifier/result and project consumers remain unchanged until later tasks. | Contract tests reject contradictory/stale/empty success states and preserve independent operational lifecycle. V1 -k assessment_contract. |
| 1.2 | Slider becomes servo platform; gripper becomes two-wheel rover despite mandatory requested parts. | Original ProjectRequest.objective → independent bounded obligation ledger before PlannerService normalization; capabilities.py/planner schemas/server creation. Depends 1.1. | Original text, quantities, dimensions and voltages are retained or explicitly unassessed. Unsupported mechanism never FULFILLED. V1 -k request_obligations. |
| 1.3 | verify_graph loses plan warnings; create/resume/commit/apply have different assessment coverage. | One revision-bound assessment projection alongside server lifecycle, persisted metadata via save_commit, get_project/list_projects/verification. Depends 1.1/1.2. | Legacy records become NOT_ASSESSED, failed checks cannot assessment-PASS, stale assessments cannot green, operational status stays independent, duplicate reads do not mutate revision history. V1 -k workspace_assessment. |
| 1.4 | Header PASS, parametric geometry wording and refine-prompt message conceal missing checks/proxies/IAM errors. | WorkspaceApp.tsx verificationLabel/load/create, presentation.ts projectStatus, hydration and focused UI tests. Depends 1.3. | Distinct statuses/reasons, explicit procedural proxy, provider failure preserved without secrets, no global engineering PASS. V2/V3; proposed browser status cases via V4. |
| 1.5 | Current tests pass while broad capability labels overstate six stress cases. | API/browser regressions with ledger/coverage/representation combinations; existing test_workspace_server.py/test_goal8_verification.py and proposed test_request_assessment.py. Depends all above. | Replay baseline: slider/gripper unsupported or needs clarification, uncertain fan concept visibly limited, no cached project claimed as new live output. Full V1–V4 with failures accounted for. |

**Detailed task definitions, contract and test assertions:** [Stage 1 plan](2026-10-05-stage-1-honest-statuses.md). Paths there are repository-relative; all named new test cases are future work.

**Unsupported afterward:** Actual 12 V and unit preservation, driver-current checks, stale-net verification, trustworthy sourced ratings, CAD generation and inaccessible What-If are still unfixed. Status can honestly expose those limits; it does not validate them.

**Time-short decision:** Mandatory GO gate before any polished demo or model-quality claim. Ship a smaller honestly limited workflow; do not retain false PASS to save time.

## Stage 2 — Deterministic correctness defects

**Outcome/boundaries:** One candidate graph has consistent units, properties, requirements and nets before and after commit. Repair known deterministic defects without expanding mechanical families. This stage requires new red tests; some existing tests assert permissive legacy behavior and need explicit semantic review, not indiscriminate updates.

| Task | Starting failure / reproduction | Files/interfaces and dependency order | Acceptance / verification |
|---|---|---|---|
| 2.1 | “servo-driven” matches mobile_drive; NEMA 17 is missed; 400 mm slider is replaced by SG90. Slider/gripper outputs in audit. | planner/service.py _semantic_plan/_named_component_count/_resolve_component_intent, capabilities.py. Consume Stage 1 obligations. Make unsupported mechanism explicit; separate identifier digits from quantities; do not synthesize unsupported mechanics. | New tests in test_semantic_generation_correctness.py for paraphrases, family-boundary collisions, quantities and unsupported mechanisms. No two-wheel gripper or servo substituted for a required stepper. V1 -k 'semantic or obligation'. |
| 2.2 | Explicit 12 V objective becomes 5 V default; 1 cm metadata renders 1 mm; absent dimensions default silently; null values can raise TypeError. | planner/service.py/schemas.py; engineering_graph/model.py validate; verification/units.py; workspace/assembly.py engineering_assembly and representation_service.py representation_specs. Depends 2.1. Canonical mm conversion at a single boundary; original units/values preserved; required missing inputs block/clarify. | New negative/null/nonfinite/unit-conversion tests plus test_engineering_invariants.py/test_physical_assembly.py. 1 cm = 10 mm across assembly/spec; requested 12 V retained or explicitly unsupported; API errors are structured, not 500. V1 selected files. |
| 2.3 | Four 0.6 A motors share a 1.2 A driver output; supply-total rule passes 3.4 A supply. Normal voltage_v lacks input/output ranges expected by graph rules. | verification/graph_rules.py port_records/voltage/current checks, catalogue.py and actual graph port/property contract; planner port metadata. Depends 2.2. Separate supply, switch/channel and load ratings, continuous/startup conditions. | New branch-current overload and voltage-range tests in test_verification_real_world.py/test_goal8_verification.py. 2.4 A > 1.2 A blocks; unknown stall/channel rating remains unknown, not PASS. V1 -k 'voltage or current or capacity'. |
| 2.4 | Removing supply relationship passes verification with old net entities, then committed graph fails. | verification/service.py _with_authoritative_nets/verify_modification; electrical.py materialize_electrical_nets; bridge.py commit; patches.py apply_patch; server commit/apply transaction. Depends 2.3. Evaluate normalized candidate after rematerializing nets; commit exact evaluated candidate or prove identical topology/hash. | New test in test_verification_graph_integrity.py: remove supply connection → rejected before commit; revision unchanged; candidate/committed electrical signatures identical for accepted edits. V1 selected graph/repository/modification tests. |
| 2.5 | 12 V pump replacement retains old 5 V parameters, then assumption-backed catalogue identity is promoted source_verified. Evidence hash covers descriptor, not document/property value. | modifications.py _replace; verification/service.py verify_modification; evidence.py EvidenceRecord.curated; catalogue.py/source/property facts. Depends 2.2/2.4. Replace/invalidate dimensions, ports, ratings and provenance coherently; bind each check to actual property evidence. Keep curated and declared distinct from fetched/measured. | New tests in test_modification_ai.py/test_goal8_verification.py: replacement cannot retain old voltage/rating; assumption never source_verified; property changes invalidate evidence/digest; unknown facts block applicable safety claims. V1 -k 'replacement or provenance or evidence'. |
| 2.6 | READY→GENERATING rejected 409 per proxy; mechanical READY means JSON spec exists; container orientation wrong, hose rendered box. | representations.py legal lifecycle, representation_service.py initial_records/persist_specs, WorkspaceApp.tsx load/model CAD loop, Cascade evaluate.mjs. Coordinate 3D/UI/shared status contract. Depends 1/2.2. Skip CAD transitions for proxies; keep artifact-ready separate from evaluated CAD. Fix only scoped orientation/scale; generic fallback explicitly degraded. | Existing test_representations.py plus new lifecycle tests and frontend status assertions. Proxy never claims CAD-ready; real nonproxy evaluation succeeds or FAILED with reason; no unexplained status409 storm. V1/V2/V3 and scoped browser V4. |

**Evidence:** [net-commit mismatch](../../audits/2026-10-05/backend-probes/net-verification-commit-mismatch.json), [replacement provenance](../../audits/2026-10-05/backend-probes/production-replacement-rating-provenance.json), [failure probes](../../audits/2026-10-05/failure-probes/results.json), [fresh renderer results](../../audits/2026-10-05/fresh-source-browser.json).

**Unsupported afterward:** General rail/rack/gear synthesis, simulation, certified ratings from unsourced planner values, manufacturing CAD, fluid mechanics, thermal/EMC validation and arbitrary multichannel actuation.

**Time-short decision:** 2.2–2.5 are mandatory for electrical compatibility claims and editable engineering workflow. If a family cannot be repaired in time, disable its supported status and modification path. Optional CAD execution can be cut if procedural representations are clearly labeled. Do not cut net/property integrity.

## Stage 3 — Working Nemotron through Nebius Token Factory

**Outcome/boundaries:** Real account-authorized Nemotron calls feed the existing planner/modification/semantic-review interfaces; the UI reports provider/model, live versus deterministic origin, latency, attempts and actionable failures. Schema success alone is not planning quality.

Token Factory documents the OpenAI-compatible base URL https://api.tokenfactory.nebius.com/v1/ and NEBIUS_API_KEY. JSON-schema support is model-dependent; confirm the selected Nemotron model in the account rather than assuming an identifier or structured-output capability. [Quickstart](https://docs.tokenfactory.nebius.com/quickstart), [structured output documentation](https://docs.tokenfactory.nebius.com/ai-models-inference/json), checked 5 October 2026.

| Task | Starting failure | Files/interfaces and dependency | Acceptance / verification |
|---|---|---|---|
| 3.1 | Live audit blocked by Vertex IAM403; no Token Factory execution evidence. | Credentials/account/project/model availability and budget preflight; no product change required. May run after Stage 0 when separately authorized. | Store sanitized model identifier/access outcome; one bounded real call succeeds. Never print key or auth header. Credential/no-credit failure is NO-GO for live-provider claim. |
| 3.2 | Existing provider paths support Vertex/Ollama; shared ModelProvider omits generate_structured used by LivePlanner and scenario review. | infrastructure/llm/provider.py ModelGenerationResult/protocol, proposed nebius.py, app/config.py, server.py plan/provider selection, diagnostics.py. Preserve Vertex adapters and expand explicit structured interface coherently. Depends 1/2. | HTTP adapter tests: generate, generate_structured, diagnostics, timeout, 401/403/429/5xx, invalid/refused/empty response, usage metadata. Prefer existing requests dependency. Proposed tests/test_nebius_provider.py; V1 selected provider/model-switch tests. |
| 3.3 | project.started planner provider hardcoded “vertex”; same objective reopens cached deterministic project before live call. | server.py _create_serialized/provenance, planner/live.py plan/repair/_generate; modifications.py LiveModificationPlanner; scenarios.py CandidateSemantics/reviewer. Depends 3.2. Provider-neutral origin and explicit reuse marker. | API shows actual provider/model, fresh/cached distinction and bounded attempts. New isolated DB or unique objectives for each live probe; no automatic deterministic substitution hidden as live. V1 model/provenance tests. |
| 3.4 | No measured live-model request fulfillment. | Exercise scoped paraphrases, changed values, underspecified request and two outside-scope mechanisms; store raw structured results with sanitized timing/cost and Stage 1 assessments. Depends 3.3. | At least 3 withheld in-scope requests × 3 runs, no mandatory obligation dropped on accepted results; all invalid/unknown cases rejected or clarified. Document completion rate, latency range, retry frequency and total usage. Opt-in proposed tests/test_nebius_live.py plus real browser/API artifacts. |

**Unsupported afterward:** Live output quality outside the qualified scope; authoritative facts produced by a model; arbitrary topology/CAD. Existing StructuredPlannerResponse carries component strings, not arbitrary geometry; the adapter does not remove that limitation.

**Time-short decision:** A real successful eligible runtime call is mandatory for the chosen submission. If account access fails, escalate credentials immediately and mark live integration blocked; a recording of deterministic_test cannot stand in for Nemotron. One model is sufficient; routing/fine-tuning/multiple models are optional cuts.

## Stage 4 — Mechanical/electrical synthesis and credible 3D within scope

**Outcome/boundaries:** Qualify the single-load fan design through named interfaces, normalized dimensions, rated electrical topology and coherent editable proxies. Useful bounded geometry means a new mounting plate derived from user dimensions and part mounting interfaces; it does not mean validated CAD or general generation.

| Task | Starting failure | Files/interfaces and dependency | Acceptance / verification |
|---|---|---|---|
| 4.1 | Semantic compiler chooses catalogue defaults; real selected ratings and control interfaces unverified. | planner/schemas.py StructuredPlannerResponse in live.py, service.py intent compiler, catalogue.py/property facts and engineering_graph/interfaces.py component_interfaces. Depends 2/3. Define supported typed roles, dimensions, voltage and threshold contracts for the fan workflow; require missing hardware facts explicitly. | Proposed tests/test_fan_controller_workflow.py: threshold/voltage/dimension variations preserved, controller→switch→fan and sensor→controller links explicit, reverse/wrong-function connections block. Scoped grounded facts or visible declared-value limitations; V1. |
| 4.2 | Connected-looking schematics can share a single overloaded output; generic pins do not establish physical wiring. | electrical.py/graph_rules.py authoritative branch nets, representation_service.py circuit payload, generators/tscircuit and SchematicViewport. Depends 4.1. Preserve terminal roles/channel IDs and required protection from selected hardware specification. | Net memberships/component IDs/labels match graph; independent schematic connectivity assertions; disconnected required terminals block; voltage/current cases still fail appropriately. V1 electrical/circuit tests and screenshot artifacts. |
| 4.3 | Visual layouts use hardcoded family poses/default dimensions; overlap test ignores rotation and mated pairs. | assembly.py engineering_assembly, interfaces.py, representation specs, HolographicScene.model/positionParts. Depends 4.1/4.2. Generate plate/mount positions from dimensions/interfaces; known orientations and supported fan clearance; remove prompt-specific display offsets from scoped path. | New interface-to-plate tests: mounting holes/frames align within stated tolerance; unit/scale changes propagate; oriented bounds detect unsupported overlaps; accepted contacts explicitly identified, not blanket ignored. Visual review from multiple angles, regenerate/explode/restore/select. V1 focused assembly tests + V4. |
| 4.4 | Mesh finite/selectable was mistaken for a coherent fulfilled engineering assembly. | Cross-view integration tests, API graph/assembly/verification/representation metadata, browser screenshots. Depends 4.1–4.3. Independent reviewer compares request ledger, BOM, topology, dimensions and visible assembly. | Three unseen wordings/parameter sets produce recognizable scoped designs with IDs and consistent facts. Mounts/clearances or facts lacking proof are labeled unknown. Durable artifacts include generation mode and commit. V1–V4 + live quality set. |

**Unsupported afterward:** General mechanisms, kinematics/dynamics, fluid routing, arbitrary meshes/assets, CAD/BREP manufacturing suitability, validated collision/contact simulation, PCB fabrication, firmware and hardware operation.

**Time-short decision:** Qualify a smaller electrical design + dimensioned mounting proxy if full mounting detail slips. Keep “procedural concept representation” label. NO-GO for assembly credibility if independent ledger, scale, terminal mapping or scoped clearance checks disagree.

## Stage 5 — Bounded repair and What-If

**Outcome/boundaries:** One bounded repair attempt and one assess→preview→apply/undo path evaluate the same candidate and refresh all views/statuses. Work items remain task tracking, not proof that a repair was done.

| Task | Starting failure | Files/interfaces and dependency | Acceptance / verification |
|---|---|---|---|
| 5.1 | Current one-repair loop can regenerate an internally consistent wrong design; original obligations not authoritative. | planner/live.py repair; server.py _create_serialized; verification/assessment; test_bounded_planner_repair.py. Depends 1–4. Repair addresses named failed obligations/checks; no scope/fact weakening. | Proposed tests: max one repair, no retry loop, original obligation IDs unchanged, unresolved repair → build_incomplete/clarification; no rejected candidate committed. V1 bounded repair tests. |
| 5.2 | Replacement candidate inherits old facts; model semantic approval can overstate direct applicability. Live review IAM403. | modifications.py, scenarios.py CandidateSemantics/EngineeringScenario, server.py create/apply scenario and verification candidate pipeline. Depends 2/3/4. Require deterministic compatibility plus evidence sufficiency after model role proposal. | Threshold/property edit works; compatible same-function replacement requires complete ratings; 12 V incompatibility and unknown ratings keep Apply disabled. Analysis leaves graph/revision unchanged; apply exactly evaluated candidate once. V1 test_round2_scenarios.py/test_modification_ai.py plus live review artifacts. |
| 5.3 | Browser Discard blocked; scenario.applied does not trigger second client's revision reload; undo only last modification. | frontend WorkspaceApp.tsx websocket/What-If controls/styles.css; server.py apply events/revisions; work.py if work linkage changes. Coordinate UI/shared. Depends 5.2. Fix overlay hit targets and one consistent revision event; clearly expose undo boundaries. | Browser real flow analyzes, discards without mutation, applies once, updates two clients, reopens same graph, undo restores graph/nets/status or is clearly unavailable. Stale/double Apply 409, no partial transaction. V4 round2-lifecycle and proposed dual-client cases; V1 lifecycle/scenarios. |

**Unsupported afterward:** Autonomous unbounded optimization, arbitrary mechanism repair, model-only compatibility decisions, physical repair validation, unrestricted history undo and work-item completion as engineering verification.

**Time-short decision:** If replacement review cannot be qualified, keep property edits with deterministic validation and disable replacement Apply. If Discard/apply/concurrency remains defective, exclude What-If from demo and public supported scope; preserve failure disclosure.

## Stage 6 — Demo, public repository and submission

**Outcome/boundaries:** Reproducible test build and an honest sub-three-minute demonstration of the qualified workflow. This is a hackathon release, not production-grade certification. Publishing and promotion require later explicit authorization.

| Task | Starting problem | Files/interfaces and dependency | Acceptance / verification |
|---|---|---|---|
| 6.1 | Existing source tests pass but one browser lifecycle case fails; source/bundle can diverge; editable runtime points elsewhere. | Integration branch, README.md, pyproject/package manifests, launcher/build/package config and diagnostics. Depends 1–5 for advertised capabilities. Create documented test build without hidden local assets/config. | Fresh isolated environment reproduces install/run using existing declared dependencies; V1–V4 required suite passes or excluded capability explicitly removed. Source/build hashes recorded; no unresolved regressions in selected workflow. |
| 6.2 | Public code/evidence/license completeness and external-asset redistribution rights not established. | README, existing LICENSE if present, third-party dependency/asset notices, audit evidence pack, .gitignore and release contents. Depends 6.1. Scan tracked/untracked release files and intended history for secrets; exclude local DB/credentials/caches. Ownership decides project license and publication. | Reviewer can find setup, boundaries, genuine Nebius/NVIDIA use, baseline/new changes, evidence and authorized license. No proprietary assets copied without rights; public repository complete for selected platform. No commit/push during this planning pass. |
| 6.3 | No qualified Nemotron end-to-end demo yet. | Real running workspace and sanitized recording artifacts. Depends 3/4 and optional 5. Show request→actual Nemotron provenance→obligations/topology→procedural assembly/schematic selection→one edit/revalidation→reopen. | Video <3 minutes shows same tested build. Include one honest incompatible/unknown result. A canned project/replay is labeled; it never substitutes for runtime model proof. |
| 6.4 | AURA existed before hackathon; track/eligibility and judging access need explicit decision. | Submission description and public/test-build links, setup instructions and period update summary. Depends 6.1–6.3. Verify official rules and chosen track with owner. | Public licensed repo + README, YouTube video, description, testing access and disclosure of significant period updates; record owner-reviewed submission confirmation. Recheck current rules/deadline. |

Prefer the Apps and Agents track for a software design workspace unless the owner chooses another justified track. Physical AI requires its additional footage/access conditions; procedural rendering alone does not establish hardware performance. Required public repository/license/README, video under three minutes, available judging access and update disclosure are from the [official rules](https://nebiusglobalaihackathon.devpost.com/rules); confirm current conditions before publishing.

**Unsupported afterward:** Multi-tenant production security/authorization, load/SLA, industrial qualification, manufacturing outputs and unsupported engineering domains. Any production claim needs a separate security/reliability/hardware audit.

**Time-short decision:** Cut extra families, CAD meshing, additional models, packaging variants and autonomous repair first. Do not cut truthful statuses, real Nebius runtime use, electrical/net/property integrity, an independently reproducible workflow or required submission assets. If those gates fail, the technically honest decision is no-go for the claimed submission behavior.

## Verification commands and artifact discipline

These are commands for **later authorized implementation**, not commands run in this documentation pass. Use a feature/integration checkout with existing dependencies. If it has no environment, point AURA_PYTHON_EXE at an already installed interpreter; do not install to make this planning pass green.

PowerShell setup from repository root:

```powershell
$auraRepo = (Get-Location).Path
$auraPython = if ($env:AURA_PYTHON_EXE) { $env:AURA_PYTHON_EXE } else { Join-Path $auraRepo '.venv/Scripts/python.exe' }
$auraFrontend = Join-Path $auraRepo 'src/aura/workspace/web/frontend'
$auraOut = Join-Path (Split-Path $auraRepo -Parent) 'aura-plan-verification'
New-Item -ItemType Directory -Force -Path $auraOut | Out-Null
$env:PYTHONPATH = Join-Path $auraRepo 'src'
$env:PYTHONPYCACHEPREFIX = Join-Path $auraOut 'pycache'
```

- **V1:** `rtk proxy $auraPython -m pytest -q --basetemp "$auraOut/pytest" --junitxml "$auraOut/pytest.xml"`. For a task, add the named existing/new file and `-k` selection; missing proposed tests are not a pass. Final full suite must pass on current source. Capture stderr/stdout and exit code.
- **V2:** In $auraFrontend, `rtk proxy npm test`. Inspect the executed test count: the script permits no tests, so exit zero alone is insufficient.
- **V3:** In $auraFrontend, `rtk proxy node node_modules/typescript/bin/tsc --noEmit`; then set `$env:AURA_FRONTEND_OUT_DIR = Join-Path $auraOut 'frontend'` and `rtk proxy npm run build`. Compare source/build versions; no tracked representation bundle overwritten incidentally.
- **V4:** Browser suite needs Microsoft Edge and a Python runtime with this checkout's PYTHONPATH. Existing playwright.config.ts expects Vite preview on 4183 and test API on 4184. With V3 output: in $auraFrontend run `rtk proxy node node_modules/@playwright/test/cli.js test --output="$auraOut/playwright-results"`; start `rtk proxy node node_modules/vite/bin/vite.js preview --outDir "$auraOut/frontend" --host 127.0.0.1 --port 4183` in another terminal first so config reuses it. Ensure the test server inherits the chosen Python executable via PATH. Do not use npm run test:browser blindly: it rebuilds to the default tracked output directory. For fresh browser artifacts, additionally run a real API workflow; mocked Playwright tests alone do not prove live integration.
- **G1 before edits:** `rtk node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`. Inspect full risk/callers; text-confirm UNKNOWN. If index no longer matches source, coordinate refresh without violating current no-install constraint.
- **G2 before a later commit:** `rtk node .gitnexus/run.cjs detect-changes --scope all --repo .`, `rtk proxy git diff --check`, `rtk proxy git status --porcelain=v1 --untracked-files=all`. Partial/truncated graph results are unresolved; never treat them as clean.
- Live probes are explicitly opt-in and budget bounded. The Stage 3 proposed live tests should require an account key and selected model from the environment, use an isolated DB/unique objective, store sanitized responses and fail/skip honestly when credentials are unavailable. Record exact command once those tests exist.

Do not compare mesh count alone as quality. Store objective, planning provenance, original obligations, assessed revision, graph/net signatures, values/units, evidence coverage, request status, screenshots and defects for each accepted workflow. Each numeric engineering check must identify which supplied, curated, retrieved or measured facts it used.
