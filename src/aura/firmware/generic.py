"""ESP32 sketch built from fixed part drivers plus the approved rule list; the model never writes C++."""
from __future__ import annotations

import json
from typing import Any

from aura.engineering_graph.model import EngineeringGraph, EntityKind

from .io import DRIVERS, IoPoint, io_points
from .sketch import FQBN, FirmwareArtifact, FirmwareUnsupported


def _num(value: Any) -> str:
    return "1" if value is True else "0" if value is False else f"{float(value):g}"


def _initial(ios: list[IoPoint], rules: list[dict[str, Any]]) -> dict[str, Any]:
    first: dict[str, Any] = {}
    for rule in rules: first.setdefault(rule["output"], rule["offValue"])
    return {io.id: first.get(io.id, False if io.value == "bool" else 0) for io in ios if io.role == "output"}


def control_block(ios: list[IoPoint], rules: list[dict[str, Any]]) -> str:
    """Plain C++ (no Arduino calls) so the same block runs on the board and in the g++ truth-table test."""
    inputs = [io for io in ios if io.supported and io.role == "input"]; outputs = [io for io in ios if io.supported and io.role == "output"]
    initial = _initial(outputs, rules)
    fields = [f"  float {io.id} = 0; bool {io.id}_ok = false;" for io in inputs]
    fields += [f"  float {io.id} = {_num(initial[io.id])}; unsigned long {io.id}_since = 0;" for io in outputs]
    lines = ["// BEGIN control", "struct State {", *fields, "};", "State S;", "",
             "void setOut(float &out, unsigned long &since, float value, float onValue, unsigned long now, unsigned long minOnMs) {",
             "  if (out == value) return;",
             "  if (out == onValue && minOnMs && now - since < minOnMs) return;  // minOnSeconds keeps the output on",
             "  if (value == onValue) since = now;",
             "  out = value;", "}", "", "void control(unsigned long now) {"]
    for rule in rules:
        i, o = rule["input"], rule["output"]; on, off = _num(rule["onValue"]), _num(rule["offValue"])
        threshold, release = rule["threshold"], rule["release"]
        if rule["when"] == "above": cond, rel = f"S.{i} >= {_num(threshold)}", f"S.{i} <= {_num(release)}" if release is not None else f"S.{i} < {_num(threshold)}"
        elif rule["when"] == "below": cond, rel = f"S.{i} <= {_num(threshold)}", f"S.{i} >= {_num(release)}" if release is not None else f"S.{i} > {_num(threshold)}"
        elif rule["when"] == "on": cond, rel = f"S.{i} >= 0.5", f"S.{i} < 0.5"
        else: cond, rel = f"S.{i} < 0.5", f"S.{i} >= 0.5"
        min_ms = int(round((rule["minOnSeconds"] or 0) * 1000)); args = f"S.{o}, S.{o}_since"
        # A cooling fan runs while its sensor is faulted; everything else goes to its off value.
        fault = on if o.startswith("fan_") else off
        lines += [f"  // {json.dumps(rule)}",
                  f"  if (!S.{i}_ok) setOut({args}, {fault}, {on}, now, 0);",
                  f"  else if ({cond}) setOut({args}, {on}, {on}, now, {min_ms});",
                  f"  else if ({rel}) setOut({args}, {off}, {on}, now, {min_ms});"]
    return "\n".join([*lines, "}", "// END control"]) + "\n"


def _upper(io: IoPoint) -> str:
    return io.id.upper()


