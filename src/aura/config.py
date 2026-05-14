from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Load .env first (production/default), then .env.example as a fallback for local setup.
load_dotenv(dotenv_path=".env", override=False)
load_dotenv(dotenv_path=".env.example", override=False)


@dataclass(frozen=True)
class Settings:
    """AURA local-only configuration. All services run offline."""

    creator_name: str = os.getenv("AURA_CREATOR_NAME", "Sooraj").strip() or "Sooraj"
    
    # Local TTS (XTTS-v2 with pyttsx3 and Windows Speech fallbacks)
    voice_persona: str = os.getenv(
        "AURA_VOICE_PERSONA",
        "Warm, confident, emotionally aware executive copilot voice.",
    )
    tts_backend: str = os.getenv("AURA_TTS_BACKEND", "auto").strip().lower()
    voice_reference: Path = Path(
        os.getenv("AURA_VOICE_REFERENCE", "voices/aura_voice.wav")
    )
    tts_device: str = os.getenv("AURA_TTS_DEVICE", "cuda").strip().lower()
    tts_cache_dir: Path = Path(os.getenv("AURA_TTS_CACHE_DIR", "models/xtts"))
    auto_warmup: bool = os.getenv("AURA_AUTO_WARMUP", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    local_tts_rate: int = int(os.getenv("AURA_LOCAL_TTS_RATE", "165"))
    local_tts_voice_index: int = int(os.getenv("AURA_LOCAL_TTS_VOICE_INDEX", "0"))
    max_research_results: int = int(os.getenv("AURA_MAX_RESEARCH_RESULTS", "8"))
    max_execution_steps: int = int(os.getenv("AURA_MAX_EXECUTION_STEPS", "16"))
    auto_reveal_results: bool = os.getenv(
        "AUTO_REVEAL_RESULTS", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}

    # Compatibility fields retained for existing planner, startup, and TTS APIs.
    # Empty defaults keep the normal runtime fully local.
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_planner_model: str = os.getenv(
        "OPENAI_PLANNER_MODEL", os.getenv("OPENAI_MODEL", "")
    )
    openai_conversation_model: str = os.getenv(
        "OPENAI_CONVERSATION_MODEL", os.getenv("OPENAI_MODEL", "")
    )
    openai_fallback_models: tuple[str, ...] = tuple(
        model.strip()
        for model in os.getenv("OPENAI_FALLBACK_MODELS", "").split(",")
        if model.strip()
    )
    openai_planner_temperature: float = float(
        os.getenv("OPENAI_PLANNER_TEMPERATURE", "0.2")
    )
    openai_conversation_temperature: float = float(
        os.getenv("OPENAI_CONVERSATION_TEMPERATURE", "0.6")
    )

    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    elevenlabs_model_id: str = os.getenv(
        "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"
    )
    elevenlabs_stability: float = float(os.getenv("ELEVENLABS_STABILITY", "0.22"))
    elevenlabs_similarity_boost: float = float(
        os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.88")
    )
    elevenlabs_style: float = float(os.getenv("ELEVENLABS_STYLE", "0.7"))
    elevenlabs_speaker_boost: bool = os.getenv(
        "ELEVENLABS_SPEAKER_BOOST", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    elevenlabs_clarity: float = float(os.getenv("ELEVENLABS_CLARITY", "0.75"))
    elevenlabs_naturalness: float = float(
        os.getenv("ELEVENLABS_NATURALNESS", "0.90")
    )

    # ------------------------------------------------------------------
    # Local Conversation Brain (Ollama / Qwen)
    # ------------------------------------------------------------------
    conversation_backend: str = os.getenv("AURA_CONVERSATION_BACKEND", "ollama")
    ollama_base_url: str = os.getenv("AURA_OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_conversation_model: str = os.getenv("AURA_OLLAMA_MODEL", "auto").strip()
    ollama_primary_model: str = os.getenv(
        "AURA_OLLAMA_PRIMARY_MODEL", "qwen3:8b"
    ).strip()
    ollama_fallback_model: str = os.getenv(
        "AURA_OLLAMA_FALLBACK_MODEL", "qwen2.5:3b"
    ).strip()
    ollama_request_timeout: int = int(os.getenv("AURA_OLLAMA_TIMEOUT", "120"))
    ollama_context_length: int = int(os.getenv("AURA_OLLAMA_CONTEXT_LENGTH", "32768"))

    hardware_profile: str = os.getenv(
        "AURA_HARDWARE_PROFILE", "auto"
    ).strip().lower()
    performance_min_ram_gb: float = float(
        os.getenv("AURA_PERFORMANCE_MIN_RAM_GB", "12")
    )
    performance_min_vram_gb: float = float(
        os.getenv("AURA_PERFORMANCE_MIN_VRAM_GB", "3.5")
    )

    stt_model: str = os.getenv("AURA_STT_MODEL", "small")
    stt_device: str = os.getenv("AURA_STT_DEVICE", "cpu")
    stt_compute_type: str = os.getenv("AURA_STT_COMPUTE_TYPE", "int8")

    sample_rate: int = int(os.getenv("AURA_SAMPLE_RATE", "16000"))
    max_record_seconds: int = int(os.getenv("AURA_MAX_RECORD_SECONDS", "12"))
    silence_threshold: float = float(os.getenv("AURA_SILENCE_THRESHOLD", "0.01"))
    silence_hold_seconds: float = float(os.getenv("AURA_SILENCE_HOLD_SECONDS", "1.2"))

    memory_dir: Path = Path(os.getenv("AURA_MEMORY_DIR", "memory"))
    log_dir: Path = Path(os.getenv("AURA_LOG_DIR", "logs"))

    confirm_words: tuple[str, ...] = tuple(
        w.strip().lower()
        for w in os.getenv("AURA_CONFIRM_WORDS", "yes,confirm,proceed").split(",")
        if w.strip()
    )
    reject_words: tuple[str, ...] = tuple(
        w.strip().lower()
        for w in os.getenv("AURA_REJECT_WORDS", "no,stop,cancel").split(",")
        if w.strip()
    )

    wake_word: str = os.getenv("AURA_WAKE_WORD", "aura").strip().lower()

    demo_mode: bool = os.getenv("AURA_DEMO_MODE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    demo_workspace: Path = Path(os.getenv("AURA_DEMO_WORKSPACE", "DemoWorkspace"))


def ensure_runtime_dirs(settings: Settings) -> None:
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    if settings.demo_mode:
        settings.demo_workspace.mkdir(parents=True, exist_ok=True)
