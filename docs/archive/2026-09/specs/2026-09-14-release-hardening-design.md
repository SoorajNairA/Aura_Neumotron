# AURA Release Hardening Design

## Objective

Turn the current demo-stable application into a release-quality workspace by closing the confirmed correctness, recovery, security, responsive, accessibility, performance, dependency, and test-integrity gaps without changing established API response contracts.

## Scope and ownership

- `hackathon-integration` owns capability classification, request orchestration, workflow state, concurrency, provider execution, shared tests, and final integration.
- `feature/3d` owns representation generation and recovery behavior in the representation service and its focused tests.
- `feature/ui` owns the React/Electron interface, legacy static assets, frontend dependencies, and browser/desktop tests.
- `main` remains untouched until the integrated tree passes the release gate. Short-lived branches are deleted after the verified merge.

## Backend design

Capability classification becomes evidence-based. Supported low-voltage/mechatronic nouns and actions produce supported results; explicit out-of-domain categories produce unsupported results using token/phrase boundaries; ambiguous objectives request clarification. Generic prose no longer silently compiles into an ESP32 system, and incidental words such as “building” no longer trigger a domain rejection.

Project creation records representation failures as recoverable project state. A retry of an existing project resumes requested or failed representations instead of returning a permanently incomplete record. Artifact failures are converted to failed representation records with useful error metadata rather than escaping after the graph commit.

Pending scenarios are additive and project-scoped. Volatile caches receive explicit bounds and consumed entries are removed. Event fan-out uses bounded queues and drops disconnected/slow subscribers without allowing unbounded memory growth. Provider calls use one bounded executor instead of creating an abandoned executor per timeout. Project creation is serialized only for identical objectives, while idempotency lookup uses repository-level event filtering rather than repeatedly walking every project.

## Frontend and desktop design

Workspace hydration separates required project/graph data from optional assembly, verification, narration, CAD, and schematic data. Optional failures produce localized retryable error states and never erase the selected project.

The shell becomes fluid from 360px upward: navigation and inspector become drawers on compact viewports, main content remains scrollable, controls meet minimum target sizes, typography remains legible, and zoom/split-screen operation is supported. Dialogs receive complete semantics, initial focus, focus trapping, Escape dismissal, and focus restoration. Canvas functions retain equivalent component selection through the hierarchy.

Rendering becomes demand-driven. Three.js pauses while hidden or unchanged, schematic panning updates its transform outside React’s render path, and layout-property transitions are removed. Heavy CAD code stays lazy. The active bundle is split at representation boundaries and warning thresholds are restored to meaningful values.

All colors, spacing, typography, and surface treatments use tokens. A light/dark/system theme contract is added. Reduced-motion rules disable decorative motion while preserving state visibility.

The obsolete `/assets/index.html` application is no longer publicly reachable, and unsafe legacy scripts/styles are removed. Electron smoke success requires the real backend application to load; the offline shell is a distinct failure unless the recovery test explicitly requests it. Duplicate unused frontend implementations are removed or folded into focused modules.

## Dependencies and security

Frontend dependencies are upgraded only along compatible release lines proven by TypeScript, unit, browser, and production build checks. The release target is zero actionable production advisories. If an upstream-only advisory has no compatible remediation, it must be documented with reachability evidence and a pinned follow-up rather than silently accepted. Security documentation is regenerated from the final lockfile audit.

## Error handling and compatibility

Existing successful response schemas and persisted graph formats remain unchanged. New error payloads use existing FastAPI detail conventions. Recovery is idempotent: retrying project creation or representation generation does not create duplicate revisions or artifacts. UI degradation is local and reversible through retry.

## Acceptance criteria

- Unsupported software, financial, aviation, and large-scale industrial objectives are rejected or clarified; supported fan/robotics/mechatronic prompts continue to work.
- Artifact write failures leave a reloadable project with a failed representation that a retry can regenerate.
- Multiple projects can hold and apply independent scenarios.
- Slow providers and WebSocket clients cannot grow threads or queues without bound.
- Browser layout works at 360, 768, 1024, 1366, and 1920 CSS pixels and at 200% zoom.
- Keyboard-only dialog flows pass; normal text meets WCAG AA contrast; actionable controls meet the chosen 44px compact target.
- Optional endpoint failures never clear the active project.
- Legacy UI URLs do not serve executable application HTML.
- Electron smoke fails offline and passes against the live app.
- TypeScript, production build, Vitest, Playwright, Electron, Python, `pip check`, `npm audit --omit=dev`, `git diff --check`, and the final Impeccable audit satisfy the release gate.
