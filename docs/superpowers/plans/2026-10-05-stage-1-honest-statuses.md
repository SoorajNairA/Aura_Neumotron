# AURA Stage 1: Honest Statuses Implementation Plan

> For agentic workers: use superpowers:executing-plans when implementation is authorized. On 6 October 2026 the user authorized **Task 1.1 only**, including the lifecycle-status correction below. Do not start Task 1.2 or later tasks.

**Goal:** Prevent AURA from presenting an unfulfilled request, unevaluated checks, unsourced engineering values or procedural geometry as a successfully verified design.

**Architecture:** An original-request obligation ledger and a pure revision-bound assessment feed additive API fields. The existing pipeline status remains operational status. Persist assessment with existing revision verification metadata; derive safe conservative responses for older projects. All lifecycle paths and frontend views consume the same contract.

**Tech Stack:** Existing Python dataclasses/Pydantic and graph/repository interfaces; React/TypeScript; pytest, Vitest and Playwright already in the project. No dependency addition is required.

**Spec:** [master plan Stage 1](2026-10-05-nebius-nvidia-hackathon-plan.md), [full audit](../../audits/2026-10-05/REPORT.md), [progress](2026-10-05-nebius-nvidia-progress.md).

## Global Constraints

Task 1.1 is limited to types, serialization and pure projection in workspace/assessment.py and its tests. Preserve graph/API compatibility and existing main changes. No obligation extraction, persistence, API, frontend, provider or geometry implementation is authorized. This stage does not fix voltage propagation, current rules, unit normalization, net compilation or replacement properties. Unknown coverage is explicitly reported.

Integration owner owns the contract, request ledger, orchestration and repository use. Coordinate feature/verification instrumentation and feature/ui consumption before integrating. Feature/3d receives representation classification requirements; do not silently edit its runtime. Mandatory GitNexus impact before each future symbol edit. _project_payload has **HIGH** upstream risk across create/get/list; review all callers and compatibility tests. Fresh context/impact for new implementation is required; this plan's audit does not replace it.

Avoid a database migration: StoredProject currently has no assessment field; save_commit already accepts a verification dictionary and list_revisions returns that payload. Store the revision assessment there rather than adding an uncoordinated constructor field or table column. Never silently rewrite a legacy project's historical graph on GET.

## Review Focus

Test independent comparison against original request, absent versus passed checks, assessment/revision binding, separation of evidence and rule results, all lifecycle entry points, old clients/projects, and truthful render/provider labels. Ensure no claim of physical verification or source retrieval is created by a status mapping.

## Observed starting failures

| Evidence | Source and current consequence | Stage 1 required outcome |
|---|---|---|
| [slider graph](../../audits/2026-10-05/unfamiliar-lead-screw/graph.json), [slider screenshot](../../audits/2026-10-05/unfamiliar-lead-screw/fresh-source-assembly.png) | planner/service.py _semantic_plan misses camera slider, stepper, guides and limits; plan becomes 5 V servo platform instead of requested 400 mm/8 mm/NEMA 17/12 V design. | Missing/unassessed mandatory obligations visible; no fulfilled badge or overall PASS. Geometry remains unchanged here. |
| [gripper graph](../../audits/2026-10-05/unfamiliar-gripper/graph.json), [gripper screenshot](../../audits/2026-10-05/unfamiliar-gripper/fresh-source-assembly.png) | “servo-driven” hits mobile_drive regex; two-wheel rover replaces parallel jaws/rack/pinion/60 mm opening. | Unsupported mechanism or clarification with original constraints, never “supported” merely because a graph exists. |
| [graph re-verification](../../audits/2026-10-05/backend-probes/actual-six-graph-reverification.json) | VerificationService.verify_graph returns cross_checked with no findings for all six; creation's plan limitations are lost. GET verification has summary/findings/evidence but no overall state. | Coverage unknown/not run cannot become success; creation warnings remain visible alongside subsequent rule results. |
| [renderer results](../../audits/2026-10-05/fresh-source-browser.json) | Every mechanical spec is family_proxy; JSON persistence marks READY, CAD loop hits READY→GENERATING 409; UI says parametric engineering geometry ready. | “Procedural concept geometry”; artifact existence is distinct from CAD evaluation, which is not verified. |
| [live API](../../audits/2026-10-05/live-solar-response.json), [UI error](../../audits/2026-10-05/live-create-ui.json) | API reports IAM403; UI asks to refine mechanism; repeat objective can return cached deterministic project. | Actionable sanitized provider failure; display stored origin and project reuse, no fabricated live run. |
| [replacement probe](../../audits/2026-10-05/backend-probes/production-replacement-rating-provenance.json) | Catalogue assumption may be called source_verified; 12 V replacement keeps 5 V facts. | Existing legacy finding state may remain for compatibility, but engineering evidence panel states declared/curated/not independently verified. No global engineering PASS. Stage 2 fixes the underlying facts. |

