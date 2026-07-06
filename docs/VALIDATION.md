# Validation Status

## Current automated proof

The default `pytest -q` suite is designed not to require Ollama, CUDA, a
microphone, GUI display, Unreal Engine, desktop application launching, or the
internet. It includes deterministic core tests and mocked/local integrations.

The engineering-core tests currently prove:

- structured request validation;
- deterministic Planner output;
- independent Verification decisions and states;
- accepted patch commit and revision creation;
- graph serialization and persistence round trips;
- frontend-neutral Workspace events;
- lightweight import boundaries;
- normal supervisor construction without importing Unreal.

Run `python -m compileall -q src tests` as the package compilation check.

## Test categories

Pytest markers are registered for `unit`, `integration`, `live`, `voice`,
`desktop`, `llm`, `legacy`, `unreal`, and `slow`. Historical standalone scripts
are being converted incrementally and are not all marker-controlled yet.

## Host-specific validation

Live Ollama, XTTS, microphone, Windows desktop, and Unreal tests are opt-in.
Results depend on local models, hardware, drivers, applications, and services.
They must not be interpreted as portable automated proof.

## Historical reports

Old host-specific release, Jarvis certification, repository audit, security,
and XTTS activation reports were removed. Their fixed-machine pass counts were
not reproducible validation of the current workspace. Supported legacy systems
and the useful historical context are summarized in `LEGACY.md`.

## Unsupported claims

The present engineering core does not prove physical correctness, manufacturing
readiness, CAD validity, circuit ERC/DRC, simulation accuracy, component
availability, regulatory compliance, or production readiness.
