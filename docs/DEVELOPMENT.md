# Development

## Environment

Use Python 3.10 or newer. Install the browser workspace and test dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[server,vertex,dev]"
Copy-Item .env.example .env
```

The active live Planner uses Vertex AI with Application Default Credentials and
`gemini-3.1-flash-lite`. Run `gcloud auth application-default login`; configure
`AURA_GCP_PROJECT` when ADC does not provide a project. The deterministic Planner
requires no model. Ollama remains isolated to the compatibility assistant.

## Run

```powershell
$env:PYTHONPATH = "src"
python -m aura.workspace.server --open
```

The QML assistant, voice stack, and Unreal domain are optional compatibility
systems. They are not imported by the workspace server.

SQLite is the normal storage mode. Its default is the platform user-data
directory (`%LOCALAPPDATA%\AURA` on Windows and the XDG data directory on
Linux). Configure `AURA_DATA_DIR`, `AURA_WORKSPACE_DB_PATH`, or
`AURA_WORKSPACE_ARTIFACT_DIR` for deployment-managed paths.

## Validate

```powershell
pytest -q
python -m compileall -q src tests
```

Live Vertex, Ollama compatibility, voice, desktop, and Unreal checks are opt-in. Never describe their
historical results as current validation.

## Generated data

`workspace/`, `memory/`, `logs/`, model caches, local voice samples, build
outputs, and Python caches are reproducible or host-specific and remain ignored.
Do not commit secrets, downloaded models, generated HTML, or runtime event data.
## Representation runtime

Install and build the isolated production browser/Node representation runtime before packaging:

```powershell
cd src/aura/workspace/web/frontend
npm ci
npm run build
npm run test:browser
```

`@tscircuit/core` is used only by the fixed Node generator. The browser bundle consumes Circuit JSON and lazy-loads `cascade-core` only for validated mechanical representations.