## Additive contract and exact semantics

The names below are proposed contract names, not existing implemented symbols. Introduce one focused integration-owned module **src/aura/workspace/assessment.py**, not a new service layer. Pure functions can be unit tested without network/browser/SQLite:

- **RequestObligation**: stable id; original text/span; kind; normalized constraint if understood; required flag; support scope; matched semantic IDs; disposition/reason. Capture original explicit values/units before compilation. No fabricated quantity or inferred requirement counted as requested.
- **RequestAssessment**: state; evaluationScope; obligation results; missing/unassessed counts; reasons; originalObjectiveDigest.
- **WorkspaceAssessment**: assessmentVersion=1; operationalStatus (the unchanged supplied lifecycle string); assessedRevisionId and revisionNumber; freshness (CURRENT/STALE/UNKNOWN); originalObjectiveDigest; request; softwareChecks; engineeringEvidence; representations; planningOrigin; limitations.
- **collect_request_obligations(objective)**: returns a bounded ledger with unassessed residual intent; no planner/catalogue/provider dependency.
- **assess_request(ledger, graph)**: compares requested constraints to actual semantic parts/metadata; same-family approximate proxy alone cannot satisfy a mechanism or dimensional constraint.
- **assess_workspace(...)**: computes the revision-bound aggregate from ledger, current graph, explicit verifier execution coverage, representation records/specs and actual stored planning provenance.
- Operational status is supplied independently and preserved exactly. Do not introduce legacy_pipeline_status or derive StoredProject.status from request, check, evidence or representation assessments. An operationally ready project can have a PARTIAL/UNSUPPORTED request or FAILED check assessment. Future UI work presents these meanings separately.
- **WorkspaceApplication.assessment(record)**: one orchestration entry to load the latest revision's assessment/verification payload and current representation records, validate revision binding, and return conservative defaults if absent. No provider call and no graph mutation.
- **WorkspaceAssessment.to_dict()**: one serialization shape used by create/get/list/verification and TypeScript mirror.

Persist original ledger on the root project's metadata as **requestObligations** and **requestObjectiveDigest**, through the normal creation GraphPatch before first commit. Persist completed **workspaceAssessment** as an additive field in the existing revision verification dictionary passed to save_commit. Representation worker state may change without a design revision; overlay current representation readiness when serializing, preserve the immutable revision's assessment, and label any missing evaluation explicitly.

Add **assessment** to create/get/list project responses and GET verification. A concise list response may omit detailed obligations but must keep the same states, assessed revision, counts and limitations. Existing capability/planningMode/status/summary/findings/evidence fields remain. _project_payload can receive an optional precomputed assessment; all three caller paths must provide it. Older frontend fixtures that lack assessment fall back to unknown rather than PASS.

