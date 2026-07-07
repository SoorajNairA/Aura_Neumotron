from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InterfaceDefinition:
    name: str
    kind: str
    position: tuple[float, float, float] = (0, 0, 0)
    orientation: tuple[float, float, float, float] = (0, 0, 0, 1)
    axis: tuple[float, float, float] | None = None
    compatible: tuple[str, ...] = ()
    clearance_mm: float = 0


def component_interfaces(family: str, dimensions: tuple[float, float, float]) -> tuple[InterfaceDefinition, ...]:
    """Return reusable physical/electrical interfaces for a component family."""
    width, length, height = dimensions
    electrical = {
        "controller": (("power", "electrical_power_in"), ("ground", "electrical_ground"), ("signal", "control_output")),
        "microcontroller_board": (("power", "electrical_power_in"), ("ground", "electrical_ground"), ("signal", "control_output")),
        "servo": (("power", "electrical_power_in"), ("ground", "electrical_ground"), ("signal", "control_input")),
        "low_voltage_power_source": (("power", "electrical_power_out"), ("ground", "electrical_ground")),
        "system power": (("power", "electrical_power_out"), ("ground", "electrical_ground")),
    }
    result = [InterfaceDefinition(name, kind, compatible=("electrical_connector",)) for name, kind in electrical.get(family, ())]
    if family == "servo":
        result += [
            InterfaceDefinition("output", "rotating_output", (0, -length / 2 - 3, 0), axis=(0, -1, 0), compatible=("rotating_input",)),
            InterfaceDefinition("body-mount", "fixed_mount", (0, 0, -height / 2), axis=(0, 0, -1), compatible=("structural_face",)),
        ]
    elif family in {"simple_arm", "lid", "dispensing-mechanism", "generic_mechanical_part"}:
        result += [
            InterfaceDefinition("joint-input", "rotating_input", (0, 0, -length / 2), axis=(0, 1, 0), compatible=("rotating_output", "hinge_axis")),
            InterfaceDefinition("end-face", "structural_face", (0, 0, length / 2), axis=(0, 0, 1), compatible=("fixed_mount", "structural_face")),
            InterfaceDefinition("fixed-input", "fixed_mount", (0, 0, -length / 2), axis=(0, 0, -1), compatible=("structural_face",)),
        ]
    elif family in {"mounting_plate", "base", "enclosure", "container"}:
        result.append(InterfaceDefinition("mount-face", "structural_face", (0, 0, height / 2), axis=(0, 0, 1), compatible=("fixed_mount",)))
    elif family == "hinge":
        result.append(InterfaceDefinition("axis", "hinge_axis", (0, 0, 0), axis=(0, 1, 0), compatible=("rotating_input",)))
    return tuple(result)


def interface_dict(owner: str, interface: InterfaceDefinition) -> dict[str, Any]:
    return {"interfaceId": f"{owner}:{interface.name}", "semanticId": owner, "type": interface.kind,
        "localPosition": list(interface.position), "localOrientation": list(interface.orientation),
        "axis": list(interface.axis) if interface.axis else None, "compatibleTypes": list(interface.compatible),
        "clearanceMm": interface.clearance_mm}
