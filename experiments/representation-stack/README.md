# Representation stack spike

## Run

```powershell
npm ci
npm run dev
```

Open `http://localhost:5173`. Run all checks with `npm run test:all`.

## Decision

Selected stack: `cascade-core` + Three.js + tscircuit Circuit JSON + `@tscircuit/schematic-viewer`. Replicad is not retained because the primary CAD candidate passed the worker, curved-geometry, separate-part, selection, and build proofs.
