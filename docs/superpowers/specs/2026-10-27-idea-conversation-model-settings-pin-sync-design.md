# Idea conversation, model settings, shared pin map — design

Date: 2026-10-27 · Branch: `AURA-nemotron_test1` · Deadline: 2026-10-30 17:00 UTC
Scope: phases 1–3 of the conversational IoT roadmap. Phases 4–7 (component library, detailed
representations, fault-injection simulation, connected hardware incl. serial log) are out of scope.

## Goals

1. A vague idea never dead-ends. AURA converses, gathers requirements, and proposes a design the
   user approves before anything is committed.
2. The user can choose the model: Nemotron on Nebius by default, any OpenAI-compatible endpoint, or a
   local Ollama endpoint, with keys stored securely and failures reported honestly.
3. Wiring, firmware and checks share one pin map. A pin change is a graph revision; firmware and
   checks follow it; undo works.

## Global rules

- AI proposes; deterministic code decides (scope, families, compatibility, GPIO validity).
- No silent provider switching and no deterministic fallback presented as live output.
- Secrets never reach the frontend, logs, exports, project files or git.
- Estimates, assumptions and unavailable prices are labelled as such. No invented ratings or prices.
- Existing APIs keep working: `POST /api/projects` stays (tests and scripts use it).

## Phase 1 — Idea conversation

### Session model (`src/aura/workspace/ideas.py`)

`IdeaSession`: `sessionId`, `originalIdea`, `messages[]` (role, text, timestamp),
`requirements` (dict keyed by slot), `openQuestions[]`, `scope` (`IN_SCOPE` | `OUT_OF_SCOPE` |
`UNKNOWN`, reasons, alternative), `proposal` (or null), `projectId` (set on approval), `createdAt`,
`updatedAt`.

Slots: `function`, `budget`, `power`, `connectivity`, `dimensions`, `environment`, `experience`.
Each slot: `value` (string), `source` (`user` | `default` | `assumption`), `status`
(`agreed` | `proposed` | `open`), `tradeoff` (string, optional).
Required before proposing: `function` agreed, and `power` agreed or defaulted. Other slots may stay
`default`/`assumption` and are listed as such on the proposal.

Persistence follows the `work_items` pattern: an `idea_sessions(session_id PK, session_json,
updated_at)` table in the SQLite repository and the Postgres repository, plus protocol methods
`save_idea_session` / `get_idea_session`.

### Turn (`POST /api/ideas`, `POST /api/ideas/{id}/messages`)

One structured model call per user message (`generate_structured`, JSON schema) returning: slot
updates, at most 3 questions (each with a suggested default and tradeoff), named component families,
and a scope opinion. Then deterministic code:
- drops slot updates with unknown slot names;
- rejects families not in `CAPABILITY_MANIFEST["supportedComponentFamilies"]` (recorded as an
  unsupported need, explained to the user);
- runs `classify_objective` on the composed requirement summary (not the raw idea). Its
  `UNSUPPORTED` verdict overrides the model; the model can never upgrade scope.
- An out-of-scope idea stays conversational: reasons + an achievable low-voltage alternative the user
  can accept as the new function.

Provider failure on a turn returns the provider's honest error (Phase 2 codes) and leaves the session
unchanged so the message can be retried.

### Proposal and approval

- `POST /api/ideas/{id}/proposal`: composes the objective from agreed requirements, runs the existing
  live planner + verification without persisting a project, stores the outcome on the session, and
  returns the card: components (part number, role, key documented specs, evidence source + date),
  alternatives per role, cost, limitations, assumptions.
- Alternatives: for each role, catalogue items of the same family with compatible voltage, ranked by
  the user's stated priority (cost, power, size). Ranking uses only documented catalogue fields; ties
  and missing data are shown, no item is called "best".
- Cost: new optional catalogue fields `price_usd`, `price_source`, `price_retrieved` for parts in the
  ESP32 fan design, researched with dated sources. Parts without them show "price unavailable"; the
  total is labelled "estimate" and lists excluded parts.
