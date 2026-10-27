# Idea conversation, model settings, shared pin map — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the NEEDS_CLARIFICATION dead end with an approved-proposal conversation, add user-chosen model profiles with secure keys, and make pin changes a graph revision that firmware follows.

**Architecture:** A persisted `IdeaSession` collects requirement slots through structured model turns; deterministic code gates scope and families; a cached planner outcome is shown as a proposal and committed on approval through the existing create path. Model profiles feed the existing OpenAI-compatible adapter. Pin changes are deterministic modification proposals committed through the existing proposal/commit path.

**Tech Stack:** Python 3.12, FastAPI, SQLite, `keyring`, React 18 + TypeScript, vitest, Playwright, arduino-cli.

**Spec:** `docs/superpowers/specs/2026-10-27-idea-conversation-model-settings-pin-sync-design.md`

## Global Constraints

- AI proposes; deterministic code decides scope (`classify_objective`), families (`CAPABILITY_MANIFEST["supportedComponentFamilies"]`) and GPIO validity (`ELEC_GPIO`).
- No silent provider switch; provider failure returns its error, never a fallback labelled live.
- API keys never appear in any API response, log line, project file, export or git.
- `POST /api/projects` keeps its current contract.
- Unpriced parts show "price unavailable"; totals are labelled "estimate" and list excluded parts.
- Slots: `function, budget, power, connectivity, dimensions, environment, experience`. Max 3 questions per turn.
- Frontend files: CRLF line endings; edit with the CRLF-aware approach already used in this repo.
- Baselines to keep: Python 1 known failure (`test_startup_boundaries`); e2e 6 known failures.
- Run tests with `export PATH="/d/Aura/Aura_Neumotron/.venv/Scripts:$PATH"`; Python suites with `--ignore=tests/test_runtime_optimizations.py --ignore=tests/test_xtts_backend.py` (numpy not installed).

## Review Focus

1. Model returns slot names/families outside the allowed sets → dropped or reported, never stored as agreed.
2. Approve after the backend restarted (proposal cache lost) → 409 `PROPOSAL_EXPIRED`, user can re-propose; no half-created project.
3. A profile with only a key, or `http://` to a non-local host → rejected with a clear message.
4. Pin change on a stale base revision or to a GPIO already used → 409 / rejected by verification; firmware unchanged.
5. Edited `fanControl` block that no longer compiles → compile reports errors; generated pins/thresholds untouched.

---

## Phase 1 — Idea conversation

### Task 1: Dated prices for the fan parts

**Files:** Modify `src/aura/verification/catalogue.py`; Test `tests/test_idea_pricing.py`

**Interfaces:** Produces `ComponentDefinition.price: dict | None` with keys `usd: float`, `source: str` (URL), `retrieved: str` (ISO date), included in `to_dict()` as `"price"`.

- [ ] Write `test_fan_parts_have_dated_prices`: for ids `esp32-devkit-v1, ds18b20-module, logic-mosfet-module, dc-fan-5v, resistor-4k7, 1n4007-diode, supply-usb-5v-1a`, `price` is either None or has `usd>0`, `source` starting `https://`, `retrieved` matching `\d{4}-\d{2}-\d{2}`; at least 5 of 7 priced. `test_unpriced_parts_have_no_price`: `mg996r-servo` → `to_dict()["price"] is None` unless researched.
- [ ] Run → FAIL (no `price`).
- [ ] Research each part with WebSearch (distributor or maker listing); record single-unit USD price, URL, retrieval date 2026-10-27. Do not guess: unfound → None.
- [ ] Run → PASS; run `tests/test_goal8_verification.py`.
- [ ] Commit.

### Task 2: Idea session domain rules

**Files:** Create `src/aura/workspace/ideas.py`; Test `tests/test_ideas.py`

