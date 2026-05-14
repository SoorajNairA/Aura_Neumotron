# AURA

AURA is a fully local AI executive assistant with offline conversation,
persistent memory, desktop automation, project generation, and natural voice
interaction.

It runs on the user's Windows computer through Ollama, Faster-Whisper, and
XTTS-v2. Conversations, files, models, and voice data remain local.

## Quick Start

### Requirements

- Windows 10 or 11
- Python 3.10 or newer
- [Ollama](https://ollama.com/) installed and running
- A working microphone for voice input
- NVIDIA CUDA GPU recommended for XTTS-v2

### 1. Install Models

Install both supported conversation models:

```powershell
ollama pull qwen3:8b
ollama pull qwen2.5:3b
```

AURA selects them automatically:

- Capable hardware: Qwen 8B with XTTS-v2
- Lower-end hardware: Qwen 3B with pyttsx3
- Manual selection: use the model menu in the AURA top bar

### 2. Install AURA

```powershell
git clone https://github.com/SoorajNairA/Aura.git
cd Aura
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

For XTTS-v2 and voice cloning:

```powershell
pip install -r requirements-xtts.txt
```

Install the CUDA-enabled PyTorch build appropriate for the machine before
installing XTTS dependencies.

### 3. Start Ollama

```powershell
ollama serve
```

Leave Ollama running in the background.

### 4. Launch AURA

For the normal Windows experience, double-click:

```text
launch_demo.bat
```

The launcher opens AURA without leaving a terminal visible. Hardware detection,
Ollama warmup, speech recognition, XTTS initialization, memory, and tool status
are shown inside the startup animation.

For development or visible console logs:

```powershell
$env:PYTHONPATH = "src"
python -m aura.main
```

## Using The Application

### Voice Mode

1. Press **TALK**.
2. Speak naturally.
3. Wait for the transcript and response.

Examples:

```text
Open Chrome
Open GitHub
Create a folder named Demo
Write Hello World into notes.txt
Build me a snake game
Who created you?
```

### Text Mode

Enter an objective in the text field at the bottom of the HUD and press Enter
or the send button. Text and voice requests use the same routing, memory, tools,
and response pipeline.

### Change Conversation Model

Use the model selector in the top bar. It lists compatible models currently
installed in Ollama.

When a model is selected, AURA verifies and warms it before switching. If the
new model cannot start, AURA keeps using the previous model.

### Created Files And Projects

AURA automatically reveals successful results:

- Files open in their default safe application.
- Folders open in Explorer.
- Generated projects open in VS Code when available.
- Websites open in the default browser.

Demo-mode projects are stored in:

```text
DemoWorkspace/
```

## Voice Cloning

Place a clean voice reference at:

```text
voices/aura_voice.wav
```

Recommended reference:

- WAV, MP3, or FLAC source
- 10 to 60 seconds
- One speaker
- Minimal noise, music, or echo

The default configuration is:

```env
AURA_TTS_BACKEND=auto
AURA_TTS_DEVICE=cuda
AURA_AUTO_WARMUP=true
AURA_VOICE_REFERENCE=voices/aura_voice.wav
```

If XTTS or CUDA is unavailable, AURA falls back to pyttsx3 and then Windows
.NET Speech.

## Configuration

Runtime settings are loaded from `.env`. Useful options include:

```env
AURA_CREATOR_NAME=Sooraj
AURA_OLLAMA_MODEL=auto
AURA_OLLAMA_PRIMARY_MODEL=qwen3:8b
AURA_OLLAMA_FALLBACK_MODEL=qwen2.5:3b
AURA_HARDWARE_PROFILE=auto
AURA_STT_MODEL=small
AURA_TTS_BACKEND=auto
AUTO_REVEAL_RESULTS=true
```

Hardware profiles:

- `auto`: detect hardware and choose the model and voice backend
- `performance`: prefer Qwen 8B and XTTS-v2
- `low`: prefer Qwen 3B and pyttsx3

Set `AURA_OLLAMA_MODEL` to an installed model name to override automatic model
selection at startup.

## Features

- Offline Qwen conversation through Ollama
- Qwen 8B and 3B hardware-aware selection
- Runtime model switching
- Faster-Whisper speech recognition
- XTTS-v2 synthesis and local voice cloning
- pyttsx3 and Windows Speech fallbacks
- Persistent conversation and project memory
- Safe tool registry for applications, URLs, files, and folders
- Executive agent for runnable project generation
- Automatic result reveal
- Destructive-action safety restrictions
- Startup diagnostics displayed inside the HUD

## Architecture

```text
Voice or text input
        |
Faster-Whisper STT
        |
Intent and tool routing
        |
Qwen via Ollama
        |
Executive Agent / Tool Registry
        |
Desktop actions and project generation
        |
Memory and verification
        |
XTTS-v2 or local speech fallback
```

## Project Structure

```text
Aura/
|-- assets/             UI assets
|-- docs/               Architecture, audits, and test reports
|-- qml/                AURA HUD interface
|-- src/aura/           Application source
|-- tests/              Unit, integration, and acceptance tests
|-- tools/              Local diagnostics
|-- voices/             Local voice references
|-- launch_demo.bat     Console-free Windows launcher
|-- launch_aura.vbs     Hidden Python launcher
|-- requirements.txt
`-- requirements-xtts.txt
```

Runtime-only directories such as `logs/`, `memory/`, `models/`, and
`DemoWorkspace/` are excluded from Git.

## Troubleshooting

### Ollama is unavailable

```powershell
ollama serve
ollama list
```

Confirm that either `qwen3:8b` or `qwen2.5:3b` is installed.

### XTTS does not activate

Check:

- CUDA-enabled PyTorch is installed.
- `AURA_TTS_DEVICE=cuda` is configured.
- The voice reference exists.
- XTTS dependencies are installed.

Review `logs/aura.log` for the fallback reason.

### AURA does not hear speech

Confirm microphone permissions in Windows and review:

```env
AURA_STT_MODEL=small
AURA_STT_DEVICE=cpu
AURA_STT_COMPUTE_TYPE=int8
```

### Startup fails silently

Run with visible logs:

```powershell
$env:PYTHONPATH = "src"
python -m aura.main
```

## Validation

- Jarvis acceptance: 39/39
- Tool routing, safety, memory, planner isolation, and visibility tests pass
- XTTS activation and fallback behavior are documented under `docs/`

## Hardware Used

The primary validated machine used:

- NVIDIA RTX 3050 Laptop GPU with 4 GB VRAM
- XTTS-v2 on CUDA
- Faster-Whisper small on CPU int8
- Qwen 8B and Qwen 3B through Ollama

## License

AURA is released under the MIT License.

XTTS-v2 usage is subject to Coqui's model license. Review that license before
downloading or redistributing XTTS model artifacts.
