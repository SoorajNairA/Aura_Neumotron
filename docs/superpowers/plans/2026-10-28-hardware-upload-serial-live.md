# Hardware upload, serial monitor, live board view — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload the current revision's ESP32 firmware over USB, monitor its serial telemetry, drive the simulation/3D from the live board, and record hardware evidence only from real telemetry.

**Architecture:** A new `aura.hardware` package wraps `arduino-cli` (board list, compile --upload, monitor) behind small functions with injectable runners, plus a fake board for tests. FastAPI routes in `server.py` gate upload on a passing compile and own one monitor session per project. The React Build space lists ports, uploads, shows the serial log and evidence; the Simulation space gains a Live board source using the existing rule evaluator.

**Tech Stack:** Python/FastAPI, subprocess + threads, SQLite/Postgres repositories, React/TypeScript, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-28-hardware-upload-serial-live-design.md`

## Global Constraints

- All board access through `arduino-cli` (`aura.firmware.compile.find_cli`); no new Python or npm dependencies.
- "Uploaded" records a flash only; "Observed on hardware" needs ≥3 telemetry lines with the current revision id from a non-fake port.
- Fake board only when `AURA_FAKE_BOARD=1`; every fake result carries `fake: true` and the UI copy "Fake board (test) — not hardware evidence".
- `likelyEsp32` VID:PID set: `10C4:EA60`, `1A86:7523`, `1A86:55D4`, `0403:6001`; UI copy "likely ESP32 (unverified)".
- Upload: 409 `COMPILE_REQUIRED` unless last compile for the current revision passed; 409 `PORT_BUSY` if a monitor holds the port; 409 `UPLOAD_IN_PROGRESS`; timeout 180 s; keep last 2 000 chars of output.
- Monitor: `arduino-cli monitor -p <port> -q --config 115200`; keep last 500 lines; wrong-revision banner copy "Board runs revision <x>, not the current design (<y>). Upload to update it."
- Live label "Live board — values reported by the firmware over USB serial"; disagreement after 3 consecutive differing lines: "Board output disagrees with the rule for <io>".
- GitNexus impact before editing existing symbols; detect-changes before each commit.

## Review Focus

1. A monitor subprocess must never outlive its session (stop, second start, project switch, app shutdown).
2. Upload while the monitor holds the same port must be refused, not race.
3. Telemetry from an older revision must never produce hardware evidence for the current one.
4. A fake-board run must never write evidence or show "Observed on hardware".
5. Malformed serial bytes (non-UTF-8, partial JSON, huge lines) must not crash the reader or the UI.

---

### Task 1: Ports and fake board

**Files:** Create `src/aura/hardware/__init__.py`, `src/aura/hardware/ports.py`, `tests/test_hardware_ports.py`. Modify `server.py` (route).

**Interfaces — Produces:** `LIKELY_ESP32: frozenset[tuple[str,str]]`; `list_ports(cli:str|None=None, run=None) -> dict` → `{"ports":[{address,label,protocol,vid,pid,likelyEsp32,fake}], "toolchainMissing":str|None}`; `fake_enabled() -> bool` (`AURA_FAKE_BOARD=="1"`), fake port `FAKE0`. Route `GET /api/hardware/ports`.

- [ ] Step 1 failing tests: recorded `board list` JSON with a CP210x port (`properties.vid "0x10C4"`, `pid "0xEA60"`) → `likelyEsp32` true, COM1 without vid → false; missing cli → `toolchainMissing:"arduino-cli"`; `AURA_FAKE_BOARD=1` adds `FAKE0` with `fake:true`; route returns the same.
- [ ] Step 2–4 FAIL → implement → PASS. Step 5 commit `Hardware port listing with fake board`.

### Task 2: Upload

**Files:** Create `src/aura/hardware/upload.py`, `tests/test_hardware_upload.py`. Modify `server.py` (`POST /api/projects/{id}/firmware/upload`; reuse `_effective_firmware`, `firmware_compiles`).

**Interfaces — Produces:** `UploadResult(status, port, revision_id, uploaded_at, errors, raw_output, fake)` with `to_dict()` (`status` ∈ `uploaded|failed|toolchain_missing`); `upload_sketch(artifact, port, *, cli=None, run=None, timeout_s=180) -> UploadResult` running `[cli,"compile","--upload","-p",port,"--fqbn",fqbn,sketch_dir]`; `upload_hint(output) -> str|None` ("Failed to connect" → "Hold BOOT on the board while uploading."). Fake port → uploaded without a subprocess.

- [ ] Step 1 failing tests: command line built with port and fqbn; non-zero exit → `failed` with hint and ≤2 000 chars output; route 409 `COMPILE_REQUIRED` with no compile and with a compile for an older revision; 409 `PORT_BUSY` when a monitor session holds the port (after Task 3; here test via the busy-port registry); fake board upload `uploaded`, `fake:true`.
- [ ] Step 2–4 FAIL → implement → PASS (+ full suite). Step 5 commit `Upload current firmware over USB`.

### Task 3: Serial monitor, telemetry and evidence

**Files:** Create `src/aura/hardware/serial.py`, `tests/test_hardware_serial.py`. Modify `server.py` (start/stop/get routes, shutdown cleanup), repositories (`save_hardware_evidence` / `get_hardware_evidence`, table `hardware_evidence(project_id PK, payload, updated_at)` SQLite + Postgres + migration).

**Interfaces — Produces:** `parse_line(raw:bytes|str) -> {"text":str,"telemetry":dict|None}` (decode with `errors="replace"`, truncate at 2 000 chars, telemetry only for JSON objects with `rev`); `class SerialSession(port, revision_id, *, cli=None, popen=None, fake_source=None)` with `start()`, `stop()`, `lines(after:int) -> list[dict]` (seq, time, text, telemetry), `running`, ring buffer 500; `evidence(lines, revision_id, fake) -> dict|None` (≥3 matching telemetry lines, non-fake). Fake source yields a startup line then one telemetry line per second for the current revision, inputs sweeping, outputs from stored rules (`rules` evaluated by a Python port of the rule semantics used only for the fake) or fan thresholds. Routes: `POST /api/projects/{id}/serial/start {port}`, `POST .../serial/stop`, `GET .../serial?after=` → `{running, port, fake, lines, wrongRevision, evidence}`; `GET /firmware` gains `hardwareEvidence`.

- [ ] Step 1 failing tests: parse JSON/raw/invalid bytes/huge line; session with a fake popen emitting lines → buffered with seq; stop kills the process; second start stops the first; wrong-revision telemetry flagged and gives no evidence; 3 matching non-fake lines → evidence persisted and returned by firmware GET; fake session never persists evidence; upload refused with `PORT_BUSY` while session runs on that port; app shutdown stops sessions.
- [ ] Step 2–4 FAIL → implement → PASS (+ full suite). Step 5 commit `Serial monitor, telemetry and hardware evidence`.

### Task 4: Build space UI

**Files:** Create `src/aura/workspace/web/frontend/src/BuildView.tsx`, `hardware.ts`, `hardware.test.ts`. Modify `WorkspaceApp.tsx` (enable Build tab when firmware supported), `CodeView.tsx` (evidence line), `styles.css`, `e2e/build.spec.ts`.

**Interfaces — Produces:** `evidenceText(evidence, fake) -> string` ("Observed on hardware: <port>, revision <rev>, <n> lines, <time>" | "Not tried on hardware"); `portLabel(port) -> "<label> — likely ESP32 (unverified)"`; BuildView polls `GET .../serial?after=` every 1 s while running.

- [ ] Step 1 failing tests (vitest: `evidenceText`, `portLabel`; e2e mocked): ports listed with "likely ESP32 (unverified)" and "Fake board (test)"; Upload asks to confirm "This writes the firmware to the board on COM5." and shows "Uploaded revision r to COM5 at … — not yet observed running"; 409 `COMPILE_REQUIRED` shows "Compile this revision first"; serial log shows lines; wrong-revision banner text; "Not tried on hardware" vs "Observed on hardware: COM5…".
- [ ] Step 2–4 FAIL → implement → PASS. Step 5 build, commit `Build space: ports, upload, serial monitor, evidence`.

### Task 5: Live board view

**Files:** Create `src/aura/workspace/web/frontend/src/live.ts`, `live.test.ts`. Modify `GenericSimulation.tsx`, `SimulationPanel.tsx`, `WorkspaceApp.tsx` (shared serial poll state, 3D outputs/spin from live), `e2e/build.spec.ts`.

**Interfaces — Produces:** `telemetryInputs(telemetry, ios) -> Record<string,Value|null>`; `telemetryOutputs(telemetry, ios) -> Record<string,Value>`; `agreement(history:{inputs,outputs}[], rules, ios) -> {disagree:string[]}` (an output listed only when the last 3 lines all differ from `evaluate` replayed over the history); fan variant uses `fanControl` with `t_c`/`fan` keys.

- [ ] Step 1 failing tests: mapping from telemetry keys; 2 differing lines → none, 3 → listed; fan telemetry agreement; e2e: Live board switch enabled only while monitor runs, shows live values and label, disagreement warning, 3D spin follows live fan output.
- [ ] Step 2–4 FAIL → implement → PASS. Step 5 build, commit `Live board view with rule agreement check`.

### Task 6: Fake-board end-to-end check and docs

- [ ] Run backend with `AURA_FAKE_BOARD=1`, create the plant project, compile, upload to `FAKE0`, start monitor, confirm lines and that no evidence is written; record honestly in `docs/active/README.md` §0 and README (Hardware section: ports, upload, monitor, BOOT hint, fake board, evidence rule). If a real board is connected, run once and record result; otherwise state "not tried on hardware". Commit `Document hardware upload and live board view`.