**Interfaces (Produces):**
- `SLOTS: tuple[str,...]`, `REQUIRED=("function","power")`
- `new_session(idea: str) -> dict` (sessionId `idea-<hex>`, originalIdea, messages, requirements {slot: {value:"",source:"assumption",status:"open",tradeoff:""}}, openQuestions [], scope {status:"UNKNOWN",reasons:[],alternative:None}, unsupportedNeeds [], proposal None, projectId None, timestamps)
- `apply_turn(session: dict, user_text: str, turn: dict) -> dict` — `turn` = model output `{slots:[{slot,value,source,status,tradeoff}], questions:[{slot,question,suggestedDefault,tradeoff}], families:[str], scope:{status,reasons,alternative}, reply:str}`.
- `compose_objective(session) -> str`
- `ready_to_propose(session) -> bool`
- `rank_alternatives(definition_id: str, priority: str) -> list[dict]`
- `cost_summary(definition_ids: list[str]) -> dict` → `{totalUsd, estimate: True, excluded: [ids], items: [...]}`

- [ ] Tests: `test_unknown_slot_dropped`; `test_unsupported_family_recorded_not_agreed` (family `"jet_engine"` → in `unsupportedNeeds`); `test_questions_capped_at_three`; `test_scope_unsupported_overrides_model` (model says IN_SCOPE, composed objective contains "aircraft" → `UNSUPPORTED`); `test_model_cannot_upgrade_unsupported`; `test_ready_requires_function_agreed_and_power_set`; `test_compose_objective_contains_function_and_power`; `test_alternatives_same_family_ranked_by_price_then_unpriced_last` (no item labelled best); `test_cost_summary_lists_excluded`.
- [ ] Run → FAIL. Implement. Scope rule: `classify_objective(compose_objective(s))`; `UNSUPPORTED` wins; `NEEDS_CLARIFICATION` keeps model status only if model says `OUT_OF_SCOPE`, else `UNKNOWN`. Run → PASS. Commit.

### Task 3: Persist idea sessions

**Files:** Modify `src/aura/infrastructure/persistence/project_repository.py`; Test `tests/test_ideas.py`

**Interfaces:** `save_idea_session(session: dict) -> None`, `get_idea_session(session_id: str) -> dict | None` on the protocol and `SQLiteProjectRepository`; table `idea_sessions(session_id TEXT PRIMARY KEY, session_json TEXT NOT NULL, updated_at TEXT NOT NULL)` created with `CREATE TABLE IF NOT EXISTS` like `work_items`.

- [ ] Test `test_idea_session_round_trip_survives_reopen` (file DB, close, reopen, get). Run → FAIL. Implement (Postgres repo has no work_items either; SQLite only — ruling). Run → PASS. Commit.

### Task 4: Idea agent turn

**Files:** Modify `src/aura/workspace/ideas.py`; Test `tests/test_ideas.py`

**Interfaces:** `TURN_SCHEMA: dict` (JSON schema for the `turn` shape, strings `maxLength` 400); `run_turn(provider, session: dict, user_text: str) -> dict` calls `provider.generate_structured(messages, system_prompt=..., max_tokens=1200, response_schema=TURN_SCHEMA)`, parses JSON, returns `apply_turn(...)`. System prompt includes `compact_capability_context()`, current slots, and the rules: only ask about open relevant slots, suggest defaults with tradeoffs, explain unsupported needs and offer a low-voltage alternative.

- [ ] Tests with a fake provider: `test_run_turn_passes_schema_and_history`; `test_run_turn_provider_error_leaves_session_unchanged` (raises → exception propagates, input dict not mutated). Run → FAIL; implement; PASS; commit.

### Task 5: Idea API and approve-from-proposal

**Files:** Modify `src/aura/workspace/server.py`; Test `tests/test_ideas_api.py`

**Interfaces:**
- `WorkspaceApplication._create_serialized(body, *, creation_info=None, outcome: PlanningOutcome | None = None)` — when `outcome` given, skip `self.plan(body)`.
- `application.idea_proposals: dict[str, PlanningOutcome]` (bounded like `modification_proposals`).
- Routes: `POST /api/ideas {idea}` → 201 session after first turn; `GET /api/ideas/{id}`; `POST /api/ideas/{id}/messages {text}`; `POST /api/ideas/{id}/proposal` → `{proposalId, objective, components:[{semanticId,name,partNumber,role,specs,evidence,alternatives}], cost, limitations, assumptions}`; `POST /api/ideas/{id}/approve {proposalId}` → project payload.
- Errors: provider failure → 502/503/504 with `{code, message}` (`MODEL_AUTHENTICATION`, `MODEL_TIMEOUT`, `MODEL_UNAVAILABLE`); not ready → 409 `REQUIREMENTS_INCOMPLETE`; unknown/expired proposal → 409 `PROPOSAL_EXPIRED`; out-of-scope → 409 `OUT_OF_SCOPE`.

