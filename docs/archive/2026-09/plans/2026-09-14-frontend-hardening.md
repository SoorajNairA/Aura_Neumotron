# Frontend and Desktop Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a resilient, responsive, accessible, themeable, performant browser and Electron workspace with trustworthy tests and dependencies.

**Architecture:** Extract focused state and dialog primitives from the incumbent app without changing its product structure. Keep required hydration atomic and optional hydration independent, use CSS-driven responsive drawers, and make renderer work event/visibility driven.

**Tech Stack:** React 18, TypeScript, Vite, Vitest, Playwright, Three.js, Electron.

**Spec:** `docs/archive/2026-09/specs/2026-09-14-release-hardening-design.md`

## Global Constraints

- Support 360px through desktop widths and 200% zoom.
- Meet WCAG AA text contrast and a 44px compact action-target standard.
- Preserve existing backend payload contracts and product-specific visual identity.

---

### Task 1: Resilient hydration

**Files:**
- Create: `src/aura/workspace/web/frontend/src/workspaceHydration.ts`
- Create: `src/aura/workspace/web/frontend/src/workspaceHydration.test.ts`
- Modify: `src/aura/workspace/web/frontend/src/WorkspaceApp.tsx`
- Modify: `src/aura/workspace/web/frontend/e2e/audit.spec.ts`

**Interfaces:**
- Produces: `loadWorkspace(projectId, signal)` returning required data plus settled optional resources and localized errors.

- [ ] Add unit cases where narration, verification, assembly, schematic, and CAD fail independently while project/graph remain available; add a browser case asserting the launcher is not shown after an optional failure.
- [ ] Run the new unit/browser cases and confirm the current `Promise.all` behavior fails.
- [ ] Move hydration into the typed loader, use `Promise.allSettled` for optional resources, and expose retryable per-panel errors without clearing storage/session.
- [ ] Re-run the focused unit and Playwright cases.

### Task 2: Responsive and accessible shell

**Files:**
- Create: `src/aura/workspace/web/frontend/src/AccessibleDialog.tsx`
- Create: `src/aura/workspace/web/frontend/src/AccessibleDialog.test.tsx`
- Modify: `src/aura/workspace/web/frontend/src/WorkspaceApp.tsx`
- Modify: `src/aura/workspace/web/frontend/src/styles.css`
- Modify: `src/aura/workspace/web/frontend/e2e/production.spec.ts`

**Interfaces:**
- Produces: a reusable dialog with labelled semantics, initial focus, focus trap, Escape dismissal, and focus restoration.

- [ ] Add keyboard dialog tests and Playwright viewport cases at 360, 768, 1024, 1366, and 1920 pixels plus a 200% zoom-equivalent compact viewport.
- [ ] Confirm failures from clipped content, undersized controls, and escaping dialog focus.
- [ ] Remove the fixed body minimum, add compact navigation/inspector drawers, allow main scrolling, raise type/control sizes, correct low-contrast tokens, and replace modal markup with `AccessibleDialog`.
- [ ] Re-run keyboard and viewport cases and verify there is no horizontal document overflow.

### Task 3: Theme and reduced motion

**Files:**
- Create: `src/aura/workspace/web/frontend/src/theme.ts`
- Create: `src/aura/workspace/web/frontend/src/theme.test.ts`
- Modify: `src/aura/workspace/web/frontend/src/styles.css`
- Modify: `src/aura/workspace/web/frontend/src/WorkspaceApp.tsx`

**Interfaces:**
- Produces: `ThemeMode = "system" | "dark" | "light"` persisted in local storage and applied through `data-theme`.

- [ ] Add tests for system resolution and persistence, plus a browser assertion that both themes keep readable surfaces.
- [ ] Confirm no theme control exists before implementation.
- [ ] Tokenize active colors/sizes, add the theme control, and replace the global `0.01ms` rule with targeted reduced-motion behavior that preserves progress state.
- [ ] Re-run focused tests and both-theme browser screenshots/contrast checks.

### Task 4: Rendering and bundle performance

**Files:**
- Modify: `src/aura/workspace/web/frontend/src/WorkspaceApp.tsx`
- Modify: `src/aura/workspace/web/frontend/vite.config.ts`
- Modify: `src/aura/workspace/web/frontend/e2e/audit.spec.ts`

**Interfaces:**
- Produces: rendering that pauses while hidden/idle and schematic panning that does not set React state per pointer event.

- [ ] Add instrumentation tests for visibility/idle rendering and a browser drag test that verifies the schematic remains responsive.
- [ ] Confirm the existing perpetual render loop and pointer-move state updates violate the assertions.
- [ ] Render on controls/resize/model changes, pause when hidden, update schematic transform through a ref, and split heavy representation dependencies into lazy chunks; restore a useful bundle warning threshold.
- [ ] Run the production build and record compressed/uncompressed chunk sizes.

### Task 5: Trustworthy desktop smoke and implementation cleanup

**Files:**
- Modify: `src/aura/workspace/web/frontend/electron/main.cjs`
- Modify: `src/aura/workspace/web/frontend/package.json`
- Delete: `src/aura/workspace/web/frontend/src/WorkView.tsx`
- Delete: `src/aura/workspace/web/frontend/src/net.css`
- Delete: `src/aura/workspace/web/frontend/src/compatibility.css`
- Delete: `src/aura/workspace/web/app.js`
- Delete: `src/aura/workspace/web/index.html`
- Delete: `src/aura/workspace/web/styles.css`
- Test: `src/aura/workspace/web/frontend/e2e/runtime-rehearsal.spec.ts`

**Interfaces:**
- Produces: `--smoke` exit success only after the online application loads; `--smoke-recovery` remains the explicit offline-shell test.

- [ ] Run the current offline smoke and capture that it incorrectly exits zero.
- [ ] Require the online URL for normal smoke, add an explicit timeout/nonzero exit for offline load, and keep recovery behavior separate.
- [ ] Remove confirmed unreferenced implementations and legacy static files after the integration route no longer serves them.
- [ ] Run online and offline Electron smoke cases and confirm their exit codes differ correctly.

### Task 6: Dependency remediation and frontend release gate

**Files:**
- Modify: `src/aura/workspace/web/frontend/package.json`
- Modify: `src/aura/workspace/web/frontend/package-lock.json`
- Modify: `docs/SECURITY.md` on `hackathon-integration`

- [ ] Record `npm audit --omit=dev --json`, trace every production advisory to a direct dependency, and upgrade compatible direct dependencies.
- [ ] Run `npm ci`, `npm audit --omit=dev`, `npm test`, `npx tsc --noEmit`, `npm run build`, `npm run test:browser`, and the Electron smoke tests.
- [ ] Document only advisories that remain after reachability and upstream-fix verification; do not describe a vulnerable graph as clean.
- [ ] Run `git diff --check`, inspect the complete UI diff, commit `feature/ui`, merge it into `hackathon-integration`, and repeat the frontend release gate on the merged tree.

