"""List USB serial ports via arduino-cli; tag common ESP32 DevKit USB-serial bridges without claiming the board."""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Callable

from aura.firmware.compile import _run_process_tree, find_cli

# CP210x, CH340, CH9102, FTDI FT232R: bridges commonly found on ESP32 DevKit boards (a tag, not a confirmation).
LIKELY_ESP32 = frozenset({("10C4", "EA60"), ("1A86", "7523"), ("1A86", "55D4"), ("0403", "6001")})
FAKE_PORT = "FAKE0"


def fake_enabled() -> bool:
    return os.environ.get("AURA_FAKE_BOARD") == "1"


def _hex(value: Any) -> str | None:
    return str(value).upper().removeprefix("0X") if value else None


def list_ports(cli: str | None = None, run: Callable[..., subprocess.CompletedProcess] | None = None) -> dict[str, Any]:
    ports: list[dict[str, Any]] = []
    cli = cli or find_cli(); missing = None if cli else "arduino-cli"
    if cli:
        try:
            done = (run or _run_process_tree)([cli, "board", "list", "--format", "json"], timeout=20)
            detected = json.loads(done.stdout or "{}").get("detected_ports", [])
        except (OSError, subprocess.TimeoutExpired, ValueError):
            detected, missing = [], "arduino-cli"
        for item in detected:
            port = item.get("port", {}); props = port.get("properties") or {}
            vid, pid = _hex(props.get("vid")), _hex(props.get("pid"))
            ports.append({"address": port.get("address"), "label": port.get("label") or port.get("address"), "protocol": port.get("protocol"),
                          "vid": vid, "pid": pid, "likelyEsp32": (vid, pid) in LIKELY_ESP32, "fake": False})
    if fake_enabled():
        ports.append({"address": FAKE_PORT, "label": "Fake board (test)", "protocol": "serial", "vid": None, "pid": None, "likelyEsp32": False, "fake": True})
    return {"ports": ports, "toolchainMissing": missing}