- [ ] Tests (fake structured provider via `create_app(provider=...)`, `tmp_path` DB): `test_create_session_runs_first_turn`; `test_messages_persist`; `test_proposal_requires_ready`; `test_proposal_does_not_create_project` (`GET /api/projects` unchanged); `test_approve_creates_project_from_cached_plan` (planner called once total); `test_approve_unknown_proposal_409`; `test_provider_failure_returns_error_and_keeps_session`; `test_direct_create_contract_unchanged`.
- [ ] Run → FAIL; implement; PASS; full Python suite; GitNexus impact on `_create_serialized` first (warn if HIGH/CRITICAL); detect-changes; commit.

### Task 6: Idea chat UI

**Files:** Create `src/aura/workspace/web/frontend/src/IdeaChat.tsx`, `IdeaChat.test.ts` (pure helpers); Modify `WorkspaceApp.tsx` (welcome BUILD → `IdeaChat`), `styles.css`; e2e `e2e/idea-chat.spec.ts`

**Interfaces:** `IdeaChat({onApproved:(projectId:string)=>void})`; helpers `slotBadge(source)`, `canPropose(session)`; test ids `idea-chat`, `idea-message`, `requirements-card`, `slot-<name>`, `default-chip`, `propose-design`, `proposal-card`, `approve-design`, `change-design`, `cost-total`.

- [ ] e2e (mocked API): type idea → assistant reply + questions visible; click a default chip → sends message; Propose enabled only when mocked session ready; proposal card shows "price unavailable" item and "estimate" total; Approve navigates to project; out-of-scope reply shows alternative text. Provider error shows the error code and keeps the typed text.
- [ ] Run → FAIL; implement (ivory/sage tokens already in `styles.css`); build; PASS; full e2e at baseline; commit.

### Task 7: Live acceptance run

- [ ] With the real backend and Nebius key: script `scripts/idea_live_check.py` (keep, documented in README) posts "a fan that turns on when my room is hot", answers questions with suggested defaults until ready, proposes, approves; prints session slots, proposal parts, cost, project status. Expected: project status `ready*`, `planningMode: live_model`. Record output in the ledger. Commit script.

## Phase 2 — Model settings

### Task 8: Model profiles core

**Files:** Create `src/aura/app/model_profiles.py`; Modify `src/aura/infrastructure/llm/nebius.py` (provider name param; `chat_template_kwargs` only when `"nemotron" in model.lower()`), `src/aura/workspace/server.py` (`_default_provider` uses active profile), `pyproject.toml`/`requirements.txt` (`keyring`); Test `tests/test_model_profiles.py`

**Interfaces:**
- `ProfileStore(path: Path, keyring_backend=None)`: `list() -> list[dict]` (no keys; `hasKey`), `upsert(profile: dict) -> dict`, `set_key(profile_id, key)`, `delete(profile_id)`, `active() -> dict`, `set_active(profile_id)`, `build_provider(profile_id=None, timeout) -> NebiusPlannerProvider`, `test(profile_id) -> {ok: bool, code?: str, message?: str, latencyMs}`.
- `validate_profile(profile) -> list[str]` errors.
- Default `nemotron-nebius` from `NEBIUS_*` env; env key used when no stored key.
- `NebiusPlannerProvider(..., provider_name="nebius")`; diagnostics `backend` = provider_name.

- [ ] Tests (keyring in-memory backend): `test_key_only_profile_rejected`; `test_http_non_local_rejected_localhost_allowed`; `test_list_never_contains_key` (serialize to JSON, assert key string absent); `test_ollama_local_needs_no_key`; `test_default_profile_from_env`; `test_build_provider_uses_profile`; `test_nemotron_only_template_kwargs`; `test_test_connection_maps_401_and_timeout` (fake session); `test_no_fallback_when_active_fails` (`_default_provider` raises, no other profile tried); `test_errors_scrub_key`.
- [ ] Run → FAIL; `pip install keyring`; implement; PASS; full Python suite; impact on `_default_provider`, `NebiusPlannerProvider`; commit.

