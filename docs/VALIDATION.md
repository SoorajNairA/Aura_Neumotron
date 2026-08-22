# Reliability validation

The integrated product surface covers Create, Modify, Inspect, Reopen, Undo,
linked representations, and verification. Authoritative graph and revision
state lives on the server; browser state is presentation-only.

## Failure matrix

| Failure | Expected behavior | Validation |
|---|---|---|
| AI provider timeout, quota, or unavailability | bounded request; clearly labelled deterministic fallback when policy permits | provider and workspace tests |
| Malformed AI response | one schema repair attempt, then fallback or an actionable error | planner and modification tests |
| Authentication or IAM failure | actionable service error; no pretend cloud success | provider tests |
| Invalid free-form edit | no graph mutation; the UI explains why no proposal was produced | modification and browser tests |
| tscircuit missing, timeout, malformed output, or non-zero exit | graph remains committed; schematic uses the connection fallback | representation tests |
| Browser CAD, WASM, or worker failure | semantic proxy remains selectable; terminal fallback state is visible | browser suite |
| Artifact upload/read failure | no ready metadata for missing content; graph remains valid | cloud adapter tests |
| Database transaction failure | no partial graph, revision, verification, or event publication | repository tests |
| WebSocket loss | bounded reconnect with event replay and client deduplication; manual reconnect after exhaustion | server and browser tests |
| Process restart | persisted projects reconstruct; abandoned generation becomes an explicit retryable fallback | persistence tests |
| Duplicate write | stable operation/idempotency key returns the first authoritative result | workspace tests |
| Stale representation result | mismatched project, revision, operation, or generation is ignored | workspace tests |

## Timeout and retry policy

Defaults are environment-configurable: Planner 20 seconds
(`AURA_PLANNER_TIMEOUT`), cloud provider 20 seconds
(`AURA_VERTEX_TIMEOUT_SECONDS`), tscircuit 8 seconds
(`AURA_CIRCUIT_TIMEOUT`), artifact storage 10 seconds
(`AURA_ARTIFACT_TIMEOUT`), and PostgreSQL pool acquisition 5 seconds
(`AURA_DB_POOL_TIMEOUT`). Browser CAD initialization has its own bounded
timeout. WebSocket reconnect uses bounded exponential delay.

Structured output gets one repair attempt rather than unbounded retries.
Authentication, verification failures, and invalid specifications are not
blindly retried. AI latency is variable; the UI shows proposal progress and
keeps the graph unchanged until a valid proposal exists and is accepted.

## Local release checks

Run:

```powershell
.\scripts\test.ps1 -Module all

Set-Location src\aura\workspace\web\frontend
npm run test:browser
npm run test:electron
npm run package
```

Before publishing, also inspect `git diff`, run `git diff --check`, and verify
the quick-start path against `/health/live`.

## Development and demo operation

Development mode uses local SQLite and artifacts. Demo mode changes operations,
not engineering rules: set `AURA_DEMO_MODE=true` when required. It never
bypasses planning or verification.

Run `aura-demo check --url URL [--project-id ID]` immediately before a hosted
demo. It checks liveness, readiness, build identity, the project index,
representations, verification, and local generator availability. Use
`aura-demo reset irrigation --url URL` only for the known deterministic demo
namespace; it does not truncate a database or delete an artifact bucket.

The private cloud service remains IAM-protected. Runtime images install only
server, provider, and cloud dependencies—never the voice, Ollama, Unreal,
PySide, or GPU stack. `/health/live` exposes only version, commit, environment,
and status.
