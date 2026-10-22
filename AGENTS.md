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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Aura** (10417 symbols, 27203 relationships, 523 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/Aura/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Aura/clusters` | All functional areas |
| `gitnexus://repo/Aura/processes` | All execution flows |
| `gitnexus://repo/Aura/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
