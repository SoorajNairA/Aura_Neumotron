# GitHub Release Audit

Date: June 14, 2026

## Summary

AURA is ready to be published only after replacing the existing pre-release Git
history. The current `HEAD` tracks local models, logs, memory, workspace output,
pycache files, and `.env`. Those files are now ignored for the release, but the
old commit must not be pushed.

## Large Files Over 50 MB

| Size | Path | Recommendation | LFS or Ignore |
|---:|---|---|---|
| 1781.4 MB | `models/xtts/tts/tts_models--multilingual--multi-dataset--xtts_v2/model.pth` | Local XTTS model cache. Do not publish. Download at runtime. | Ignore via `models/` |
| 1781.4 MB | `.git/objects/...` | Existing bad Git blob from pre-release commit. Must be removed by clean initial history. | Rewrite/fresh history |
| 1781.4 MB | `.git/lfs/objects/...` | Local LFS cache from pre-release state. Do not publish. | Clean local LFS cache after fresh commit |
| 2218.1 MB | `.venv/Lib/site-packages/torch/lib/dnnl.lib` | Virtual environment dependency. | Ignore via `.venv/` |
| 981.2 MB | `.venv/Lib/site-packages/torch/lib/torch_cuda.dll` | Virtual environment dependency. | Ignore via `.venv/` |
| 643.4 MB | `.venv/Lib/site-packages/torch/lib/cublasLt64_12.dll` | Virtual environment dependency. | Ignore via `.venv/` |
| 490.1 MB | `.venv/Lib/site-packages/torch/lib/cudnn_engines_precompiled64_9.dll` | Virtual environment dependency. | Ignore via `.venv/` |
| 362.0 MB | `.venv/Lib/site-packages/torch/lib/cusparse64_12.dll` | Virtual environment dependency. | Ignore via `.venv/` |
| 207.3 MB | `.venv/Lib/site-packages/sudachidict_core/resources/system.dic` | Virtual environment dependency. | Ignore via `.venv/` |

## Secrets

| Path | Finding | Recommendation |
|---|---|---|
| `.env` | Local runtime configuration. Must not be committed. | Ignored |
| Existing `HEAD:.env` | Previously tracked environment file. | Replace history before pushing |
| `.env.example` | Sanitized template. No secrets. | Commit |

## Temporary Files And Caches

| Path | Recommendation |
|---|---|
| `logs/` | Ignore |
| `memory/` | Ignore |
| `workspace/` | Ignore |
| `Code/` | Ignore generated project output |
| `models/` | Ignore local model cache |
| `.venv/` | Ignore local virtual environment |
| `src/**/__pycache__/`, `tests/**/__pycache__/` | Ignore |
| `src/aura_agent.egg-info/` | Ignore |

## Voice And Media

| Path | Status | Recommendation |
|---|---|---|
| `voices/` | Present with `.gitkeep`; no voice sample present | Commit directory; LFS tracks future voice samples |
| `voices/aura_voice.wav` | Absent | Add only if intentionally public or use a private local file |
| `assets/` | Present with placeholder subdirectories | Commit |

## Git LFS

Configured patterns:

- `*.wav`
- `*.mp3`
- `*.flac`
- `*.pth`
- `*.bin`
- `*.safetensors`
- `*.onnx`
- `*.gguf`
- `*.pt`
- `voices/*`

`models/` is ignored, so local model caches are not published even though model
file extensions are protected by LFS if intentionally added elsewhere.

## Release Recommendation

Use a clean initial release commit. Do not push the old `Initial commit` because
it contains models, runtime logs, memory state, generated output, pycache files,
and `.env`.
