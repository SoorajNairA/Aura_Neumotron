from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind

TEMPLATE_PATH = Path(__file__).with_name("fan_sketch.ino.tmpl")
FQBN = "esp32:esp32:esp32"
# shortcut: library versions are pinned by hand; confirm against the installed toolchain when it changes.
LIBRARIES = ("OneWire@2.3.8", "DallasTemperature@3.9.0")
HYSTERESIS_C = 2.0
DEFAULT_THRESHOLD_C = 26.0


@dataclass(frozen=True)
class FirmwareArtifact:
    source: str
    revision_id: str
    fqbn: str
    libraries: tuple[str, ...]
    pins: dict[str, int]
    t_on_c: float
    t_off_c: float


class FirmwareUnsupported(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = tuple(reasons)


def generate_fan_sketch(graph: EngineeringGraph) -> FirmwareArtifact:
    """Render the fan sketch from the graph's ESP32 pins and sensor threshold."""
    components = [e for e in graph.entities.values() if e.kind is EntityKind.COMPONENT]
    connections = [e.metadata for e in graph.entities.values() if e.kind is EntityKind.CONNECTION]

    def first(family: str) -> EngineeringEntity | None:
        return next((c for c in components if c.metadata.get("family") == family), None)

    controller, sensor, fan, driver = first("microcontroller_board"), first("temperature_sensor"), first("fan"), first("mosfet_driver")
    reasons = []
    if controller is None or controller.metadata.get("parameters", {}).get("component_definition_id") != "esp32-devkit-v1":
        reasons.append("Firmware generation supports only an ESP32 DevKit V1 controller")
    if sensor is None: reasons.append("No temperature sensor in the design")
    if fan is None: reasons.append("No fan in the design")
    if driver is None or not any(c.get("source_id") == driver.id and c.get("target_id") == fan.id for c in connections if fan):
        reasons.append("No MOSFET driver switching the fan")
    if not graph.current_revision_id: reasons.append("The design has no committed revision")
    if reasons: raise FirmwareUnsupported(reasons)

    gpio_map = controller.metadata["parameters"].get("gpio_map", {})

    def controller_pin(other: EngineeringEntity) -> int | None:
        for c in connections:
            if c.get("connection_type") not in {"signal", "control"}: continue
            if (c.get("source_id"), c.get("target_id")) == (controller.id, other.id): return gpio_map.get(c.get("source_interface"))
            if (c.get("source_id"), c.get("target_id")) == (other.id, controller.id): return gpio_map.get(c.get("target_interface"))
        return None

    pins = {"temperature_data": controller_pin(sensor), "fan_gate": controller_pin(driver)}
    missing = [name for name, pin in pins.items() if pin is None]
    if missing: raise FirmwareUnsupported([f"No GPIO assignment for {name}" for name in missing])
    t_on = float(sensor.metadata.get("parameters", {}).get("threshold_c", DEFAULT_THRESHOLD_C));t_off = t_on - HYSTERESIS_C
    values = {"ONE_WIRE_PIN": pins["temperature_data"], "FAN_PIN": pins["fan_gate"], "T_ON_C": f"{t_on:.1f}", "T_OFF_C": f"{t_off:.1f}",
              "REVISION_ID": graph.current_revision_id}
    source = TEMPLATE_PATH.read_text(encoding="utf-8")
    for key, value in values.items(): source = source.replace("{{" + key + "}}", str(value))
    return FirmwareArtifact(source, graph.current_revision_id, FQBN, LIBRARIES, pins, t_on, t_off)
