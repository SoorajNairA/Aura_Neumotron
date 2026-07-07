# Reliability validation

Goal 10 freezes the Goals 1–9 product surface and hardens Create, Modify, Inspect,
Reopen, and Undo. Authoritative graph/revision state lives on the server; browser
state is presentation-only.

## Failure matrix

| Failure | Expected behavior | Validation |
|---|---|---|
| Vertex timeout/unavailable/quota | bounded provider retry, then clearly labelled deterministic fallback when policy permits | provider and Workspace tests |
| Vertex malformed response | one schema repair, then fallback | `test_workspace_server.py` |
| Vertex authentication/IAM | actionable 503; no pretend cloud success | provider tests |
| tCircuit missing/timeout/malformed/nonzero | graph remains committed; schematic uses connection fallback | `test_representations.py` |
| Browser CAD/WASM/worker failure | semantic proxy remains selectable; terminal fallback state | browser suite |
| GCS upload/read failure | no ready metadata for missing content; graph remains valid | cloud-adapter tests |
| Database transaction failure | no partial graph, revision, Verification, or event publication | repository tests |
| WebSocket loss | six bounded reconnects, `afterEventId` replay and client dedupe; manual Reconnect thereafter | server/browser tests |
| Cloud/process restart | persisted project reconstructs; orphaned generation becomes explicit retryable fallback | Goal 10 tests |
| Speech failure | text narration continues; speech queue can be stopped | Goal 9/browser tests |
| Duplicate write | stable operation/idempotency key returns the first authoritative result | Goal 10 tests |
| Stale CAD result | mismatched project, revision, operation, or generation is ignored | Goal 10 tests |

## Timeout and retry policy

Defaults are environment-configurable: Planner 20 s (`AURA_PLANNER_TIMEOUT`),
Vertex 20 s (`AURA_VERTEX_TIMEOUT_SECONDS`), tCircuit 8 s
(`AURA_CIRCUIT_TIMEOUT`), GCS 10 s (`AURA_ARTIFACT_TIMEOUT`), PostgreSQL pool
acquisition 5 s (`AURA_DB_POOL_TIMEOUT`), and browser CAD initialization 10 s.
WebSocket reconnect uses six attempts with exponential delay capped at 15 s.
Invalid structured data is repaired once, not retried indefinitely. Authentication,
Verification, and invalid specifications are never blindly retried.

## Development and demo operation

Development mode uses local SQLite/artifacts and Cloud Run may use zero minimum
instances. Demo mode changes operations only: set `AURA_DEMO_MODE=true`, and set
the existing Cloud Run minimum-instances configuration to 1 if measured cold start
warrants it. It never bypasses planning or Verification.

Run `aura-demo check --url URL [--project-id ID]` immediately before presenting.
It is fast and read-only: it checks liveness, readiness, build identity, project
index, selected benchmark representations, Verification, and local Node presence.
Use `aura-demo reset irrigation --url URL` to create/reopen only the known,
deterministic benchmark namespace; it never truncates a database or deletes a
bucket. The UI labels saved projects separately from new live requests.

## Hackathon performance budgets

Targets, not guarantees: warm list under 500 ms; persisted reopen under 1 s;
modification commit under 500 ms excluding generators; current Verification under
100 ms; typical Vertex modification under 5 s; typical complete cloud readiness
under 10 s. Record actual local and cloud smoke timings with the release validation
results. Progressive state is shown as graph/proxies, circuit, then generated CAD.

The private Cloud Run service must remain IAM-protected. Runtime images install
only server, Vertex, and cloud extras—no voice, Ollama, Unreal, PySide, or GPU stack.
`/health/live` exposes only version, commit, and environment build identity.
