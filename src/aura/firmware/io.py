"""IO points the firmware can drive, and deterministic checks for the rule list a model proposes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind


@dataclass(frozen=True)
class Driver:
    role: str
    value: str
    pin: str
    libraries: tuple[str, ...] = ()


DRIVERS: dict[str, Driver] = {
    "ds18b20-module": Driver("input", "celsius", "onewire", ("OneWire@2.3.8", "DallasTemperature@4.0.5")),
    "capacitive-soil-v1": Driver("input", "percent", "analog"),
    "photoresistor-module": Driver("input", "percent", "analog"),
    "pir-hc-sr501": Driver("input", "bool", "digital"),
    "push-button": Driver("input", "bool", "digital"),
    "relay-module-5v": Driver("output", "bool", "digital"),
    "logic-mosfet-module": Driver("output", "bool", "digital"),
    "led-generic": Driver("output", "bool", "digital"),
    "sg90-servo": Driver("output", "angle", "pwm", ("ESP32Servo@3.2.1",)),
}
SLUGS = {"ds18b20-module": "temp", "capacitive-soil-v1": "soil", "photoresistor-module": "light", "pir-hc-sr501": "motion",
         "push-button": "button", "relay-module-5v": "relay", "led-generic": "led", "sg90-servo": "servo"}
LOAD_SLUGS = {"fan": "fan", "small_dc_pump": "pump", "small_dc_motor": "motor", "dc_motor": "motor", "motor": "motor"}
RANGES = {"celsius": (-55, 125, "°C"), "percent": (0, 100, "%"), "bool": (0, 1, ""), "angle": (0, 180, "°")}


@dataclass(frozen=True)
class IoPoint:
    id: str
    component_id: str
    name: str
    definition_id: str | None
    role: str | None
    value: str | None
    unit: str
    low: float
    high: float
    gpio: int | None
    supported: bool


def definition_id(entity: EngineeringEntity) -> str | None:
    return entity.metadata.get("parameters", {}).get("component_definition_id") or entity.metadata.get("component_definition_id")


def io_points(graph: EngineeringGraph) -> list[IoPoint]:
    """Every part wired to a controller GPIO, in controller port order."""
    connections = [e.metadata for e in graph.entities.values() if e.kind is EntityKind.CONNECTION]
    controller = next((e for e in graph.entities.values() if e.kind is EntityKind.COMPONENT and e.metadata.get("parameters", {}).get("gpio_map")), None)
    if controller is None: return []
    gpio_map = controller.metadata["parameters"]["gpio_map"]
    wired: dict[str, str] = {}
    for c in connections:
        if c.get("connection_type") not in {"signal", "control"}: continue
        if c.get("source_id") == controller.id and c.get("source_interface") in gpio_map: wired.setdefault(c["source_interface"], c["target_id"])
        if c.get("target_id") == controller.id and c.get("target_interface") in gpio_map: wired.setdefault(c["target_interface"], c["source_id"])
    counts: dict[str, int] = {}; points = []
    for port in gpio_map:
        if port not in wired or wired[port] not in graph.entities: continue
        part = graph.entities[wired[port]]; definition = definition_id(part); driver = DRIVERS.get(definition or "")
        slug = SLUGS.get(definition or "") or str(part.metadata.get("family", "part"))
        # Switching modules are named for their load, so the fan fail-safe follows the fan whichever driver switches it.
        if definition in {"logic-mosfet-module", "relay-module-5v"}:
            loads = [str(graph.entities[c["target_id"]].metadata.get("family")) for c in connections if c.get("source_id") == part.id
                     and c.get("connection_type") == "switched-power" and c.get("target_id") in graph.entities]
            slug = next((LOAD_SLUGS[family] for family in loads if family in LOAD_SLUGS), slug if definition == "relay-module-5v" else "switch")
        counts[slug] = counts.get(slug, 0) + 1
        low, high, unit = RANGES[driver.value] if driver else (0, 0, "")
        points.append(IoPoint(f"{slug}_{counts[slug]}", part.id, part.name, definition, driver.role if driver else None, driver.value if driver else None,
                              unit, low, high, gpio_map[port], driver is not None))
    return points


_RULE_PROPERTIES = {
    "input": {"type": "string"}, "when": {"enum": ["above", "below", "on", "off"]}, "threshold": {"type": ["number", "null"]},
    "release": {"type": ["number", "null"]}, "output": {"type": "string"}, "onValue": {"type": ["boolean", "number"]},
    "offValue": {"type": ["boolean", "number"]}, "minOnSeconds": {"type": ["number", "null"]},
}
RULES_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False, "required": ["rules", "explanation"],
    "properties": {"explanation": {"type": "string"}, "rules": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": list(_RULE_PROPERTIES), "properties": _RULE_PROPERTIES}}},
}
RULE_KEYS = tuple(_RULE_PROPERTIES)


class RuleError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_value(value: Any, io: IoPoint, field: str) -> None:
    ok = isinstance(value, bool) if io.value == "bool" else _number(value) and io.low <= value <= io.high
    if not ok: raise RuleError("OUT_OF_RANGE", f"{field} {value!r} does not fit {io.id} ({io.value} {io.low}–{io.high}).")


def validate_rules(payload: dict[str, Any], ios: list[IoPoint]) -> list[dict[str, Any]]:
    """Reject any rule that names a missing IO, points the wrong way, or leaves the part's range."""
    by_id = {io.id: io for io in ios if io.supported}
    rules = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rules, list): raise RuleError("BAD_CONDITION", "The rule list is missing.")
    clean = []
    for raw in rules:
        rule = {key: raw.get(key) if isinstance(raw, dict) else None for key in RULE_KEYS}
        for field in ("input", "output"):
            if rule[field] not in by_id: raise RuleError("UNKNOWN_IO", f"{rule[field]!r} is not an IO point of this design.")
        source, target = by_id[rule["input"]], by_id[rule["output"]]
        if source.role != "input": raise RuleError("WRONG_DIRECTION", f"{source.id} is an output, not an input.")
        if target.role != "output": raise RuleError("WRONG_DIRECTION", f"{target.id} is an input, not an output.")
        when, threshold, release = rule["when"], rule["threshold"], rule["release"]
        if when in {"on", "off"}:
            if source.value != "bool" or threshold is not None or release is not None:
                raise RuleError("BAD_CONDITION", f"'{when}' needs an on/off input and no threshold.")
        elif when in {"above", "below"}:
            if source.value == "bool" or not _number(threshold): raise RuleError("BAD_CONDITION", f"'{when}' needs a numeric threshold on a numeric input.")
            _check_value(threshold, source, "threshold")
            if release is not None:
                _check_value(release, source, "release")
                if (when == "above" and release > threshold) or (when == "below" and release < threshold):
                    raise RuleError("BAD_CONDITION", f"release {release} must be on the off side of threshold {threshold}.")
        else: raise RuleError("BAD_CONDITION", f"Unknown condition {when!r}.")
        _check_value(rule["onValue"], target, "onValue"); _check_value(rule["offValue"], target, "offValue")
        if rule["minOnSeconds"] is not None and not (_number(rule["minOnSeconds"]) and 0 <= rule["minOnSeconds"] <= 3600):
            raise RuleError("OUT_OF_RANGE", "minOnSeconds must be between 0 and 3600.")
        clean.append(rule)
    return clean


def default_rules(ios: list[IoPoint]) -> list[dict[str, Any]]:
    """One plain rule per output from the first supported input; used when no live model proposes rules."""
    source = next((io for io in ios if io.supported and io.role == "input"), None)
    if source is None: return []
    if source.value == "celsius": condition = ("above", 26, 24, None)
    elif source.value == "percent" and source.id.startswith("soil"): condition = ("below", 30, 45, 5)
    elif source.value == "percent": condition = ("below", 30, 40, None)
    else: condition = ("on", None, None, None)
    rules = []
    for target in (io for io in ios if io.supported and io.role == "output"):
        on, off = (True, False) if target.value == "bool" else (90, 0)
        rules.append(dict(zip(RULE_KEYS, (source.id, condition[0], condition[1], condition[2], target.id, on, off, condition[3]))))
    return rules
