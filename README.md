# AURA

AURA is an AI-assisted engineering workspace that turns a product request into
a connected, versioned system model. It combines an engineering graph,
deterministic verification, generated schematic and 3D representations, and an
AI proposal workflow in one desktop interface.

```text
Request -> AI proposal -> Verification -> Engineering Graph -> 3D / Schematic
```

Edits are proposed before they are committed. AURA identifies affected
components and relationships, previews the impact, runs verification, and then
updates the authoritative graph only after acceptance. The interface does not
present arbitrary component substitutions as valid engineering changes, and it
does not expose provider or model branding in user-facing output.

## Fast start on Windows

Prerequisites:

- Python 3.11 recommended (3.9 and newer are supported)
- Current Node.js LTS with npm
- Optional: Google Cloud Application Default Credentials for live AI planning

From the repository root, run:

```powershell
.\scripts\start.bat
```

The launcher creates `.venv` when needed, installs missing backend and frontend
dependencies, starts the FastAPI backend, waits for its health check, and opens
the Electron desktop app. Existing healthy services and installed dependencies
are reused, so later starts are fast.

Useful alternatives:

```powershell
# Open the browser UI instead of Electron
.\scripts\start.ps1 -Frontend browser

# Start only the backend
.\scripts\start.ps1 -Frontend none

# Reinstall dependencies and rebuild the frontend
.\scripts\start.ps1 -Install -Build

# Use a different local port
.\scripts\start.ps1 -Port 9000
```

The default application URL is <http://127.0.0.1:8765/> and liveness is
reported at <http://127.0.0.1:8765/health/live>.

## Live AI configuration

The launcher copies `.env.example` to `.env` only when `.env` does not exist.
For the configured cloud planner, authenticate once and set the project value:

```powershell
gcloud auth application-default login
```

```env
AURA_LLM_PROVIDER=vertex
AURA_GCP_PROJECT=your-gcp-project-id
AURA_GCP_LOCATION=global
AURA_DETERMINISTIC_FALLBACK=true
```

`.env` is ignored by Git. Without usable cloud credentials, the workspace can
still run with its bounded deterministic fallback; live free-form engineering
edits require the configured AI provider.

For Nemotron on Nebius set `AURA_LLM_PROVIDER=nebius` with `NEBIUS_API_KEY`
(and optionally `NEBIUS_BASE_URL`, `NEBIUS_MODEL`). In the app, the model badge
menu → **Model settings** adds profiles for Nebius, any OpenAI-compatible
endpoint, or a local Ollama endpoint. A profile needs a kind, endpoint and model
id; keys are stored in Windows Credential Manager (`keyring`, service
`aura-model`) and are never returned by the API. **Test** reports the real
provider error. The active profile changes only when you choose it; a failing
profile is reported, never silently replaced.

## Firmware toolchain (optional)

The fan workflow generates an ESP32 sketch and can compile it with
`arduino-cli`. Without it, compile reports `toolchain_missing`; nothing is
treated as a pass. To enable real compiles:

```powershell
winget install ArduinoSA.CLI
$url = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"
arduino-cli core update-index --additional-urls $url
arduino-cli core install esp32:esp32 --additional-urls $url
arduino-cli lib install OneWire DallasTemperature
```

Set `AURA_ARDUINO_CLI` to the executable path if it is not on `PATH`.

In the Code space only the `fanControl` function is editable; pins, thresholds
and board setup stay generated from the design. Pin changes are made from the
inspector's GPIO picker and become a normal revision (verified, undoable), and
the firmware follows them.

## Product capabilities

- **Design with AURA**: a requirements conversation (function, budget, power,
  connectivity, size, environment, experience) that proposes parts, compatible
  alternatives, a dated-price cost estimate and limitations for approval before
  a project is created. `scripts/idea_live_check.py` drives one live run.
- Versioned projects, revisions, undo, replayable events, and persistence.
- Typed assemblies, subsystems, components, interfaces, and relationships.
- AI-generated creation and edit proposals validated against strict schemas.
- Deterministic electrical, physical, safety, reference, and graph checks.
- Generic representation compilation for multi-part mechanical assemblies.
- Interactive Three.js assembly views and tscircuit schematic rendering.
- Selection-linked 3D, schematic, engineering graph, verification, and work UI.
- Desktop Electron shell plus the same workspace in a normal browser.

Project data is stored under `%LOCALAPPDATA%\AURA` by default. Override it with
`AURA_DATA_DIR`, `AURA_WORKSPACE_DB_PATH`, or
`AURA_WORKSPACE_ARTIFACT_DIR`. Use `AURA_WORKSPACE_STORAGE_MODE=memory` only
for disposable tests.

## Development

Install all test dependencies after the fast-start environment exists:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[server,vertex,dev]"
```

Run the repository validation script:

```powershell
.\scripts\test.ps1 -Module all
```

Run the full browser and desktop checks:

```powershell
Set-Location src\aura\workspace\web\frontend
npm run test:browser
npm run test:electron
```

Frontend source is under `src/aura/workspace/web/frontend`; its production
bundle is emitted into `src/aura/workspace/web/representation` and served by
the Python application.

## Repository map

```text
src/aura/engineering_graph/   Authoritative graph, patches, and revisions
src/aura/planner/             Structured planning contracts and proposal flow
src/aura/verification/        Deterministic engineering checks
src/aura/workspace/           API, persistence, assembly, and representations
src/aura/workspace/web/       Browser assets and frontend source
src/aura/infrastructure/      Provider, persistence, and host adapters
src/aura/legacy/              Optional compatibility systems
tests/                        Python unit and integration tests
docs/                         Architecture, operations, security, and decisions
scripts/                      Startup, test, integration, and deployment tools
infra/                        Cloud infrastructure definitions
```

Generated workspaces, build packages, test reports, caches, local models,
runtime data, and secrets are intentionally excluded from Git.

After validation or packaging, remove only reproducible local output with:

```powershell
.\scripts\cleanup.ps1
```

The cleanup script preserves `.env`, `.venv`, `node_modules`, Terraform state,
and deployment caches.

## Documentation

- [Active work and detailed remaining tasks](docs/active/README.md)
- [Documentation index](docs/README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Validation and failure behavior](docs/VALIDATION.md)
- [Cloud deployment](docs/CLOUD_DEPLOYMENT.md)
- [Security](docs/SECURITY.md)
- [Legacy compatibility systems](docs/LEGACY.md)
- [Third-party notices](docs/THIRD_PARTY_NOTICES.md)

## License

AURA is licensed under the MIT License. Optional XTTS use is also subject to
Coqui's model license.
