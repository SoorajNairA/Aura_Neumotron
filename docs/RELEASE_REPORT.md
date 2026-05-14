# Release Report

Date: June 14, 2026

## Release Target

Professional GitHub release for hackathon selection, portfolio review, recruiter
review, and open-source presentation.

## Test Summary

| Suite | Result | Notes |
|---|---:|---|
| Jarvis acceptance | 39/39 passed | `logs/jarvis_acceptance.json` |
| XTTS live activation | 7/7 passed | `logs/xtts_live_results.json` |
| Fast path | Passed | Zero LLM calls for common greetings |
| Conversation routing | Passed | No planner leakage for discussion |
| Memory | Passed | Working-memory continuity verified |
| Planner isolation | Passed | Planner activates only for goals |
| Thread safety | Passed | Working memory concurrent writes safe |
| Offline mode | Passed | No external OpenAI or ElevenLabs calls |
| Streaming TTS pipeline | Passed | Chunking and fallback path validated |
| Tool calling | Passed | App, URL, file, and safety routing |
| ExecutiveAgent | Passed | Project generation and memory integration |
| Visibility policy | Passed | Created outputs are revealed |

## Latency Metrics

| Metric | Observed |
|---|---:|
| Fast path greetings | 0.0-0.1 ms |
| Memory continuation | 44.3 ms |
| Project creation in acceptance runner | 28-52 ms dry-run verified |
| XTTS startup return | 164.4 ms |
| XTTS CUDA warm generation | 710.8 ms |
| XTTS VRAM allocated | 1831.5 MB |
| XTTS queue stress | 10 utterances, no overlap |
| Faster-Whisper startup after cache fix | 1.787 s |

Known caveat: Ollama cold latency exceeded the 2 s first-token target during
parallel regression testing. This is a local model performance issue, not a
repository hygiene or release blocker.

## Hardware

- NVIDIA GeForce RTX 3050 Laptop GPU
- 4 GB VRAM
- CUDA PyTorch `2.8.0+cu128`
- Faster-Whisper small on CPU int8
- XTTS-v2 on CUDA
- Ollama Qwen local conversation model

## Repository Hygiene

- `.env` ignored
- `models/` ignored
- `logs/` ignored
- `memory/` ignored
- `workspace/` ignored
- Generated `Code/` projects ignored
- `.venv/` ignored
- Git LFS configured for audio and model binary formats
- Public `.env.example` contains no secrets

## Release Status

The working tree is configured for a clean public release. The existing
pre-release Git history is not safe and should be replaced by the clean initial
release commit.
