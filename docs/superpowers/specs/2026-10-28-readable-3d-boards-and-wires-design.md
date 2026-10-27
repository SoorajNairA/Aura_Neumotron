# Readable 3D boards and pin-to-pin wires — design

Date: 2026-10-28 · Branch: `AURA-nemotron_test1` · Deadline: 2026-10-30 17:00 UTC
Reference look: `AURA desk fan engineering studio (1).png` (concept image, not a target for photorealism).

## Goal

A user can read the 3D assembly and learn from it: board names and pin labels printed on the boards, every
cable leaving a real pin and landing on a real pin, colour-coded and numbered, and lighting close to the
reference image. Today wires are drawn between backend-guessed interface points, so cables end in empty space.

## Global constraints

- No new dependencies: Three.js core plus `three/examples` only.
- Pin labels and wire endpoints come from the same data as the code and wiring views: controller `gpio_map`,
  `pinout.ts` (ESP32-DevKitC J2/J3 table) and graph connections. No second copy of pin data.
- No logos or trademarks; only part names, pin names and polarity marks.
- A cable is drawn only between two known pin anchors. If either end has no anchor, the cable is not invented:
  the backend route is drawn dashed and labelled "approximate route".
- Wire routes are an illustration of the connections ("Illustrative routing — not a measured cable layout").
- Effects degrade automatically on weak GPUs or `prefers-reduced-motion`; picking, explode, X-ray, isolate,
  simulation and live views keep working.

## 1. Lighting and look

`RoomEnvironment` PMREM environment, ACES filmic tone mapping, soft shadows from one key light onto a shadow-only
ground plane, and SSAO/GTAO-style ambient occlusion through `EffectComposer` (falls back to no post-processing
when the frame time stays above 33 ms or WebGL2 is missing). Light neutral background like the reference.

## 2. Pin anchors on models

Every detailed model adds named, invisible anchor objects at its real pin tips: `pin:<name>`.
- ESP32-DevKitC: all 38 header pins named from `pinout.ts` (`IO4`, `3V3`, `GND`, `EN`, `VP`…) at 2.54 mm pitch,
  J2 left / J3 right, pin 1 at the antenna end.
- Modules: DS18B20 `VCC/DAT/GND`; MOSFET module `IN/VCC/GND` header and `V+/V-/OUT+/OUT-` terminals; relay
  `IN/VCC/GND` and `COM/NO/NC`; soil `VCC/AOUT/GND`; light `VCC/AO/GND`; PIR `VCC/OUT/GND`; LED `A/K`; button `1/2`;
  servo lead `SIG/V+/GND`; fan `+/-`; power module `+/-`; resistor/diode `A/B` / `A/K`; breadboard rails.
- A per-family table maps graph interface names to anchor names (e.g. controller `signal-1` → `IO<gpio>` via
  `gpio_map`; `vcc-out` → `3V3`; `ground` → `GND`; sensor `signal` → `DAT`).

## 3. Pin-to-pin jumper wires

- For each graph electrical connection (`signal`, `control`, `power`, `regulated-power`, `switched-power`, `ground`)
  whose two ends resolve to anchors, draw a jumper: short vertical rise from each pin, a smooth arc over the parts
  (height scales with distance), tube radius 0.6 mm, a small connector sleeve at each end.
- Colours: power `+` red, ground black, signal/data yellow, control/PWM orange, switched load blue.
- Each wire gets a number; a small numbered tag floats at the arc top. The inspector "Connections" list shows the
  same numbers. Hover a wire: tooltip `1 · DS18B20 · DAT ↔ ESP32 DevKit · IO4 (GPIO4, J3 pin 13)`. Click selects it
  and highlights both pins.
- Wires follow the parts in explode, isolate and X-ray (recomputed from anchor world positions).

## 4. Readable board text

Silkscreen drawn as `CanvasTexture` decals on the board top surfaces: board name (e.g. `ESP32-DevKitC`), pin labels
beside each header pin, `VCC DAT GND` on module headers, `+`/`−` beside terminals, part names on chips/relays.
Text is drawn at high resolution (≥ 8 px per mm) so it reads when zoomed; at distance the camera-facing
`PinLabels` overlay shows the pins used by the design (only connected pins, to avoid clutter).

## 5. More detail on the core parts

ESP32: WROOM-style shield with antenna area, USB connector, EN/BOOT buttons, LDO, LEDs, both 19-pin rows.
DS18B20: TO-92 body with flat face and 3-pin header. MOSFET: TO-220 with heatsink, blue screw terminal, LED.
Others keep their Task 9 models plus anchors and silkscreen.

## Testing

- vitest: every studio model exposes the anchors listed above; ESP32 anchor for `IO4` sits at J3 pin 13 position
  (2.54 mm pitch); interface→anchor mapping for fan and plant graphs; wire builder returns one wire per resolvable
  connection with the right colour and number, and no wire when an end is missing (approximate route instead);
  silkscreen canvas contains the pin names.
- Playwright: fan project screenshot (stored as artifact) and hooks: `__auraWires()` lists wires with both
  endpoints; every wire end lies within 0.5 mm of its anchor; hover tooltip text; inspector numbers match.
- Manual: side-by-side screenshot with the reference image, reported honestly.

## Out of scope

Photoreal path tracing, measured cable lengths, wire collision avoidance beyond the arc, custom part images.
