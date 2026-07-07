# Development

## Environment

Use Python 3.10 or newer. Install the browser workspace and test dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[server,dev]"
Copy-Item .env.example .env
```

The active live Planner uses `AURA_PLANNER_MODEL=qwen3:8b`. The deterministic
irrigation fallback requires no local model. `qwen2.5:3b` remains supported only
as the low-hardware fallback for the compatibility assistant.

## Run

```powershell
$env:PYTHONPATH = "src"
python -m aura.workspace.server --open
```

The QML assistant, voice stack, and Unreal domain are optional compatibility
systems. They are not imported by the workspace server.

SQLite is the normal storage mode. Configure `AURA_WORKSPACE_DB_PATH` and
`AURA_WORKSPACE_ARTIFACT_DIR` with repository-relative or deployment-managed
paths. Artifact metadata is stored in SQLite; binary content is written under
the artifact directory using generated IDs and atomic replacement.

## Validate

```powershell
pytest -q
python -m compileall -q src tests
```

Live Ollama, voice, desktop, and Unreal checks are opt-in. Never describe their
historical results as current validation.

## Generated data

`workspace/`, `memory/`, `logs/`, model caches, local voice samples, build
outputs, and Python caches are reproducible or host-specific and remain ignored.
Do not commit secrets, downloaded models, generated HTML, or runtime event data.
## Representation runtime

Install and build the isolated production browser/Node representation runtime before packaging:

```powershell
cd src/aura/workspace/representation_runtime
npm ci
npm run build
npm run test:browser
```

`@tscircuit/core` is used only by the fixed Node generator. The browser bundle consumes Circuit JSON and lazy-loads `cascade-core` only for validated mechanical representations.
