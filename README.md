# AURA

AURA is migrating into a local AI Engineering Workspace. A structured project
request is proposed by one Planner, checked by deterministic Verification,
committed to a versioned Engineering Graph, and presented through
frontend-neutral Workspace events.

```text
Project request -> Planner -> Verification -> Engineering Graph -> Workspace
```

The existing Windows assistant remains available during migration. Its proven
Ollama, Faster-Whisper, XTTS, memory, safe tools, desktop integration, project
templates, and QML UI are being retained as infrastructure or compatibility
features. Unreal, TITAN, and the old specialist hierarchy are legacy opt-in
experiments and are not part of normal startup.

## Implemented engineering core

- Stable project, assembly, subsystem, component, connection, requirement,
  constraint, assumption, decision, artifact, evidence, verification-result,
  and representation entities.
- Hierarchy and typed relationships with deterministic lookup.
- JSON serialization and safe project-graph persistence.
- Validated graph patches and revision history.
- Explicit structured Planner request and proposal schemas.
- Categorical Verification states controlled independently of Planner output.
- GUI-independent Workspace events and subscriptions.
- A deterministic request-to-revision-to-event flow requiring no LLM, GUI,
  voice, desktop, internet, or Unreal installation.

The browser Workspace includes production mechanical representations through
cascade-core/Three.js and generated Circuit JSON rendered by tscircuit's
schematic viewer.

## Installation

Python 3.10 or newer is supported.

Install the lightweight engineering core and Ollama HTTP support:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Install the current Windows UI and voice assistant dependencies:

```powershell
pip install -e ".[voice,desktop]"
```

XTTS is optional. Install the correct CUDA-enabled PyTorch build for the host,
then run:

```powershell
pip install -e ".[voice,xtts]"
```

`requirements.txt` and `requirements-xtts.txt` remain available for the
existing reproducible assistant setup during migration.

## Running

The compatibility assistant optionally uses Ollama. To run it, install a supported local model:

```powershell
ollama pull qwen3:8b
ollama serve
```

Launch through the package entry point:

```powershell
aura
```

For the compatibility assistant:

```powershell
$env:PYTHONPATH = "src"
aura-assistant
```

The compatibility assistant supports text/voice conversation, safe tools,
project templates, memory, and result reveal.

Run the primary browser engineering workspace server:

```powershell
$env:PYTHONPATH = "src"
pip install -e ".[server,vertex]"
gcloud auth application-default login
python -m aura.workspace.server --open
```

The reusable frontend consumes project, graph, revision, modification, and
WebSocket event APIs. Component cards use stable graph IDs for hover, click
selection, information display, verification warnings, representation states,
and AURA focus highlighting. The existing QML interface remains a legacy
assistant fallback and is not imported by the workspace server.

Projects and artifacts persist by default in the platform user-data directory
(`%LOCALAPPDATA%\AURA` on Windows). `AURA_DATA_DIR`,
`AURA_WORKSPACE_DB_PATH`, and `AURA_WORKSPACE_ARTIFACT_DIR` override it. Set
`AURA_WORKSPACE_STORAGE_MODE=memory` only for disposable development or tests.

The production frontend package is under `src/aura/workspace/web/frontend`:

```powershell
cd src/aura/workspace/web/frontend
npm ci
npm run build
```

## Testing

Install development dependencies:

```powershell
pip install -e ".[dev]"
```

Default fast and mocked-local suite:

```powershell
pytest -q
```

Exclude all explicitly live tests:

```powershell
pytest -q -m "not live"
```

Live host validation is opt-in and environment-specific:

```powershell
pytest -m live
python tests/live_xtts_activation.py
python tests/live_desktop_integration.py
python tests/live_titan_validation.py --live --editor "C:\path\to\UnrealEditor-Cmd.exe"
```

Standalone historical `tests/t*.py` files are not all collected by pytest yet.
Their old reports are historical evidence, not proof of the current checkout.

## Configuration

Settings use package defaults and optional values from `.env`. Copy
`.env.example` when local customization is needed. Important options include:

```env
AURA_LLM_PROVIDER=vertex
AURA_GCP_PROJECT=your-gcp-project-id
AURA_GCP_LOCATION=global
AURA_VERTEX_MODEL=gemini-3.1-flash-lite
AURA_VERTEX_TIMEOUT_SECONDS=20
AURA_DETERMINISTIC_FALLBACK=true
AURA_HARDWARE_PROFILE=auto
AURA_STT_MODEL=small
AURA_TTS_BACKEND=auto
AUTO_REVEAL_RESULTS=true
```

Secrets, models, voice references, logs, generated workspaces, and runtime
memory are excluded from Git.

## Architecture and status

- [Current architecture](docs/ARCHITECTURE.md)
- [Legacy systems](docs/LEGACY.md)
- [Validation status](docs/VALIDATION.md)
- [Development](docs/DEVELOPMENT.md)
- [Representation stack decision](docs/decisions/representation-stack.md)
- [Vertex Planner decision](docs/decisions/vertex-planner.md)
- [Third-party notices](docs/THIRD_PARTY_NOTICES.md)

Known migration limitations include the still-large compatibility supervisor,
fragmented historical test scripts, host-dependent voice/desktop behavior, and
legacy modules that remain at their original import paths for compatibility.

## License

AURA is licensed under the MIT License. XTTS usage is also subject to Coqui's
model license.
