"""Flash the current revision's sketch with arduino-cli; a fake port succeeds only when the fake board is enabled."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from aura.firmware.compile import _run_process_tree, find_cli
from aura.firmware.sketch import FirmwareArtifact

from .ports import FAKE_PORT, fake_enabled

_HINTS = (("failed to connect", "Hold BOOT on the board while uploading."),
          ("access is denied", "The port is in use or not permitted; close other serial programs."),
          ("permission denied", "The port is in use or not permitted; close other serial programs."),
          ("could not open port", "The port was not found; check the cable and pick the port again."),
          ("no such file", "The port was not found; check the cable and pick the port again."))


@dataclass(frozen=True)
class UploadResult:
    status: str  # "uploaded" | "failed" | "toolchain_missing"
    port: str
    revision_id: str
    uploaded_at: str
    errors: tuple[str, ...] = ()
    raw_output: str = ""
    fake: bool = False
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "port": self.port, "revisionId": self.revision_id, "uploadedAt": self.uploaded_at,
                "errors": list(self.errors), "rawOutput": self.raw_output, "fake": self.fake, "hint": self.hint}


def upload_hint(output: str) -> str | None:
    lowered = output.lower()
    return next((hint for needle, hint in _HINTS if needle in lowered), None)


def upload_sketch(artifact: FirmwareArtifact, port: str, *, cli: str | None = None,
                  run: Callable[..., subprocess.CompletedProcess] | None = None, timeout_s: float = 180) -> UploadResult:
    now = datetime.now(timezone.utc).isoformat()
    if port == FAKE_PORT and fake_enabled():
        return UploadResult("uploaded", port, artifact.revision_id, now, fake=True)
    cli = cli or find_cli()
    if cli is None: return UploadResult("toolchain_missing", port, artifact.revision_id, now, ("arduino-cli not found",))
    root = tempfile.mkdtemp(prefix="aura-upload-")
    try:
        sketch_dir = Path(root) / "aura_device"; sketch_dir.mkdir()
        (sketch_dir / "aura_device.ino").write_text(artifact.source, encoding="utf-8")
        try:
            done = (run or _run_process_tree)([cli, "compile", "--upload", "-p", port, "--fqbn", artifact.fqbn, str(sketch_dir)], timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return UploadResult("failed", port, artifact.revision_id, now, (f"Upload timed out after {timeout_s:g}s",), hint=upload_hint("failed to connect"))
        except FileNotFoundError:
            return UploadResult("toolchain_missing", port, artifact.revision_id, now, ("arduino-cli not found",))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    output = f"{done.stdout or ''}\n{done.stderr or ''}".strip()
    if done.returncode == 0: return UploadResult("uploaded", port, artifact.revision_id, now, raw_output=output[-2000:])
    last = output.splitlines()[-1] if output else "Upload failed"
    return UploadResult("failed", port, artifact.revision_id, now, (last[-300:],), output[-2000:], hint=upload_hint(output))
