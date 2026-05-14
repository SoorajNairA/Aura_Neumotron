# AURA XTTS-v2 Activation Report

Date: June 14, 2026  
Status: **Activated and live-tested**

## Voice System

| Item | Result |
|---|---|
| Model | `tts_models/multilingual/multi-dataset/xtts_v2` |
| Coqui package | `coqui-tts 0.25.3` |
| Model cache | `models/xtts/tts/tts_models--multilingual--multi-dataset--xtts_v2` |
| Model size | 1.75 GB |
| PyTorch | `2.8.0+cu128` |
| Device | CUDA 12.8 |
| GPU | NVIDIA GeForce RTX 3050 Laptop GPU, 4 GB |
| XTTS VRAM | 1831.5 MB allocated, approximately 1.9 GB reserved |
| Active voice | XTTS preset `Claribel Dervla` |
| Voice clone | Not active; `voices/aura_voice.wav` is absent |
| Hot reload | Enabled using reference-file modification time |
| Reference validation | WAV/MP3/FLAC, readable, 10-60 seconds |
| Fallbacks | XTTS-v2, then pyttsx3, then Windows .NET Speech |
| License | CPML accepted for educational, hackathon, non-commercial use |

FP16 was tested but disabled. This XTTS build fails blanket half-precision
conversion in GPT layer normalization. Reliable FP32 CUDA inference fits the
4 GB GPU with approximately 1.9 GB reserved.

## Performance

| Measurement | Result | Target |
|---|---:|---:|
| AURA constructor/startup return | 164.4 ms | Below 20 s: Pass |
| Cached XTTS model load | 23.35 s | Below 20 s: Miss |
| Background warmup generation | 3.75 s | Startup-only |
| Warm `Hello.` generation | 710.8 ms | Below 2 s: Pass |
| Warm `Hello.` playback | 1383.9 ms | Immediate after generation |
| Warm end-to-end `Hello.` | 2107.4 ms | Near target |
| Warm representative generation | 1.18-1.48 s | Below 2 s: Pass |
| CPU load plus generation | 19.72 s | Functional fallback |
| XTTS after Ollama inference | 3.79 s | Contention case |
| Queue wait, first utterance | 0.1 ms | Pass |

AURA no longer blocks on model loading. The GUI and fallback speech become
available in under one second while XTTS loads and warms in a daemon worker.
The backend switches to XTTS atomically after warmup.

## Live Tests

| Test | Result | Evidence |
|---|---|---|
| Natural `Hello.` playback | Pass | CUDA XTTS generated and played audio |
| Open VS Code | Pass | Spoken response and successful host launch |
| Build snake game | Pass | Five artifacts verified and project opened in VS Code |
| Ten-response queue stress | Pass | FIFO worker completed all ten without overlap or crashes |
| CPU fallback | Pass | CPU model loaded and generated a WAV |
| Temporary cleanup | Pass | No orphan `aura_xtts_*.wav` files |
| Ollama coexistence | Pass | Qwen replied in 2.80 s with XTTS resident; voice remained functional |
| Voice reference behavior | Pass | Missing reference selected default voice without failure |

Detailed live results: `logs/xtts_live_results.json`

## Regression

- Jarvis acceptance: **39/39 passed**
- Fast path: passed
- Conversation routing: passed
- Memory and project memory: passed
- Planner isolation: passed
- Thread safety: passed
- Offline-only operation: passed
- Streaming pipeline: passed
- Tool calling: passed
- ExecutiveAgent: passed
- Visibility policy: passed
- Python compilation and dependency validation: passed

The Ollama cold-health benchmark exceeded its latency target during the
parallel regression run. This is an existing model cold-start/performance issue,
not an XTTS functional regression.

## Operational Notes

- Adding or replacing `voices/aura_voice.wav` with a clean 10-60 second sample
  activates cloning automatically on the next utterance.
- Invalid or corrupted reference files are rejected while the current/default
  voice remains active.
- All model and Hugging Face cache paths are contained within `models/xtts`.
- XTTS generation, playback, queue wait, queue size, and fallback reasons are
  logged.
- On this 4 GB GPU, concurrent Ollama activity can temporarily increase XTTS
  generation latency, but both systems remain operational.

## Final Result

AURA's XTTS-v2 voice system is activated, local, CUDA accelerated, queued,
warm-started, voice-clone ready, and protected by two offline fallbacks.

Production restart verification:

- Faster-Whisper ready in 1.787 seconds.
- GUI/fallback TTS available before XTTS loading.
- XTTS CUDA model initialized successfully.
- Silent warmup completed.
- Production voice report confirmed `Claribel Dervla`, CUDA, RTX 3050, and both fallbacks.