| Dimension | Allowed state vocabulary | Proof required / display |
|---|---|---|
| request.state | NOT_ASSESSED, FULFILLED, PARTIAL, UNSUPPORTED, NEEDS_CLARIFICATION, STALE | FULFILLED only within declared bounded evaluationScope with every mandatory obligation satisfied and no unassessed requested behavior. No recognized obligations → NOT_ASSESSED. Unknown requirement never disappears. “Request constraints met” is scoped, not physical proof. |
| obligation.disposition | SATISFIED, MISSING, UNASSESSED | SATISFIED identifies matching IDs and checked property/interface; raw planner text or mesh existence is insufficient. Unsupported mechanism is UNASSESSED with support reason, not substituted. |
| softwareChecks.state | NOT_RUN, PASSED, FAILED, STALE | PASSED requires explicit executed checks and known applicability/coverage for the named graph-rule scope; zero findings is insufficient. No execution metadata → NOT_RUN with coverage unknown. FAILED beats other states; historical results bind to their revision. |
| engineeringEvidence.state | NOT_VERIFIED, LIMITED, INVALID, STALE | INVALID means a known declared engineering constraint failed, not a hardware measurement. LIMITED means identified evidence supports only named properties; it does not imply physical verification. No PHYSICALLY_VERIFIED state exists. |
| engineeringEvidence properties | declared, curated, retrieved, measured, unknown origin per used property | Existing curated title/URL/descriptor hash does not establish retrieved document/value provenance. Unknown/assumption-backed values never promote. Retain old raw findings separately for compatibility. |
| representations[].kind | PROCEDURAL_PROXY, CAD_UNVERIFIED, ABSTRACT_NETLIST, NONE | One assessment per representation preserves its type and semantic IDs. family_proxy → PROCEDURAL_PROXY regardless of old READY flag. A nonproxy specification without actual evaluation is CAD_UNVERIFIED. No VALIDATED_CAD state. |
| representation artifactState | NOT_READY, READY, FAILED, STALE | READY means artifact/mesh available according to explicit proof. Separate cadEvaluationState NOT_RUN/SUCCEEDED/FAILED; successful meshing still not engineering-valid CAD. |
| representations.electrical.kind | ABSTRACT_NETLIST, NONE | Generic circuit symbols/netlist do not establish physical package pinout or manufacturing layout. |
| planningOrigin | provider, model, planningMode, reusedProject, fallbackReason, verificationStatus | Use actually stored event/model metadata. Old hardcoded/unavailable provider data is unverified, not corrected by guessing. Mark deterministic_test explicitly; missing model remains unknown. |

Assessment precedence is independent of operational lifecycle: a current known failed or blocking check produces softwareChecks.state=FAILED; unfulfilled, unsupported or ambiguous requests retain their own request states. Revision mismatch produces STALE assessment data. None of these rewrites the supplied operationalStatus to BUILD INCOMPLETE or READY WITH LIMITATIONS. A project with missing assessment retains accessible stored artifacts but its request/check state is unknown. Pipeline readiness never substitutes for request fulfillment or engineeringEvidence.

Verifier coverage must distinguish **executed**, **applicable**, **not applicable** and **not evaluated** checks. Task 1.1 defines an explicit CheckCoverage input in the focused module; do not edit VerificationResult or instrument verifiers yet. A later coordinated task may add coverage to existing result/persistence interfaces. Coverage names its scope, executed/applicable/not-applicable/not-evaluated IDs and whether applicability is known. Keep confidence_ingredients as integer counts. Record only checks demonstrably executed; do not infer “10 passed” from ten absent errors. Unknown/incomplete coverage remains NOT_RUN. Keep creation findings/limitations separate from latest graph findings; neither overwrites the other's scope.

Original objective obligations are an independent evaluator, not another generator. Recognize only constraints whose comparison exists: explicit supported roles/quantities, voltage and dimension properties tied to named parts, and known mechanism demands that the current graph cannot fulfill. Mechanism coverage is bounded; any unparsed “must”, opening/travel, transmission or hardware requirement remains unassessed. Do not claim general natural-language completeness. In particular NEMA 17's 17 is a model identifier, not seventeen motors; motor/fan dimensions are not mounting-plate dimensions.