def _driver_code(io: IoPoint) -> tuple[list[str], list[str], list[str], list[str]]:
    """(globals, setup, read, write) lines for one supported IO."""
    pin, name = f"{_upper(io)}_PIN", io.id; kind = DRIVERS[io.definition_id or ""].pin
    if kind == "onewire":
        return ([f"OneWire ow_{name}({pin});", f"DallasTemperature ds_{name}(&ow_{name});"], [f"  ds_{name}.begin();"],
                [f"  if (tick) {{ ds_{name}.requestTemperatures(); float v = ds_{name}.getTempCByIndex(0); S.{name}_ok = v != DEVICE_DISCONNECTED_C; S.{name} = v; }}"], [])
    if kind == "analog":
        return ([f"#define {_upper(io)}_RAW_AT_0 3000  // uncalibrated: raw reading at 0 %", f"#define {_upper(io)}_RAW_AT_100 1300  // uncalibrated: raw reading at 100 %"],
                [], ["  {", f"    int raw = analogRead({pin});",
                     "    // A reading pinned to a rail is treated as a disconnected sensor (assumption).",
                     f"    S.{name}_ok = raw > 0 && raw < 4095;",
                     f"    S.{name} = constrain(map(raw, {_upper(io)}_RAW_AT_0, {_upper(io)}_RAW_AT_100, 0, 100), 0, 100);", "  }"], [])
    if io.definition_id == "push-button":
        return ([f"int {name}_raw = HIGH; unsigned long {name}_changed = 0;"], [f"  pinMode({pin}, INPUT_PULLUP);"],
                ["  {", f"    int raw = digitalRead({pin});", f"    if (raw != {name}_raw) {{ {name}_raw = raw; {name}_changed = now; }}",
                 f"    if (now - {name}_changed >= 30) S.{name} = raw == LOW ? 1 : 0;  // pressed = LOW, 30 ms debounce",
                 f"    S.{name}_ok = true;", "  }"], [])
    if io.role == "input":
        return ([], [f"  pinMode({pin}, INPUT);"], [f"  S.{name} = digitalRead({pin}) == HIGH ? 1 : 0; S.{name}_ok = true;"], [])
    if kind == "pwm":
        return ([f"Servo servo_{name};"], [f"  servo_{name}.attach({pin});"], [], [f"  servo_{name}.write((int)S.{name});"])
    return ([], [f"  pinMode({pin}, OUTPUT);", f"  digitalWrite({pin}, LOW);"], [], [f"  digitalWrite({pin}, S.{name} >= 0.5 ? HIGH : LOW);"])


def generate_generic_sketch(graph: EngineeringGraph, rules: list[dict[str, Any]]) -> FirmwareArtifact:
    controller = next((e for e in graph.entities.values() if e.kind is EntityKind.COMPONENT and e.metadata.get("parameters", {}).get("gpio_map") is not None), None)
    reasons = []
    if controller is None or controller.metadata.get("parameters", {}).get("component_definition_id") != "esp32-devkit-v1":
        reasons.append("Firmware generation supports only an ESP32 DevKit V1 controller")
    ios = io_points(graph) if controller else []; supported = [io for io in ios if io.supported]
    if controller and not supported: reasons.append("No part wired to the controller has a driver yet")
    if not graph.current_revision_id: reasons.append("The design has no committed revision")
    if reasons: raise FirmwareUnsupported(reasons)
    libraries = tuple(dict.fromkeys(lib for io in supported for lib in DRIVERS[io.definition_id or ""].libraries))
    includes = {"OneWire@2.3.8": "#include <OneWire.h>", "DallasTemperature@4.0.5": "#include <DallasTemperature.h>", "ESP32Servo@3.2.1": "#include <ESP32Servo.h>"}
    globals_, setup, reads, writes = [], [], [], []
    for io in supported:
        g, s, r, w = _driver_code(io); globals_ += g; setup += s; reads += r; writes += w
    report = ['  Serial.print("{\\"rev\\":\\""); Serial.print(REVISION_ID); Serial.print("\\"");']
    for io in supported:
        value = f"if (S.{io.id}_ok) Serial.print(S.{io.id}, 2); else Serial.print(\"null\");" if io.role == "input" else f"Serial.print(S.{io.id}, 0);"
        report.append(f'  Serial.print(",\\"{io.id}\\":"); {value}')
    report.append('  Serial.println("}");')
    source = "\n".join([
        f"// AURA generated firmware for Engineering Graph revision {graph.current_revision_id}.",
        "// Generated by AURA from fixed part drivers and the approved rule list; no model wrote this code.",
        "// Part ratings and wiring are catalogue values and assumptions until checked on real hardware.",
        *[includes[lib] for lib in libraries], "",
        *[f"#define {_upper(io)}_PIN {io.gpio}" for io in supported],
        f'static const char *REVISION_ID = "{graph.current_revision_id}";', "",
        *globals_, "", control_block(ios, rules),
        "unsigned long lastReport = 0;", "bool firstTick = true;", "",
        "void setup() {", "  Serial.begin(115200);", *setup, "}", "",
        "void report() {", *report, "}", "",
        "void loop() {", "  unsigned long now = millis();", "  bool tick = firstTick || now - lastReport >= 1000;",
        *reads, "  control(now);", *writes,
        "  if (tick) { firstTick = false; lastReport = now; report(); }  // one JSON telemetry line per second", "}", ""])
    return FirmwareArtifact(source, graph.current_revision_id, FQBN, libraries, {io.id: io.gpio for io in supported},
                            kind="generic", ios=tuple(ios), rules=tuple(rules))
