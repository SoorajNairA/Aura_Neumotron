# Representation stack decision

## Selected packages

- CAD: `cascade-core@2.0.6`; OpenCascade.js lockfile revision `03c26253880a1a561a03bfd1588475a56bc8eef0`.
- Rendering: `three@0.185.1`.
- Circuit generation: `@tscircuit/core@0.0.1609` and `circuit-json@0.0.464`.
- Circuit rendering: `@tscircuit/schematic-viewer@2.0.76`, React/ReactDOM `18.3.1`.
- Tooling: Vite `7.3.6`, TypeScript `5.9.3`, Vitest `3.2.7`, Playwright `1.62.1`.
- Repositories inspected at: CascadeStudio `4fabeebd16a39c8f08aa630ccb8f3ed471f95a78`, Replicad `c7bdff60153100138672d52d5d249d757ff5ddc6`, schematic-viewer `fedb2f944c8b183c05fa1f3cdc442e0d3e2fea10`, step.parts `c6113328a5695b976a010a203a90fe86191769bf`.

## Licence summary

CascadeStudio/cascade-core, Three.js, Replicad, React, Vite, Vitest, and the tscircuit repositories are MIT. Circuit JSON is ISC. Playwright is Apache-2.0. OpenCascade.js embeds OCCT under LGPL-2.1 with the OCCT exception. No catalogue geometry is committed: step.parts is MIT only for original repository material and does not relicense third-party models.

## Successfully proven

`cascade-core` generated a four-section curved loft, a B-spline pipe sweep, and a filleted enclosure in a Web Worker. Each result remained a separate shaded Three.js mesh with normals, bounding box, transform, and stable semantic metadata. Raycast hover/click, camera orbit/reset, isolate/show-all, and explode/assemble preserve identity. A deterministic tscircuit build step generates 154 irrigation Circuit JSON elements for controller, soil sensor, MOSFET, flyback diode, pump load, and battery with explicit power/ground wiring. Viewer symbol selection and Three.js selection cross-highlight through an explicit reference-to-semantic-ID table. Timeouts, two CAD evaluation attempts, diagnostics, and visible failed/proxy states prevent permanent loading.

## Failed or rejected

- Browser-loaded `@tscircuit/core` failed because its React 19 reconciler is incompatible with the React 18 runtime required to avoid duplicate-hook failures in the current schematic viewer tree. Core therefore runs only during deterministic build generation; it is not shipped in the browser bundle.
- Vite must prebundle the schematic viewer; direct ESM loading exposes an incompatible CommonJS `xml-reader` named export.
- step.parts returned `bearing_608zz`, but its record supplied no individual model licence, attribution, original units, or orientation. Loading/redistribution was rejected and the UI reports a proxy. Replicad `0.23.1` was inspected but not activated because cascade-core succeeded.

## Measured observations

- Production application bundle: 1,465.29 kB JavaScript (358.00 kB gzip), 2.67 kB CSS (1.08 kB gzip).
- OpenCascade payload: 21,241,345-byte WASM plus 375,242-byte worker.
- OpenCascade initialization: approximately 693 ms.
- Reservoir loft: 728 ms, 1,832 triangles, 70.4 × 70.0 × 92.0 mm.
- Tube sweep: 368 ms, 932 triangles, 75.0 × 41.6 × 76.3 mm.
- Filleted enclosure: 285 ms, 228 triangles, 58.0 × 42.0 × 20.0 mm.
- tscircuit generation: 608.1 ms for 154 elements; catalogue load: not attempted because licence validation failed.
- CAD generation remained responsive because all kernel work ran in the cascade-core worker. No multi-minute initialization, frozen UI, or worker-loading failure occurred in the success path.

## Selected CAD option and reason

Select `cascade-core`. The primary candidate passed browser build, curved loft/sweep/fillet generation, worker execution, separate-part identity, normals, and direct Three.js mesh conversion using its supported npm API. Replicad would add a second OpenCascade wrapper without addressing a demonstrated failure.

## Known integration risks

The 21.2 MB kernel payload needs caching and a lazy-loading boundary. `cascade-core` also bundles unused OpenSCAD-parser paths that Vite warns contain Node `fs/path` imports. The tscircuit dependency graph currently requires build-time/runtime React separation, emits a viewer ref warning, and reports 10 production audit findings (2 moderate, 8 high) in transitive packages; it must be upgraded or narrowed before production use. Catalogue metadata cannot be trusted for redistribution until per-model licence, attribution, units, and orientation are machine-readable.

## Production disposition

Goal 2 implemented the selected stack under `src/aura/workspace/web/frontend`.
The Engineering Graph stores no Three.js, React, tscircuit, or OpenCascade
runtime objects. The superseded executable experiment was retired after its
important behaviors were covered by production tests.