## Task 1.1 — Contract and conservative truth table

**Owner:** integration; coordinate verification/UI. **Dependencies:** Stage 0 preserved baseline.

**Files:** workspace/assessment.py and tests/test_request_assessment.py only for implementation. Inspect existing verification/results.py, evidence.py, verification/delta.py, representation types and graph model; leave them unchanged. Tests precede implementation.

- [x] Run G1 for existing symbols being adapted; record HIGH/UNKNOWN risk and call sites.
- [x] Add **test_assessment_contract_never_infers_pass_from_empty_findings**: an old result without coverage produces NOT_RUN and NOT_VERIFIED, never PASSED.
- [x] Add **test_assessment_contract_failure_is_independent_of_ready**: operational ready status + failed/blocking finding → software FAILED, while operationalStatus remains the supplied ready value. PARTIAL/UNSUPPORTED request states also preserve that operational value.
- [x] Add **test_assessment_contract_proxy_is_not_cad_validation**: family_proxy + READY + Cascade generator name → PROCEDURAL_PROXY, cadEvaluationState NOT_RUN.
- [x] Add **test_assessment_contract_revision_mismatch_is_stale**: payload assessed at revision r, graph at r+1 → STALE/unknown request until reassessed.
- [x] Add **test_assessment_contract_assumption_cannot_be_source_evidence**: old source_verified label referencing engineering-assumption remains declared/unknown in the new evidence dimension.
- [x] Add **test_assessment_contract_serialization_keeps_meanings_separate**: JSON preserves independent operational/request/check/evidence/representation fields without a blanket success or physical-validity status.
- [x] Run V1 tests/test_request_assessment.py -k assessment_contract and capture the expected red result.
- [x] Implement only type/serialization/pure projection in the proposed module; use existing enums unchanged and additive new states here. No database schema changes.
- [x] Run the same selection green; review serialized output for contradictory claims and unnecessary fields.

**Acceptance:** Stable additive JSON vocabulary above; no path maps absence, proxy or unknown evidence to engineering verification. Operational lifecycle remains unchanged even for failed or unfulfilled assessments. Unit tests cover each precedence/default and separate serialization meanings, not snapshots mirroring code.

