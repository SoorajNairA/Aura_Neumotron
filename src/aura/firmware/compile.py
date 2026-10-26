from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .sketch import FirmwareArtifact

DEFAULT_TIMEOUT_S = 180.0
_ERROR = re.compile(r"^(?:.*[\\/])?(?P<file>[^\\/:\n]+):(?P<line>\d+):(?:\d+:)? (?:fatal )?error: (?P<message>.+)$", re.M)
_SIZE = re.compile(r"Sketch uses (\d+) bytes")


@dataclass(frozen=True)
class CompileResult:
    status: str  # "passed" | "failed" | "toolchain_missing"
    errors: tuple[dict[str, Any], ...]
    size_bytes: int | None
    revision_id: str
    compiled_at: str
    raw_output: str
    missing: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "errors": list(self.errors), "sizeBytes": self.size_bytes, "revisionId": self.revision_id,
                "compiledAt": self.compiled_at, "rawOutput": self.raw_output, "missing": self.missing}


def find_cli() -> str | None:
    return os.environ.get("AURA_ARDUINO_CLI") or shutil.which("arduino-cli")


def compile_sketch(artifact: FirmwareArtifact, *, cli: str | None = None, timeout_s: float = DEFAULT_TIMEOUT_S,
                   run: Callable[..., subprocess.CompletedProcess] | None = None) -> CompileResult:
    """Compile with arduino-cli; a missing toolchain is reported, never treated as a pass."""
    now = lambda: datetime.now(timezone.utc).isoformat()
    cli = cli or find_cli()
    if cli is None:
        return CompileResult("toolchain_missing", (), None, artifact.revision_id, now(), "", "arduino-cli")
    run = run or subprocess.run
    with tempfile.TemporaryDirectory(prefix="aura-fw-") as root:
        sketch_dir = Path(root) / "aura_fan"
        sketch_dir.mkdir()
        (sketch_dir / "aura_fan.ino").write_text(artifact.source, encoding="utf-8")
        try:
            done = run([cli, "compile", "--fqbn", artifact.fqbn, "--warnings", "default", str(sketch_dir)],
                       capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return CompileResult("failed", ({"file": None, "line": None, "message": f"Compile timed out after {timeout_s:g}s"},), None,
                                 artifact.revision_id, now(), "")
        except FileNotFoundError:
            return CompileResult("toolchain_missing", (), None, artifact.revision_id, now(), "", "arduino-cli")
    output = f"{done.stdout or ''}\n{done.stderr or ''}"
    if done.returncode == 0:
        size = _SIZE.search(output)
        return CompileResult("passed", (), int(size.group(1)) if size else None, artifact.revision_id, now(), output)
    lowered = output.lower()
    if "platform not installed" in lowered or "unknown fqbn" in lowered:
        return CompileResult("toolchain_missing", (), None, artifact.revision_id, now(), output, "esp32:esp32 core")
    missing_header = re.search(r"([A-Za-z0-9_]+)\.h: No such file or directory", output)
    if missing_header:
        return CompileResult("toolchain_missing", (), None, artifact.revision_id, now(), output, f"library providing {missing_header.group(1)}.h")
    errors = tuple({"file": m["file"], "line": int(m["line"]), "message": m["message"].strip()} for m in _ERROR.finditer(output))
    return CompileResult("failed", errors or ({"file": None, "line": None, "message": output.strip()[-500:] or "Compile failed"},), None,
                         artifact.revision_id, now(), output)
