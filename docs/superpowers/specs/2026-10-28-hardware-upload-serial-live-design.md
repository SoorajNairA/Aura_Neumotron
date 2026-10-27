# Hardware: USB upload, serial monitor, live board view — design

Date: 2026-10-28 · Branch: `AURA-nemotron_test1` · Deadline: 2026-10-30 17:00 UTC
Scope: roadmap phase 7. Builds on generated ESP32 firmware (fan sketch and generic sketch), which already prints
one JSON telemetry line per second at 115200 baud.

## Goal

From the Build space, the user picks a USB port, uploads the current revision's firmware, watches the serial
output, and sees the simulation and 3D follow the real board. Hardware may not be present: everything is built
for a real ESP32 DevKit and proven with a fake board; the app never claims hardware validation without telemetry
from a real board.

## Global constraints

- All board access goes through `arduino-cli` (already required for compile; `AURA_ARDUINO_CLI` or `PATH`).
  No new Python or npm dependencies.
- Never claim hardware validation without evidence. "Uploaded" records a flash only. "Observed on hardware"
  needs telemetry lines carrying the current revision id from a non-fake port.
- No silent fallback: a fake board is used only when `AURA_FAKE_BOARD=1`, and every fake result is labelled
  "Fake board (test)".
- Port names, raw serial text and arduino-cli output are shown escaped; nothing secret is logged or exported.
- One upload and one monitor per project at a time; uploads and monitor never run on the same port at once.

## 1. Ports

- `GET /api/hardware/ports` → `[{address, label, protocol, vid, pid, likelyEsp32, fake}]` from
  `arduino-cli board list --format json`.
- `likelyEsp32` is true for common ESP32 DevKit USB-serial bridges: CP210x `10C4:EA60`, CH340 `1A86:7523`,
  CH9102 `1A86:55D4`, FTDI `0403:6001`. Shown as "likely ESP32 (unverified)", never as a confirmed board.
- Toolchain missing → `{"ports":[], "toolchainMissing":"arduino-cli"}`, not an error page.

## 2. Upload

- `POST /api/projects/{id}/firmware/upload {port}`.
- Allowed only when the last compile for the current revision passed (409 `COMPILE_REQUIRED` otherwise) and no
  monitor holds that port (409 `PORT_BUSY`).
- Runs `arduino-cli compile --upload -p <port> --fqbn <fqbn> <sketch>` with the same sketch the firmware GET returns
  (fan sketch with the user's edit, or generic sketch). Timeout 180 s.
- Result `{status: "uploaded"|"failed"|"toolchain_missing", port, revisionId, uploadedAt, errors, fake}`;
  failures keep the last 2 000 characters of output, escaped, and a short reason (port not found, permission denied,
  no response from board — "hold BOOT while uploading" hint for the ESP32 "Failed to connect" message).
- The UI asks first: "This writes the firmware to the board on <port>." Uploaded copy:
  "Uploaded revision <rev> to <port> at <time> — not yet observed running."

## 3. Serial monitor

- `POST /api/projects/{id}/serial/start {port}` / `POST .../serial/stop`; `GET .../serial?after=<seq>` returns
  `{running, port, lines:[{seq, time, text, telemetry|null}], evidence}` (polled about once a second by the UI).
- Backend runs `arduino-cli monitor -p <port> -q --config 115200` as a subprocess; a reader thread keeps the last
  500 lines in memory. Stop, project switch and app shutdown kill the process.
- Lines that parse as a JSON object with a `rev` field are telemetry; others are shown raw.
- Telemetry whose `rev` differs from the current revision raises the banner "Board runs revision <x>, not the current
  design (<y>). Upload to update it."

## 4. Live board view

- Simulation space gets a source switch: `Simulated` (default) / `Live board` (enabled while the monitor runs).
- Live: input values and output states come from the latest telemetry (`null` input = sensor fault); 3D follows the
  live outputs (fan spin, servo angle, LED).
- Agreement check (generic firmware): AURA evaluates the approved rules on the live inputs with the same TS
  evaluator; an output that differs from the board's report for 3 consecutive lines shows
  "Board output disagrees with the rule for <io>". Fan firmware uses `fanControl` the same way.
- Label: "Live board — values reported by the firmware over USB serial".

## 5. Hardware evidence

- When at least 3 telemetry lines with the current revision id arrive from a non-fake port, AURA records
  `{port, revisionId, firstSeen, lines, agreement: "agrees"|"disagrees"|"not checked"}` per project (persisted).
- Build space and Code view show "Observed on hardware: <port>, revision <rev>, <n> lines, <time>" or
  "Not tried on hardware". Fake-board runs show "Fake board (test) — not hardware evidence" and never write evidence.

## 6. Fake board

- `AURA_FAKE_BOARD=1` adds port `FAKE0` (`fake:true`). Upload to it succeeds after a short delay without
  arduino-cli; its monitor emits one telemetry line per second for the current revision, inputs sweeping their
  ranges and outputs computed from the stored rules (or `fanControl`), plus a startup text line.
- Used by unit, API and Playwright tests. Never active unless the variable is set.

## Testing

- pytest: port parsing and `likelyEsp32` from recorded `board list` JSON; upload gate (no compile, stale compile,
  busy port); upload command line and failure parsing with a fake runner; monitor line parsing (telemetry, raw,
  wrong revision); evidence written only for non-fake matching telemetry; fake board end to end through the API.
- vitest: live agreement check (3-line rule), telemetry → simulation inputs/outputs mapping.
- Playwright (mocked API): port picker with "likely ESP32 (unverified)"; upload confirm; serial log; wrong-revision
  banner; Live board switch; disagreement warning; "Not tried on hardware" vs "Observed on hardware".
- Real board: optional manual run by the user; result recorded honestly in `docs/active/README.md`.
- GitNexus impact before editing existing symbols; detect-changes before each commit.

## Out of scope

OTA/Wi-Fi upload, boards other than ESP32 DevKit, sending commands to the board, calibration, long-term logging.