**Completed 6 October 2026:** 33 contract tests, 94 focused tests, and the full Python suite (330 passed, 2 opt-in live skips). Exact red/green commands, review corrections and evidence paths are recorded in the [progress checklist](2026-10-05-nebius-nvidia-progress.md#task-11-completion--6-october-2026). Only Task 1.1 is complete.

**Unsupported after this task:** No obligation extraction, lifecycle persistence or UI integration yet. Record partial progress only.

### Task 1.1 contract decisions for later tasks

- assess_workspace takes explicit assessed/current revision IDs and numbers plus the unchanged operational_status; it does not inspect or mutate an EngineeringGraph or StoredProject. WorkspaceAssessment.freshness is separate from each assessment state.
- RequestAssessment currently carries enum-valued state, evaluation_scope, satisfied_count, missing_count, unassessed_count and reasons. Counts must be nonnegative; FULFILLED requires an explicit scope, a positive satisfied count and no missing/unassessed obligations. Task 1.2 must independently establish those inputs from the original request. RequestObligation, extraction and graph comparison are not implemented here.
- CheckCoverage is an explicit typed input, not an edit to VerificationResult. PASSED requires successful aggregate software results, complete known applicable coverage, and no unresolved applicable individual finding. Older finding revisions cannot support current success; a known current failed check remains FAILED even alongside stale older findings. The overall wrapper can be CURRENT while its software results are STALE.
- PropertyEvidence binds a supplied EvidenceRecord to one property/entity. Existing assumptions project to DECLARED; matching existing non-assumption references project only to CURATED. Descriptor hashes, retrievedAt and source_verified do not establish retrieved or measured properties. RETRIEVED/MEASURED and engineering INVALID vocabulary are reserved for later qualified inputs; this projection does not generate those claims.
- RepresentationInput uses existing RepresentationRecord/RepresentationSpec. Outputs are a tuple/list of per-representation assessments, retaining type, revision and semantic IDs. Artifact READY means the supplied ready record has an artifact ID; no file lookup occurs. family_proxy is PROCEDURAL_PROXY, and cadEvaluationState remains NOT_RUN because no CAD execution proof is consumed here.
- PlanningOrigin is an optional supplied data type; no provider discovery or inference occurs. JSON serialization uses camelCase and keeps independent operationalStatus/request/softwareChecks/engineeringEvidence/representations fields. It contains no combined PASS or physical-validation status.
- This is a typed Python contract and serializer, not an untrusted JSON deserializer. Later API/persistence tasks must validate and construct typed inputs rather than reuse arbitrary legacy status strings as proof.

## Task 1.2 — Preserve and assess original obligations

**Owner:** integration. **Dependencies:** 1.1.

**Files:** workspace/assessment.py; planner/schemas.py ProjectRequest; server.py _create_serialized/_store_build_incomplete; root EngineeringEntity metadata created by PlannerService plan patch. Existing compiler functions are inspected but their generation behavior stays unchanged here.

- [ ] Add **test_request_obligations_slider_never_fulfilled_by_servo_platform**, using the archived original objective and a reproducibly compiled actual graph. Assert mandatory travel/lead screw/stepper/guides/switches/12 V remain missing or unassessed and request state is not FULFILLED.
- [ ] Add **test_request_obligations_gripper_never_fulfilled_by_rover**, asserting jaws/60 mm opening/rack-pinion/linear guides never satisfied by wheel/chassis metadata.
- [ ] Add **test_request_obligations_explicit_12v_is_not_satisfied_by_default_5v** and **test_request_obligations_dimension_requires_value_units_and_target**; absence or mismatch cannot be satisfied through a default.
- [ ] Add **test_request_obligations_unknown_residual_prevents_fulfilled** and **test_request_obligations_quantity_is_not_model_identifier**. Use paraphrases and altered values, not project-name assertions.
- [ ] Add **test_request_obligations_scoped_match_is_not_hardware_validation**: a fully comparable bounded declared constraint set may be FULFILLED while evidence remains NOT_VERIFIED and mechanical output remains PROCEDURAL_PROXY.
- [ ] Run V1 tests/test_request_assessment.py -k request_obligations red.
- [ ] Implement the bounded original-text ledger, preserving raw numeric values, units and text spans, and explicit unsupported/unassessed residuals. Reuse existing quantity/unit utilities when correct; do not rewrite the planner in this task.
- [ ] Attach ledger/digest before accepted first graph commit, retaining it unchanged during repair and future edits. Diagnostic build_incomplete records retain the original ledger even with no candidate parts.
- [ ] Run green; review that the evaluator's claimed scope matches what it actually compares and cannot fabricate fulfillment from compiler-generated semanticRequirements.

**Acceptance:** Unsupported slider/gripper remain recognizable failed obligations in API assessment. Explicit parameter demands cannot vanish. Fully analyzed scoped requests can be distinguished from partial/unassessed requests without any new geometry.

**Unsupported afterward:** Actual stepper/gripper synthesis and parameter propagation remain unchanged; the evaluator can reject, not generate them.

## Task 1.3 — One assessment for persisted revisions and all API paths

**Owner:** integration with verification metadata handoff. **Dependencies:** 1.1/1.2.

**Files:** server.py WorkspaceApplication/_create_serialized/_resume_incomplete/recover_interrupted/_project_payload, create/get/list/verification, commit modification/apply scenario/undo; persistence/project_repository.py save_commit/list_revisions; verification/service.py verify/verify_graph/verify_modification and result metadata. Existing repository schema and transaction API stay.

- [ ] Add proposed **test_workspace_assessment_create_get_list_agree** to tests/test_workspace_server.py: exact revision/state/count parity, additive old fields still present.
- [ ] Add **test_workspace_assessment_zero_graph_findings_do_not_erase_plan_limitations**: latest cross_checked graph record cannot erase original missing obligation/proxy/creation limitation.
- [ ] Add **test_workspace_assessment_legacy_reopen_is_unknown_and_read_only**: old project has no ledger or coverage; repeated GET preserves graph/revision and reports NOT_ASSESSED/NOT_RUN.
- [ ] Add **test_workspace_assessment_resume_keeps_same_gates** and **test_workspace_assessment_rejected_candidate_never_ready** using the existing build-incomplete retry/recovery mechanisms.
- [ ] Add **test_workspace_assessment_modification_scenario_and_undo_bind_revision**: committed revision, modified values, ledger and finding scope agree; stale previous result explicitly STALE; all preserved original constraints reassessed. A rejected/failed edit leaves baseline assessment/revision unchanged.
- [ ] Add **test_workspace_assessment_cached_deterministic_origin_is_not_new_live_run**: original project.started metadata/planningMode retained; reuse marked even when caller asks live_model. Do not make a provider request in this deterministic API test.
- [ ] Run V1 tests/test_workspace_server.py tests/test_project_repository.py -k workspace_assessment red.
- [ ] Implement WorkspaceApplication.assessment and the single pure projection. Store the assessment in the existing revision verification dictionary within save_commit, with correct revision ID/number. Capture coverage conservatively; unknown executed/applicable checks stay explicit.
- [ ] Update create/get/list/_project_payload and GET verification to include assessment. No GET mutation, no extra assessment-only engineering revision, no independent status algorithm per route.
- [ ] Apply the same projection to create/retry/resume/commit/scenario/undo and recover-interrupted rendering. Preserve operation idempotency and optimistic revision checks.
- [ ] Run focused tests green, then existing repository, verification-delta, reliability and lifecycle tests with V1. Inspect API diffs and current GitNexus callers.

**Acceptance:** Assessment survives restart and agrees across create/get/list/verification; existing fields/constructors/SQLite schema remain compatible; concurrency/idempotency tests still pass. If historical evidence cannot be tied to the current revision, explicitly stale/unknown.

**Unsupported afterward:** Candidate/net-commit equivalence and electrical rating correctness remain Stage 2 defects. Instrumented rule execution reports what ran, not correctness of a flawed rule.

## Task 1.4 — Truthful frontend and actionable provider errors

**Owner:** feature/ui on agreed integration contract. **Dependencies:** 1.3.

**Files:** frontend/src/WorkspaceApp.tsx verificationLabel/load/create, presentation.ts projectStatus/statusTone, workspaceHydration.ts plus existing hydration/session helpers; presentation.test.ts and relevant existing tests. Proposed e2e/request-assessment.spec.ts for real persisted API status; no wholesale component rewrite.

- [ ] Add Vitest cases for missing assessment, unknown coverage, blocked design, partial request, proxy/CAD-unverified, stale revision and declared-only evidence. Existing ready summary fixtures become conservative; document the intentional status semantics change.
- [ ] Add frontend provider-error test: sanitized IAM403/API detail is displayed as account/permission issue, preserving a meaningful error code; no refine-mechanism guidance for authentication failure and no bearer/key output.
- [ ] Add real browser/API test: display request missing constraints and procedural proxy for archived wrong-family objectives; header never shows verification PASS. Cross-view selection remains usable for diagnostic artifacts.
- [ ] Run V2 and selected V4 cases red.
- [ ] Render separate concise request/rule/evidence/representation labels with accessible expandable reasons. Remove blanket engineering PASS and “parametric engineering geometry ready” for family_proxy. Display current assessed revision and actual planning mode/model when known.
- [ ] Use backend assessment as authority; do not duplicate obligation matching in JavaScript. Missing backend assessment gets unknown labels; failure/unsupported labels cannot acquire green statusTone.
- [ ] Surface sanitized structured provider/API failures in create and What-If. Preserve retry/reopen context and cached/deterministic origin.
- [ ] Run V2/V3 green; V4 cases with a fresh external build and real API. Capture screenshots with errors/unknowns and inspect for secrets.

**Acceptance:** Viewers can distinguish graph-rule outcome, requested behavior, property evidence and geometry status. IAM failure is diagnosable. Existing selection/navigation works, and old-project data cannot default to a green engineering result.

**Unsupported afterward:** What-If Discard overlay and dual-client refresh are not fixed here; model access remains unverified.

## Task 1.5 — Regression gate and progress update

**Owner:** integration with UI/verification handoffs. **Dependencies:** all 1.x tasks.

**Files:** new/focused tests above; existing tests/test_goal8_verification.py, test_verification_delta.py, test_goal10_reliability.py, test_lifecycle_torture.py; frontend/e2e/request-assessment.spec.ts; progress document. Reuse source fixtures/objectives or compact graph fixture builders; do not copy all audit output into tests or bake project UUIDs/mesh counts into assertions.

- [ ] Run V1–V3 on integration current source. Check actual executed test counts and no test silently skipped merely to pass.
- [ ] Run V4 new status/selection cases. Record the pre-existing round2-lifecycle Discard failure separately if still unresolved; full browser green is a later Stage 5/6 gate, not a false Stage 1 claim.
- [ ] Reproduce all six audited objectives with explicit deterministic_test in a new isolated database and unique request IDs; retain source objective text, graph, status and screenshot. These remain stress tests, not curated supported prompts.
- [ ] Assert slider/gripper not FULFILLED; other family concepts do not assert general physical validity; unknown coverage/evidence and all procedural meshes are labeled honestly.
- [ ] Verify cached reopen cannot count as a fresh live-model attempt. Live-quality conclusion remains “not verified: IAM403” until Stage 3 real evidence exists.
- [ ] Check API compatibility and revision/read-only invariants, git diff --check and nontruncated GitNexus change analysis.
- [ ] Update progress task rows with command, result, assessed revision/build, artifact paths and remaining unsupported scope. Do not mark Stage 2 defects fixed.

**Acceptance:** Every new status path has meaningful negative assertions; partial/unsupported/unknown cases are demonstrated in real API/UI outputs; all required Stage 1 tests pass, historical browser failure remains disclosed if outstanding. No new production/cloud/CAD claim.

**Go/no-go:** Mandatory before Stage 2 fixes are presented as dependable or Stage 3 outputs judged as fulfilling requests. If honest positive coverage cannot be instrumented yet, expose unknown. If stage spans too much code, split API contract, persistence and UI handoffs into independently reviewed changes; do not omit legacy/revision tests to accelerate.

## Future verification commands

Use V1–V4 and G1/G2 from the [master plan](2026-10-05-nebius-nvidia-hackathon-plan.md#verification-commands-and-artifact-discipline). These commands are not executed in this planning pass.

Stage 1 focused Python suite after the proposed file exists:

```powershell
rtk proxy $auraPython -m pytest -q tests/test_request_assessment.py tests/test_workspace_server.py tests/test_project_repository.py tests/test_verification_delta.py --basetemp "$auraOut/stage1-pytest" --junitxml "$auraOut/stage1.xml"
```

Frontend: npm test must execute status tests; tsc --noEmit; external Vite build; selected request-assessment Playwright tests against the real test API. Store outputs outside temp in the ongoing verification archive and publish only reviewed sanitized subsets.

Stage 1 is complete only when request assessment, revision/API consistency and UI defaults pass their gates. It makes existing defects visible; it does not claim their repair.
