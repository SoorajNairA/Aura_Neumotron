# Representation Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure artifact failures remain visible, reloadable, and retryable instead of stranding committed projects.

**Architecture:** Representation generation owns conversion of generator/storage exceptions into failed records. Project orchestration detects incomplete existing records and resumes only requested/failed representations idempotently.

**Tech Stack:** Python 3.12, representation service, project repository, pytest.

**Spec:** `docs/superpowers/specs/2026-09-14-release-hardening-design.md`

## Global Constraints

- Preserve representation record and project response schemas.
- Do not create duplicate artifacts or graph revisions during retry.
- Representation-owned files are committed on `feature/3d`; shared orchestration is applied on `hackathon-integration`.

---

### Task 1: Failed artifact writes become failed records

**Files:**
- Modify: `src/aura/workspace/representation_service.py`
- Test: `tests/test_representations.py`

**Interfaces:**
- Consumes: `RepresentationService.persist_specs(graph, specs)`
- Produces: one terminal `FAILED` record per failed write with an actionable error string.

- [ ] Add a repository double whose mechanical `write_artifact` raises `OSError("disk full")`; assert `persist_specs` returns a failed mechanical record rather than raising.
- [ ] Run `pytest tests/test_representations.py -q` and confirm the test fails with the uncaught `OSError`.
- [ ] Catch storage/generator failures at the per-representation boundary, mark the artifact failed when possible, and return a failed representation record.
- [ ] Re-run the focused test file and confirm existing successful generation still passes.

### Task 2: Retry incomplete representations

**Files:**
- Modify: `src/aura/workspace/server.py` on `hackathon-integration`
- Test: `tests/test_workspace_server.py`

**Interfaces:**
- Produces: an existing-project retry that regenerates only `REQUESTED` or `FAILED` representations and returns the existing project ID.

- [ ] Add an integration test that forces the first artifact write to fail, restores storage, repeats the same create request, and asserts the same project ID becomes ready without a duplicate revision.
- [ ] Run the focused test and confirm retry currently returns the incomplete record unchanged.
- [ ] Add an idempotent resume helper before the existing-project early return and persist the updated representation records/events.
- [ ] Re-run the focused test and representation lifecycle tests.

### Task 3: Recovery release gate

- [ ] Run `pytest tests/test_representations.py tests/test_workspace_server.py tests/test_lifecycle_torture.py -q`.
- [ ] Run `git diff --check` and inspect the complete representation diff.
- [ ] Commit `feature/3d`, merge it into `hackathon-integration`, then re-run the same focused suite.

