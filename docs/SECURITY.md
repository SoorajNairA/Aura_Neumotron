# Production representation dependency audit

Audit command: `npm audit --json` in `src/aura/workspace/web/frontend` on 2026-08-07.

Direct compatible fixes were applied: Vite `7.1.7 → 7.3.6` removed six development-server advisories, and Vitest `3.2.4 → 3.2.7` removed the critical UI-server advisory. Build and browser tests passed after both upgrades. No forced audit fix was used.

| Finding | Severity | Dependency path and reachability | Patch/disposition |
|---|---:|---|---|
| React Router open redirect, constructor injection, and XSS (`GHSA-wrjc-x8rr-h8h6`, `GHSA-337j-9hxr-rhxg`, `GHSA-jjmj-jmhj-qwj2`) | Moderate | `@tscircuit/schematic-viewer → tscircuit → graphics-debug → react-router-dom/react-router`. Transitive runtime packages, but the production renderer does not expose routing, SSR hydration, or user-controlled navigation. | Compatible transitive fix exists but cannot be forced without changing the pinned tscircuit graph. Keep viewer inputs to server-generated Circuit JSON; upgrade when tscircuit publishes a compatible graph. |
| sharp/libvips inherited CVEs (`GHSA-f88m-g3jw-g9cj`) | High | `@tscircuit/core → create-fdm-enclosure → graphics-debug → looks-same → sharp`. Node generator dependency; excluded from browser chunks. | Available only through an incompatible core downgrade according to npm. Generator accepts bounded structured JSON, no files/URLs/code, and runs as a fixed subprocess. |
| `@tscircuit/core`, `create-fdm-enclosure`, `fanout-solver`, `graphics-debug`, `looks-same`, `bun-match-svg`, and `tscircuit` aggregate findings | High | Build/generator-side tscircuit graph, primarily image/debug/FDM paths unused by circuit generation. `tscircuit` is also an automatically installed peer of schematic-viewer, but inspection of built browser chunks found no `@tscircuit/core`, `react-reconciler`, `sharp`, `looks-same`, or `graphics-debug` code. | npm suggests incompatible core `0.0.1475` or unconstrained transitive changes. Retain pinned versions, isolate core in Node, reject executable input, and revisit on a compatible tscircuit release. |

Final audit: **10 unresolved findings: 2 moderate, 8 high, 0 critical**. The audit is not clean.
