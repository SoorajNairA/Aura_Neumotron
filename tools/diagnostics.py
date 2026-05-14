import socket
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    import torch

    from aura.config import Settings
except ImportError:
    print("Error: Missing dependencies. Run 'pip install -r requirements.txt'.")
    sys.exit(1)


def check_ollama() -> tuple[bool, str]:
    """Check whether the local Ollama service is accepting connections."""
    try:
        with socket.create_connection(("localhost", 11434), timeout=2):
            return True, "Ollama is running."
    except (OSError, socket.timeout):
        return False, "Ollama is not running. Start Ollama before launching AURA."


def check_gpu() -> tuple[bool, str]:
    """Report CUDA availability."""
    if torch.cuda.is_available():
        count = torch.cuda.device_count()
        name = torch.cuda.get_device_name(0)
        return True, f"GPU found: {name} ({count} device(s))"
    return False, "No CUDA GPU found. STT/TTS will use CPU fallbacks."


def check_xtts() -> tuple[bool, str]:
    """Check configured XTTS model and voice paths."""
    settings = Settings()
    if not settings.tts_cache_dir.exists():
        return False, f"XTTS model directory missing: {settings.tts_cache_dir}"
    if not settings.voice_reference.exists():
        return False, f"Voice reference missing: {settings.voice_reference}"
    return True, "XTTS model directory and voice reference found."


def run_diagnostics() -> int:
    print("=" * 60)
    print("  AURA Diagnostics Tool")
    print("=" * 60)

    python_ver = sys.version.split()[0]
    print(f"[OK] Python {python_ver}")

    gpu_ok, gpu_msg = check_gpu()
    print(f"{'[OK]' if gpu_ok else '[WARN]'} {gpu_msg}")

    ollama_ok, ollama_msg = check_ollama()
    print(f"{'[OK]' if ollama_ok else '[FAIL]'} {ollama_msg}")

    xtts_ok, xtts_msg = check_xtts()
    print(f"{'[OK]' if xtts_ok else '[WARN]'} {xtts_msg}")

    dependencies_ok = True
    for module_name in ("faster_whisper", "pyttsx3"):
        try:
            __import__(module_name)
            print(f"[OK] {module_name} found")
        except ImportError:
            dependencies_ok = False
            print(f"[FAIL] {module_name} not found")

    report_path = Path("logs/diagnostics_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as report:
        report.write("# AURA Diagnostics Report\n\n")
        report.write(f"- Python: {python_ver}\n")
        report.write(f"- GPU: {gpu_msg}\n")
        report.write(f"- Ollama: {ollama_msg}\n")
        report.write(f"- XTTS: {xtts_msg}\n")
        report.write(f"- Dependencies: {'Ready' if dependencies_ok else 'Missing'}\n")
        report.write("\n## Summary\n")
        ready = ollama_ok and dependencies_ok
        report.write(
            "System is ready to launch AURA.\n"
            if ready
            else "System has missing required components. See the checks above.\n"
        )

    print("-" * 60)
    print(f"Report saved to {report_path}")
    print("=" * 60)
    return 0 if ollama_ok and dependencies_ok else 1


if __name__ == "__main__":
    raise SystemExit(run_diagnostics())
