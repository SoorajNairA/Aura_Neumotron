# AURA Hackathon Collaboration Rules

## Branch workflow

- `main` is the last known stable demo. Never work on or modify `main` directly.
- Feature work belongs on exactly one owned branch: `feature/3d`, `feature/verification`, or `feature/ui`.
- Combine and validate feature work only on `hackathon-integration`.
- Never merge a feature branch automatically into `main`. Promotion from `hackathon-integration` to `main` is an explicit, human-reviewed integration-owner action.
- Shared contracts and core orchestration are integration-owned. Feature agents must not silently modify them; coordinate the change and let the integration owner apply or explicitly approve it.

## Engineering rules

- Make the smallest change that fully solves the assigned problem.
- Inspect the existing implementation, nearby tests, and call sites before creating an abstraction or changing behavior.
- Preserve existing APIs and data contracts unless a change is necessary and explicitly coordinated.
- Do not add unnecessary files, wrappers, dependencies, helpers, layers, configuration, or rewrites.
- Do not perform unrelated refactors, formatting sweeps, renames, or cleanup.
- Do not add placeholder, fake, mocked, or hard-coded production implementations. Test doubles belong only in tests.
- Follow existing project patterns and keep code direct, readable, and removable.
- Run the relevant tests before declaring work complete.
- Inspect `git diff` and `git diff --check` before declaring work complete.

## Module ownership

### `feature/3d`

Owns the representation implementation and focused tests:

- `src/aura/workspace/representations.py`
- `src/aura/workspace/representation_service.py`
- `src/aura/workspace/prototype.py`
- `src/aura/workspace/web/representation/`
- `src/aura/workspace/web/frontend/generators/`
- representation, physical-assembly, and interface-compiler tests directly associated with those files

### `feature/verification`

Owns:

- `src/aura/verification/`
- verification-focused tests, including `tests/test_goal8_verification.py`

### `feature/ui`

Owns presentation and desktop-shell code:

- `src/aura/workspace/web/frontend/src/`
- `src/aura/workspace/web/frontend/electron/`
- `src/aura/workspace/web/frontend/e2e/`
- frontend package/build/test configuration under `src/aura/workspace/web/frontend/` (except `generators/`)
- `src/aura/workspace/web/app.js`, `styles.css`, and `index.html`
- `src/aura/legacy/ui/`

### Integration-owned shared code

Everything not listed above is integration-owned, especially:

- `src/aura/engineering_graph/` and its models/interfaces
- `src/aura/planner/` schemas and orchestration
- workspace assembly, bridge, events, modifications, server, and view models
- application entry points, configuration, dependency manifests, migrations, and infrastructure
- cross-module tests and shared documentation

If a feature needs an integration-owned change, describe it in the handoff. Do not hide it among module changes.

