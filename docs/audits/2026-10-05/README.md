# AURA Audit Evidence — 5 October 2026

[Complete audit report](REPORT.md) · [screenshot gallery](gallery.html) · [baseline](baseline.json) · [source hashes](audited-source-hashes.json) · [published evidence manifest](evidence-manifest.json).

This is the full capability audit with portable source/evidence links, not an abridged replacement. Its finding categories and negative conclusions are preserved. Original evidence was copied byte-for-byte to a durable archive outside the temporary directory and repository. The archive holds the original report, reproduction scripts, logs, graph/API snapshots and screenshots plus original SHA-256 hashes and a snapshot of the pre-existing workspace changes. The repository edition removes machine paths and normalizes text encoding; evidence-manifest.json records original and published hashes for each transformation.

The archive is intentionally separate: local configuration, project databases, caches, generated frontend dependencies/WASM bundles and unnecessary host details are not added here. Selected reproduction scripts are retained in the original archive rather than publishing their machine-specific paths. This edition contains output artifacts and replay instructions sufficient to independently test the documented failures.

## Baseline and interpretation

Source commit: **eb5a756b3148bb1aa50bd36da6fd9aa5aae3b2b5**. Audit ran against main with PYTHONPATH pinned to that checkout. The existing editable Python environment points at another checkout; relying on its default import path can test the wrong source. Documentation/evidence are prepared in an existing clean hackathon-integration worktree at the same commit.

Pre-existing main changes: modified AGENTS.md and untracked CLAUDE.md plus six .claude/skills GitNexus files, listed exactly in baseline.json. They were preserved. No audit/planning code fix, dependency installation, commit or push was performed.

Historical evidence, not new verification of fixes:

| Check | Observed result | Evidence |
|---|---|---|
| Source-pinned Python suite, fresh external bytecode cache | 297 passed, 2 skipped | [log](pytest-fresh.log), [XML](pytest-fresh-results.xml) |
| Frontend unit suite | 14 passed, 4 files | [log](frontend-tests.log) |
| Type check / external build | Exit 0 / build succeeded | [typecheck log](typescript.log), [build log](frontend-build.log) |
| Browser suite | 28 passed, 1 skipped, **1 failed** | [log](playwright.log); round2-lifecycle Discard blocked by overlay |
| Six actual backend projects / fresh-source browser | Completed only in deterministic_test; finite/selectable proxies, visible wrong assemblies | [full results](prompt-results.json), [compact](compact-results.json), [fresh browser](fresh-source-browser.json), [gallery](gallery.html) |
| Real provider request | Vertex IAM403, missing aiplatform.endpoints.predict; live quality **not verified** | [API](live-solar-response.json), [UI](live-create-ui.json), [screenshot](live-create-error.png) |

JSON API outputs and screenshots do not prove physical behavior. Mesh counts and successful HTTP responses do not establish request fulfillment. Existing provider errors contain no published bearer token/key. Automated text checks found no private-key, bearer-token, known-key or credential-value patterns and no retained personal machine paths in the published pack; screenshots were visually reviewed during the audit. This is an evidence review, not a repository-wide historical secret audit.

## Reproduction prerequisites and commands

Use the audited commit in an isolated checkout with already installed dependencies, Python >=3.9 with the project's test/server extras, Node/frontend dependencies and Microsoft Edge for Playwright. Cloud live execution requires authorized account credentials; the archived audit's Vertex permissions were insufficient. No new cloud run is implied by these instructions.

From the selected repository root set:

```powershell
$auraRepo = (Get-Location).Path
$auraPython = if ($env:AURA_PYTHON_EXE) { $env:AURA_PYTHON_EXE } else { Join-Path $auraRepo '.venv/Scripts/python.exe' }
$auraOut = Join-Path (Split-Path $auraRepo -Parent) 'aura-audit-rerun'
New-Item -ItemType Directory -Force -Path $auraOut | Out-Null
$env:PYTHONPATH = Join-Path $auraRepo 'src'
$env:PYTHONPYCACHEPREFIX = Join-Path $auraOut 'pycache'
rtk proxy $auraPython -m pytest -q --basetemp "$auraOut/pytest" --junitxml "$auraOut/pytest.xml"
```