### Task 9: Model settings API and UI

**Files:** Modify `server.py`; Create `frontend/src/ModelSettings.tsx`; Modify `WorkspaceApp.tsx` (badge → menu; Settings → "Model settings"), `studio.ts` (`modelBadge` reads active profile label); e2e `e2e/model-settings.spec.ts`; Test `tests/test_model_profiles_api.py`

**Interfaces:** `GET /api/model-profiles` → `{active, profiles}`; `PUT /api/model-profiles/{id}`; `PUT /api/model-profiles/{id}/key {key}` → 204; `DELETE /api/model-profiles/{id}`; `POST /api/model-profiles/{id}/test`; `POST /api/model-profiles/active {profileId}`.

- [ ] API tests: key PUT then GET has `hasKey:true` and no key text anywhere in body; invalid profile 422 with errors; set active changes provider used by next idea turn. e2e (mocked): add OpenAI-compatible profile, save key (input type password, cleared after save), Test shows error text from mock, set active updates badge.
- [ ] FAIL → implement → PASS; baselines; commit.

## Phase 3 — Shared pin map

### Task 10: Pin change as a revision

**Files:** Modify `src/aura/workspace/modifications.py` (`propose_pin_change`), `server.py` (route); Modify `WorkspaceApp.tsx` (GPIO picker on controller wire end in Wiring view); Tests `tests/test_pin_change.py`, e2e in `e2e/studio.spec.ts`

**Interfaces:** `propose_pin_change(graph, base: int, controller_id: str, port: str, gpio: int) -> ModificationProposal` — UPDATE_ENTITY of controller `parameters.gpio_map[port]`; raises `ValueError("stale_revision")`, `ModificationError("PIN_NOT_ALLOWED")` for GPIO not in `ESP32_OUTPUT_GPIOS` (or strapping pin 5 — ruling: picker/proposal level only, `ELEC_GPIO` unchanged so existing plans stay valid). Route `POST /api/projects/{id}/pin-proposals {baseRevision, controllerId, port, gpio}` → proposal dict, stored in `modification_proposals`, committed via existing commit route.

- [ ] Tests on the fan graph (deterministic create): `test_pin_change_commit_updates_firmware_pins` (fan_gate 16→17, `GET /firmware` pins updated, revision +1); `test_undo_restores_pin`; `test_duplicate_gpio_rejected_by_verification`; `test_input_only_or_strapping_rejected`; `test_stale_base_409`; `test_compile_cache_marked_stale_after_pin_change`. e2e (mocked): click controller wire end → picker → choose → proposal summary → commit called.
- [ ] FAIL → implement → PASS; impact on commit path; baselines; commit.

### Task 11: Editable fanControl and Code view errors

**Files:** Modify `src/aura/firmware/sketch.py` (`splice_control(source, block) -> str`, `extract_control(source) -> str`), `server.py` (`PUT /api/projects/{id}/firmware/edit {block, revisionId}`; GET returns `edit: {block, revisionId, needsReview}`; compile uses edit), `project_repository.py` (`save_firmware_edit`/`get_firmware_edit`, table `firmware_edits(project_id TEXT PRIMARY KEY, block TEXT NOT NULL, revision_id TEXT NOT NULL, updated_at TEXT NOT NULL)`, `CREATE TABLE IF NOT EXISTS`); Modify `CodeView.tsx` (editable textarea for the block only, Save, Reset to generated, error + Retry state); Tests `tests/test_firmware_edit.py`, e2e.

- [ ] Tests: `test_splice_replaces_only_block`; `test_edit_must_keep_signature` (block without `bool fanControl(` → 422); `test_compile_uses_edit` (real arduino-cli if available, else skip with reason); `test_bad_edit_compile_reports_errors`; `test_edit_flagged_after_revision_change`; e2e: firmware GET 500 → Code view shows error and Retry; edit + save shows "edited" badge.
- [ ] FAIL → implement → PASS; full suites; commit.

### Task 12: Docs and wrap

- [ ] Update `docs/active/README.md` §0 status and README (idea flow, model settings, pin edits, keyring). Commit.
