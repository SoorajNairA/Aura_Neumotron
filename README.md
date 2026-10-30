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

Any ESP32 DevKit design gets a generated sketch (the fan workflow keeps its own), and AURA can compile it with
`arduino-cli`. Without it, compile reports `toolchain_missing`; nothing is
treated as a pass. To enable real compiles:

```powershell
winget install ArduinoSA.CLI
$url = "https://espressif.github.io/arduino-esp32/package_esp32_index.json"
arduino-cli core update-index --additional-urls $url
arduino-cli core install esp32:esp32 --additional-urls $url
arduino-cli lib install OneWire@2.3.8 DallasTemperature@4.0.5 ESP32Servo@3.2.1
```

Set `AURA_ARDUINO_CLI` to the executable path if it is not on `PATH`.

In the Code space only the `fanControl` function is editable; pins, thresholds
and board setup stay generated from the design. Pin changes are made from the
inspector's GPIO picker and become a normal revision (verified, undoable), and
the firmware follows them.

## Hardware: upload and live board (optional)

The Build space (or **Connect device**) lists USB ports through `arduino-cli
board list`; common ESP32 DevKit USB-serial chips are tagged "likely ESP32
(unverified)". Upload asks for confirmation and needs a passing compile of the
current revision. If the ESP32 says "Failed to connect", hold BOOT while it
uploads. The serial monitor (115200 baud) shows the board's output; the
Simulation space can then switch to **Live board**, where the 3D follows the
reported values and AURA flags an output that disagrees with the approved rule
for three lines in a row.

"Observed on hardware" appears only after three telemetry lines carrying the
current revision arrive from a real port. Set `AURA_FAKE_BOARD=1` to add a test
port `FAKE0`; its runs are labelled "Fake board (test)" and never count as
hardware evidence.

## Product capabilities

- **Design with AURA**: a requirements conversation (function, budget, power,
  connectivity, size, environment, experience) that proposes parts, compatible
  alternatives, a dated-price cost estimate and limitations for approval before
  a project is created. `scripts/idea_live_check.py` drives one live run.
- **Firmware for new projects**: Nemotron fills a short rule list (input,
  threshold, output) for the parts in the design; AURA validates it and writes
  the C++ from fixed drivers (DS18B20, soil, light, PIR, button, relay/MOSFET,
  LED, SG90). The proposal card shows the rules in plain words; without the
  live model a labelled default rule is used. Analog sensors get ADC1 pins.
- **Simulation with faults**: the same rule list drives sliders/toggles per
  input and shows each output; inject sensor disconnected/stuck, actuator
  stalled, driver shorted. Behavioral only, not hardware.
- **Exact pins and breadboard**: wire rows show ESP32-DevKitC header pins
  (e.g. `GPIO4 (IO4, J3 pin 13)`), both wire ends and polarity; selecting a
  part highlights what it is wired to. Prototypes get an 830-point breadboard
  (nominal standard size) that can be left out. Common modules have detailed
  3D models; others are labelled "Generic proxy".
- **Readable 3D**: boards carry printed names and pin labels (ESP32-DevKitC
  `IO4`, `3V3`, `GND`…; module `VCC/DAT/GND`, terminals `V+/OUT+`), and every
  cable runs from a real pin to a real pin, colour-coded (red +, black GND,
  yellow signal, orange control, blue switched load) and numbered like the
  part card. Hover a cable for both ends; parts without a model get a dashed
  "approximate route". Cables run as a tidy harness: straight up, flat on
  their own lane, straight down. Routing is illustrative, not a measured cable
  layout.
- **Layout**: ☰ then File/Edit/Project/Help menu; Design, Code,
  Simulation and Build in the toolbar above the viewport; the round button in
  the viewport corner opens Fit, Explode, Solid and Show all.
- **Component library** (☰ in Design): search the catalogue, add several parts
  as one verified proposal (safe GPIOs, undoable), edit part settings, mount
  parts, and try DS18B20/fan behavioral test benches (not hardware).
- **IoT catalogue with pins**: 66 curated parts in eight categories (boards,
  sensors, actuators, displays, communication, power, breadboards, basic),
  each with a manufacturer source, printed pin labels, pin roles and
  datasheet-range settings (`GET /api/catalogue?category=displays`). New:
  SSD1306 OLED, LCD1602 I²C, MAX7219 matrix, WS2812B stick, RFM95W LoRa,
  nRF24L01+, NEO-6M GPS, MFRC522 RFID, AMS1117-3.3, TP4056, potentiometer,
  active buzzer, 400-point breadboard. Only the ESP32-DevKitC is a full
  controller; other boards are listed only.
- **Auto-wiring on add**: an added part is wired to the ESP32 by fixed rules,
  with no model call: VCC to 3V3 or 5V by its supply range, GND, analog to
  ADC1, I²C on GPIO21/22, SPI on GPIO18/23/19 with its own CS pin, UART on two
  free pins (one UART part per project). A part the board cannot power (for
  example 12 V) is added with its supply unwired and a warning.
- **Pin-to-pin wire edits (API)**: `POST /api/projects/{id}/wire-proposals`
  connects, reconnects or disconnects a wire as a verified, undoable revision.
- **Electrical rule checks**: these flag two outputs on one net, a supply
  outside a part's range, ground mixed with signals, a 5 V logic signal into
  an ESP32 pin, duplicate I²C addresses, an unwired required pin, and a 3V3
  budget above 500 mA (warning). They are rule checks, not simulation.
- **Not yet done**: library category tabs, Replace/Delete/Rename and settings
  forms in the inspector, wire editing in the Wiring view, and broken-rule
  handling after a delete. The backend for wire edits exists, but the UI does
  not use it yet. The HC-05 and an 18650 holder were left out because no
  manufacturer source could be confirmed.
- **Menu bar, File menu and wiring editing**: ☰ (component library plus
  view/tool actions) sits before File, Edit, Project and Help; the 3D
  view/Wiring/Split switch is at the viewport's top-left; updates show as
  dismissible toasts; sidebars run full height. File offers New, Open (Ctrl+O,
  searchable), Save (Ctrl+S: the layout, plus a pending Code-space
  control-rule edit), Make a copy, Export ▸ Project ZIP, Import ▸
  Project ZIP and Save local copy. The ZIP holds manifest, graph, project,
  firmware, layout and design artifacts, never keys or env; unsaved wiring
  edits are guarded on project switch. In the Wiring view: Select/Pan, drag
  parts, drag wire bends (connections never change), rename via the
  inspector's Display name, Ctrl+Z/Ctrl+Shift+Z; with the view focused, W /
  Shift+W selects the next / previous wire and Enter moves to its bend
  handles (arrow keys bend); the layout autosaves and
  survives reopen and regeneration. Limits: no endpoint reconnection, no
  firmware pin sync from the wiring view, no shareable links (no hosted server
  with access control), bends per segment only, layout changes the schematic
  not 3D placement, and renames show in 3D only in the hover label.
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
