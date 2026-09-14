# Backend Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make classification, project creation, scenarios, events, provider timeouts, and idempotency correct and resource-bounded.

**Architecture:** Keep existing HTTP contracts and repositories. Add boundary-aware classification and small bounded runtime primitives, then route existing endpoints through them. Persist committed facts in the repository and treat process memory only as a bounded cache.

**Tech Stack:** Python 3.12, FastAPI, pytest, SQLite/Postgres repository adapters.

**Spec:** `docs/superpowers/specs/2026-09-14-release-hardening-design.md`

## Global Constraints

- Do not change successful API response schemas or graph persistence formats.
- Every behavioral change begins with a failing test and is implemented minimally.
- Shared code is committed only on `hackathon-integration`.

---

### Task 1: Evidence-based capability classification

**Files:**
- Modify: `src/aura/capabilities.py`
- Test: `tests/test_goal5_generalization.py`

**Interfaces:**
- Consumes: `classify_objective(objective: str) -> dict[str, Any]`
- Produces: the same dictionary keys with corrected status/reason values.

- [ ] Add literal assertions that a temperature-controlled fan and robotic arm remain supported, while social-media, cryptocurrency-dashboard, passenger-aircraft, and passenger-ship objectives are unsupported, and generic “something cool” requires clarification.
- [ ] Run `pytest tests/test_goal5_generalization.py -q` and confirm the new software/finance/ship cases fail under the permissive fallback.
- [ ] Replace substring checks with normalized word/phrase matching and require at least one supported-domain signal before returning supported status.
- [ ] Re-run `pytest tests/test_goal5_generalization.py tests/test_goal11_pipeline.py -q` and confirm all classification and pipeline cases pass.

### Task 2: Project-scoped bounded pending state

**Files:**
- Modify: `src/aura/workspace/server.py`
- Test: `tests/test_round2_scenarios.py`
- Test: `tests/test_goal10_reliability.py`

**Interfaces:**
- Produces: `BoundedPendingStore(max_entries: int)` with mapping-compatible `get`, assignment, `pop`, and `clear_project(project_id)` behavior.

- [ ] Change the existing cross-project scenario test to assert that creating project B’s scenario does not invalidate project A’s scenario; add a capacity test proving the oldest consumed/expired entry is evicted at the configured bound.
- [ ] Run the two focused test files and confirm the isolation assertion fails because `application.scenarios` is replaced wholesale.
- [ ] Store scenarios additively, validate `scenario.project_id` on every route, remove consumed entries, and bound proposal/scenario caches without changing endpoint payloads.
- [ ] Re-run both focused files and confirm the isolation and bound behaviors pass.

### Task 3: Bounded event delivery

**Files:**
- Modify: `src/aura/workspace/server.py`
- Test: `tests/test_goal10_reliability.py`

**Interfaces:**
- Produces: subscriber queues with a fixed maximum and deterministic slow-subscriber removal.

- [ ] Add an async test that fills a subscriber queue, publishes one more event, and asserts the subscriber is removed while repository-backed replay remains available.
- [ ] Run the focused test and confirm the current unbounded queue contract fails the maximum-size assertion.
- [ ] Create queues with the configured maximum, stop retaining a duplicate unbounded event history, and remove a subscriber when `put_nowait` raises `QueueFull`.
- [ ] Re-run the focused test and existing WebSocket replay tests.

### Task 4: Bounded provider execution and scoped creation locks

**Files:**
- Modify: `src/aura/planner/live.py`
- Modify: `src/aura/workspace/server.py`
- Test: `tests/test_goal10_reliability.py`
- Test: `tests/test_lifecycle_torture.py`

**Interfaces:**
- Produces: one bounded planner executor and per-objective creation locks; public planner and API signatures remain unchanged.

- [ ] Add a timeout stress test proving repeated timeouts cannot create more workers than the configured maximum, plus a concurrency test proving different objectives are not blocked by the same creation lock.
- [ ] Run both focused files and confirm the new bounds/concurrency assertions fail.
- [ ] Reuse a bounded executor, reject saturated work with the existing fallback outcome, and key creation locks by normalized objective with cleanup after release.
- [ ] Re-run focused tests and the project-creation integration tests.

### Task 5: Legacy route and idempotency lookup hardening

**Files:**
- Modify: `src/aura/workspace/server.py`
- Modify only if required by the existing repository seam: `src/aura/infrastructure/persistence/project_repository.py`
- Test: `tests/test_workspace_server.py`
- Test: `tests/test_project_repository.py`

**Interfaces:**
- Produces: no executable legacy HTML at `/assets/index.html`; operation lookup behavior remains identical.

- [ ] Add an HTTP test asserting `/assets/index.html` does not return the legacy application and a repository test asserting operation lookup returns the matching committed event without loading unrelated graphs.
- [ ] Run focused tests and confirm the legacy route test fails.
- [ ] Mount only required representation assets and route operation lookup through the narrowest repository query already supported; add one indexed event query only if no suitable seam exists.
- [ ] Re-run the focused server/repository tests.

### Task 6: Backend release gate

- [ ] Run `pytest -q` and require zero failures, allowing only the two documented opt-in cloud skips.
- [ ] Run `pip check` and require no broken requirements.
- [ ] Run `git diff --check` and inspect the complete branch diff.
- [ ] Commit the verified backend hardening changes.