- `POST /api/ideas/{id}/approve`: creates the project from the stored plan (no re-plan) through the
  same persistence path as `create`; sets `projectId`. A stale or missing proposal returns 409.

### UI

The welcome BUILD box starts a session and opens a chat panel: messages, a requirements card (slot,
value, source badge), suggested-default chips, and a **Propose design** button enabled once required
slots are met. The proposal card has **Approve** and **Change**. Approve opens the new project.
Settings → New design opens the same flow.

## Phase 2 — Model settings

- Profile: `profileId`, `label`, `kind` (`nebius` | `openai_compatible` | `ollama_local`),
  `baseUrl`, `model`, `hasKey` (derived). Stored in `aura_data_dir()/model_profiles.json` with the
  active profile id. Keys stored with `keyring` (Windows Credential Manager), service `aura-model`,
  username = profile id. Keys are write-only over the API.
- Default profile `nemotron-nebius` is built from existing `NEBIUS_*` env vars; env still works.
- Validation: kind, baseUrl and model are required; a key alone is never a valid profile. `https` is
  required except for `localhost`/`127.0.0.1`. `ollama_local` needs no key.
- All kinds use the existing OpenAI-compatible adapter (`NebiusPlannerProvider`, generalized to take
  the provider name for messages). `chat_template_kwargs` is sent only when the model id contains
  `nemotron`.
- API: `GET /api/model-profiles`, `PUT /api/model-profiles/{id}`, `PUT .../{id}/key`,
  `DELETE /api/model-profiles/{id}`, `POST .../{id}/test`, `POST /api/model-profiles/active`.
  Test sends one tiny structured request and returns `ok` or the real error class and message
  (auth rejected, timeout, unreachable, malformed response). Errors are scrubbed of the key.
- The active profile changes only by user action. Failures surface; no automatic switch.
- The model badge becomes a menu: profiles list, active mark, "Model settings…".

## Phase 3 — Shared pin map

- Wiring view: clicking a controller-side wire end opens a GPIO picker listing
  `ESP32_OUTPUT_GPIOS` (input-only pins only for input roles). Choosing creates a deterministic
  `SET_PARAMETER` proposal on the controller `gpio_map` through the existing proposal → verification
  → commit path (revisions, undo, narration unchanged).
- `ELEC_GPIO` verification decides; invalid choices (duplicate, input-only for output, strapping
  pins) are rejected with the finding text.
- Firmware is already generated from `gpio_map`; a new revision regenerates it. Compile results of
  older revisions show "stale".
- Editable firmware: only the `fanControl` block (between its markers) is editable in the Code view.
  Edits are stored per project with the revision they were made on
  (`PUT /api/projects/{id}/firmware/edit`). Compile uses the edited block spliced into the generated
  sketch. If the graph revision changes, the edit is kept and flagged "review after revision change".
- Fix: the Code view shows the error and a retry when the firmware request fails.

## Testing / acceptance

- Phase 1: unit tests for slot merging, family rejection, scope override, alternative ranking,
  cost labelling; API tests for session persistence, proposal, approve (incl. stale 409); a
  Playwright test with mocked API; one live Nemotron run: "a fan that turns on when my room is hot"
  → questions → propose → approve → ready project.
- Phase 2: tests that keys never appear in any API response or log line; validation (key-only
  profile rejected, http non-local rejected); test-connection error mapping; no fallback on failure;
  Playwright settings flow.
- Phase 3: pin change creates a revision, firmware pins change, undo restores them; invalid pin
  rejected by `ELEC_GPIO`; edited block compiles (real arduino-cli); stale flag; Code view error state.
- Full suites stay at current baselines (Python: 1 known failure; e2e: 6 known failures).

## Known defects addressed

Keyword-only scope gate (Phase 1), env-only model config (Phase 2), wiring edits not reaching
firmware and Code view stuck on load failure (Phase 3).

## Ownership note

Phase 1–3 touch integration-owned code (`server.py`, persistence, planner orchestration). This
branch is the integration branch for this work; changes are called out per commit.
