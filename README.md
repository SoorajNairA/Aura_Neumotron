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

This foundation does not yet implement CAD, circuit simulation, automatic
engineering calculations, or the final interactive workspace UI.

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

Install and start Ollama, then install at least one supported local model:

```powershell
ollama pull qwen3:8b
ollama pull qwen2.5:3b
ollama serve
```

Launch through the package entry point:

```powershell
aura
```

For source-tree development:

```powershell
$env:PYTHONPATH = "src"
python -m aura.main
```

On Windows, `launch_aura.vbs` continues to provide the hidden-console launch.
The current assistant supports text/voice conversation, safe file and folder
creation, known application and URL opening, project templates, memory, and
result reveal.

Build the interactive irrigation vertical-slice prototype without Ollama or a
GUI framework:

```powershell
$env:PYTHONPATH = "src"
python -m aura.workspace.prototype --open
```

This writes `workspace/irrigation-workspace.html` and opens it in the default
browser. Component cards use stable graph IDs for hover, click selection,
information display, verification warnings, and AURA focus highlighting.

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

Settings are loaded from `.env` with `.env.example` as a fallback. Important
options include:

```env
AURA_OLLAMA_MODEL=auto
AURA_OLLAMA_PRIMARY_MODEL=qwen3:8b
AURA_OLLAMA_FALLBACK_MODEL=qwen2.5:3b
AURA_HARDWARE_PROFILE=auto
AURA_STT_MODEL=small
AURA_TTS_BACKEND=auto
AUTO_REVEAL_RESULTS=true
```

Secrets, models, voice references, logs, generated workspaces, and runtime
memory are excluded from Git.

## Architecture and status

- [Current architecture](docs/architecture.md)
- [Legacy systems](docs/LEGACY.md)
- [Validation status](docs/VALIDATION.md)

Known migration limitations include the still-large compatibility supervisor,
fragmented historical test scripts, host-dependent voice/desktop behavior, and
legacy modules that remain at their original import paths for compatibility.

## License

AURA is licensed under the MIT License. XTTS usage is also subject to Coqui's
model license.
