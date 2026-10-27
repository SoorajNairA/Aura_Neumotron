"""One serial monitor per project: arduino-cli monitor (or the test-only fake board) read on a thread into a ring buffer."""
from __future__ import annotations

import json
import subprocess
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from aura.firmware.sketch import FirmwareArtifact

MAX_LINE = 2000


def parse_line(raw: bytes | str) -> dict[str, Any]:
    text = (raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw).rstrip("\r\n")[:MAX_LINE]
    try: value = json.loads(text) if text.startswith("{") else None
    except ValueError: value = None
    return {"text": text, "telemetry": value if isinstance(value, dict) and "rev" in value else None}


def evidence(lines: list[dict[str, Any]], revision_id: str, *, port: str, fake: bool) -> dict[str, Any] | None:
    """Hardware evidence needs 3+ telemetry lines for the current revision from a real port; a fake board never counts."""
    matching = [line for line in lines if (line.get("telemetry") or {}).get("rev") == revision_id]
    if fake or len(matching) < 3: return None
    return {"port": port, "revisionId": revision_id, "firstSeen": matching[0]["time"], "lines": len(matching), "agreement": "not checked"}


def _evaluate(rules: list[dict[str, Any]], inputs: dict[str, Any], outputs: dict[str, Any], since: dict[str, float], now: float) -> None:
    # Same semantics as the generated control(); used only to make the fake board's outputs plausible.
    for rule in rules:
        out, on, off = rule["output"], rule["onValue"], rule["offValue"]; value = inputs.get(rule["input"]); min_on = rule.get("minOnSeconds") or 0

        def put(target: Any, minimum: float) -> None:
            if float(outputs[out]) == float(target): return
            if float(outputs[out]) == float(on) and minimum and now - since.get(out, 0) < minimum: return
            if float(target) == float(on): since[out] = now
            outputs[out] = target

        if value is None: put(on if out.startswith("fan_") else off, 0); continue
        v, t, r = float(value), rule.get("threshold") or 0, rule.get("release")
        cond, rel = {"above": (v >= t, v <= r if r is not None else v < t), "below": (v <= t, v >= r if r is not None else v > t),
                     "on": (v >= .5, v < .5), "off": (v < .5, v >= .5)}[rule["when"]]
        if cond: put(on, min_on)
        elif rel: put(off, min_on)


def fake_board(artifact: FirmwareArtifact, stop: threading.Event, period: float = 1.0) -> Iterator[str]:
    """Test-only board: a boot line, then one telemetry line per period for the revision it was 'flashed' with."""
    yield "AURA fake board (test) - not hardware"
    step, since, rules = 0, {}, list(artifact.rules)
    outputs = {rule["output"]: rule["offValue"] for rule in rules}; fan = False
    while not stop.is_set():
        if artifact.kind == "fan":
            t = 20 + (step % 20) * .6; fan = t >= (artifact.t_on_c or 26) or (fan and t > (artifact.t_off_c or 24))
            line = {"t_c": round(t, 2), "fan": int(fan), "rev": artifact.revision_id}
        else:
            inputs = {}
            for io in artifact.ios:
                if io.supported and io.role == "input":
                    inputs[io.id] = int(step % 4 < 2) if io.value == "bool" else round(io.low + (io.high - io.low) * (step % 20) / 19, 2)
            _evaluate(rules, inputs, outputs, since, step * period)
            line = {"rev": artifact.revision_id, **inputs, **{key: (int(v) if isinstance(v, bool) else v) for key, v in outputs.items()}}
        yield json.dumps(line, separators=(",", ":"))
        step += 1; stop.wait(period)


class SerialSession:
    def __init__(self, port: str, revision_id: str, *, cli: str | None = None, popen: Callable[..., Any] | None = None,
                 fake_source: Callable[[threading.Event], Iterator[str]] | None = None) -> None:
        self.port, self.revision_id, self.fake = port, revision_id, fake_source is not None
        self._cli, self._popen, self._fake_source = cli, popen, fake_source
        self._buffer: deque[dict[str, Any]] = deque(maxlen=500); self._seq = 0; self._lock = threading.Lock()
        self._stop = threading.Event(); self._process: Any = None; self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def _add(self, raw: bytes | str) -> None:
        line = parse_line(raw)
        with self._lock:
            self._seq += 1; self._buffer.append({"seq": self._seq, "time": datetime.now(timezone.utc).isoformat(), **line})

    def _read(self) -> None:
        if self._fake_source is not None:
            for raw in self._fake_source(self._stop):
                if self._stop.is_set(): break
                self._add(raw)
            return
        stream = self._process.stdout
        while not self._stop.is_set():
            raw = stream.readline(MAX_LINE * 2)  # bounded: a line without a newline cannot grow without limit
            if not raw: break
            self._add(raw)

    def start(self) -> None:
        if self._fake_source is None:
            command = [self._cli or "arduino-cli", "monitor", "-p", self.port, "-q", "--config", "115200"]
            self._process = (self._popen or subprocess.Popen)(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        self._thread = threading.Thread(target=self._read, name=f"serial-{self.port}", daemon=True); self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try: self._process.wait(timeout=2)
            except subprocess.TimeoutExpired: self._process.kill()
        if self._thread is not None: self._thread.join(timeout=3)

    def lines(self, after: int = 0) -> list[dict[str, Any]]:
        with self._lock: return [line for line in self._buffer if line["seq"] > after]