Verify imported aura.__file__ points into this checkout. The frontend and browser commands with external build output are V2–V4 in the [implementation plan](../../superpowers/plans/2026-10-05-nebius-nvidia-hackathon-plan.md#verification-commands-and-artifact-discipline). Full normal launcher/build commands may install or overwrite tracked output, so do not use them during reconnaissance.

The backend workflow can be started with the existing WorkspaceApplication/create_app factory against a **new** database and artifact store in $auraOut. Inspect server.py WorkspaceApplication constructor and existing tests/test_workspace_server.py fixtures for current accepted constructor arguments; do not point to the user's persisted workspace. API port is arbitrary; the original audit used 8877. The existing e2e/aura_test_server.py supplies an isolated local browser test application on 4184, with explicit test-provider behavior that must not be mistaken for real model output.

For each original objective in prompt-results.json, POST /api/projects with objective and planningMode=deterministic_test, using a fresh DB or unique objective suffix to avoid objective-idempotency reuse. Save create response plus GET /api/projects/{id}/graph, /assembly, /verification, /provenance and /revisions. Compare source commit and raw objective, not project UUID. Open the actual UI, inspect Assembly and Schematic, select a part, explode then restore; save screenshots and browser errors. Repeat with current-source external frontend build to avoid stale-bundle ambiguity.

For real-provider testing separately use live_model with a fresh objective; save sanitized origin, structured output and provider errors. A reused deterministic project is not a successful live run.

## Failure replay index

| Failure | Repeatable action and expected baseline defect | Primary evidence |
|---|---|---|
| Slider | Create original camera slider objective with 400 mm travel, 8 mm screw, NEMA 17, two rails, limit switches and 12 V. Inspect roles/values and assembly. | [graph](unfamiliar-lead-screw/graph.json): SG90/servo platform, no requested mechanism, 5 V; [image](unfamiliar-lead-screw/fresh-source-assembly.png) |
| Gripper | Create original 60 mm parallel-jaw/linear-guide/servo-driven rack-pinion objective. | [graph](unfamiliar-gripper/graph.json): two-wheel rover/chassis; [image](unfamiliar-gripper/fresh-source-assembly.png) |
| Driver current | Inspect original rover's output net: four 0.6 A loads on 1.2 A driver; compare source-total and driver-channel checks. | [topology](backend-probes/actual-rover-electrical-topology.json), [verification](four-wheel-rover/verification.json) |
| Dimension/null/unit handling | Existing archived failure probes set missing/null/malformed dimensions and cm-unit values; inspect Graph.validate and compare representation/assembly dimension output. | [backend probe results](backend-probes/failure_probes.json), [API probes](failure-probes/results.json), [notes](backend-probes/backend-audit-notes.md) |
| Net verification versus commit | Construct GraphPatch removing only a power relationship while existing net entities remain; verify_modification then bridge.commit/materialize nets and verify_graph. Before commit accepts; after commit detects disconnected required port. | [exact before/after output](backend-probes/net-verification-commit-mismatch.json); original executable probe retained in durable archive |
| Replacement provenance | Invoke the production replacement path for exact 12 V pump definition; inspect old parameters/property evidence after replacement and verification. | [full result](backend-probes/production-replacement-rating-provenance.json); raw probe retained in archive |
| Plan versus graph check coverage | Re-run VerificationService.verify_graph on each archived graph and compare creation verification. | [all-six results](backend-probes/actual-six-graph-reverification.json): zero findings/cross_checked despite limitations |
| CAD readiness | Inspect family_proxy spec/READY record, then UI CAD loop status POST responses. | [fresh browser output](fresh-source-browser.json): READY→GENERATING 409 for every mechanical proxy |
| What-If discard/event/undo | Existing round2-lifecycle browser test; archived real property scenario/apply/discard/undo and revision events. | [browser log](playwright.log), [lifecycle](lifecycle/results.json); source event reload only revision.committed/project.ready |

The durable raw scripts provide exact internal-call argument fixtures for net/property failure reproduction; this guide intentionally does not rewrite those scripts as product tests during the planning pass. Future Stage 2 tests must express the engineering assertion independently and begin red on the baseline.

## Preservation and review

[evidence-manifest.json](evidence-manifest.json) contains SHA-256 hashes of each published file and its original archived source. [preservation-check.json](preservation-check.json) records hash/link/JSON/scan validation. baseline.json contains commit/status only, not absolute machine paths or configuration values.

When updating evidence, retain original results and create a new dated/revision-tagged run. Do not overwrite a failing historical result with a later successful one. Keep sanitized publication evidence separate from original forensics, and do not add databases, credential files or unrelated local changes.

