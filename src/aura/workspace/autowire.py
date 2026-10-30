"""Deterministic wiring of a newly added catalogue part to the project's controller (spec 2: auto-wire on add).

Wires follow the part's own pins (`PinDefinition` name and role), never a generic `signal`. Power and ground go to
the board's supply pins, I2C/SPI share the board's bus ports, and every other signal takes a free `signal-N` port.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aura.engineering_graph.interfaces import BUS_GPIOS, allocate_gpio
from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind, Relationship
from aura.engineering_graph.patches import GraphOperation, PatchOperation
from aura.verification.pins import PinDefinition, pins_for_definition

BOARD_LABELS = {"vcc-out": "3V3", "power": "5V", "ground": "GND"}
I2C_ROLES, SPI_ROLES = ("i2c_sda", "i2c_scl"), ("spi_sck", "spi_mosi", "spi_miso")
I2C_PORTS, SPI_PORTS = ("i2c-sda", "i2c-scl"), ("spi-sck", "spi-mosi", "spi-miso")
BUS_PORT = {"i2c_sda": "i2c-sda", "i2c_scl": "i2c-scl", "spi_sck": "spi-sck", "spi_mosi": "spi-mosi", "spi_miso": "spi-miso"}
# Roles where the part drives the wire (connection type "signal"); everything else is driven by the board ("control").
# SDA is bidirectional; it is recorded as the part's data line, SCL as board-driven.
PART_DRIVES = frozenset({"digital_out", "analog_out", "uart_tx", "spi_miso", "i2c_sda"})
# Allocation pool per role: an input to the board may use input-only GPIOs, an output may not; analog needs ADC1.
POOL_FAMILY = {"analog_out": "soil_moisture_sensor", "digital_out": "switch", "uart_tx": "switch"}
GPIO_ROLES = frozenset({"digital_in", "digital_out", "analog_out", "pwm_in", "uart_tx", "uart_rx", "spi_cs"})


@dataclass(frozen=True)
class Wire:
    connection_id: str
    source_id: str
    source_interface: str
    target_id: str
    target_interface: str
    connection_type: str
    name: str = ""
    parent_id: str | None = None

    def to_ops(self) -> list[GraphOperation]:
        """The connection entity plus its `-edge` relationship, the storage form every wire uses."""
        metadata = {"source_id": self.source_id, "target_id": self.target_id, "connection_type": self.connection_type,
                    "source_interface": self.source_interface, "target_interface": self.target_interface}
        edge = Relationship(f"{self.connection_id}-edge", self.source_id, self.target_id, self.connection_type, {"connection_id": self.connection_id})
        return [GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(self.connection_id, EntityKind.CONNECTION, self.name or self.connection_id, self.parent_id, metadata)),
                GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=edge)]


def _error(code: str, message: str, status: int = 409) -> Exception:
    from .modifications import ModificationError  # modifications imports this module
    return ModificationError(code, message, status)


def _has_uart(entity: EngineeringEntity) -> bool:
    definition = entity.metadata.get("parameters", {}).get("component_definition_id") or entity.metadata.get("component_definition_id")
    pins = entity.metadata.get("pins")
    roles = [p.get("role") for p in pins] if pins else [p.role for p in pins_for_definition(definition, str(entity.metadata.get("family", "")))]
    return any(role in ("uart_tx", "uart_rx") for role in roles)


def _claim_bus(gpio_map: dict[str, int], ports: tuple[str, ...], bus: str) -> None:
    """Reserve a bus's board GPIOs once; refuse when another port already sits on one of them."""
    for port in ports:
        holder = next((p for p, g in gpio_map.items() if g == BUS_GPIOS[port] and p != port), None)
        if holder: raise _error("BUS_PINS_IN_USE", f"The {bus} bus needs GPIO{BUS_GPIOS[port]} ({port}), but {holder} is using it. Move {holder} to another pin first.")
    for port in ports: gpio_map[port] = BUS_GPIOS[port]


def autowire(graph: EngineeringGraph, controller: EngineeringEntity, entity_id: str, pins: tuple[PinDefinition, ...], gpio_map: dict[str, int],
             free_ports: list[str], *, name: str | None = None, claimed: set[str] | None = None) -> tuple[list[Wire], list[dict[str, Any]]]:
    """Wire one added part by its pins; returns the wires and check dicts, mutating `gpio_map` and consuming `free_ports`.

    `claimed` carries resources taken by earlier parts of the same proposal (the graph does not hold them yet)."""
    name = name or entity_id; suffix = entity_id.rsplit("-", 1)[-1]
    claimed = claimed if claimed is not None else set()
    wires: list[Wire] = []; notes: list[str] = []; checks: list[dict[str, Any]] = []

    def connect(pin: PinDefinition, board_port: str, kind: str, note: str | None = None) -> None:
        connection_id = f"connection-user-wire-{suffix}-{pin.name}"
        ends = (entity_id, pin.name, controller.id, board_port) if kind == "signal" else (controller.id, board_port, entity_id, pin.name)
        wires.append(Wire(connection_id, *ends, kind, f"{name} {pin.name}", graph.project_id))
        notes.append(f"{pin.label} to {note or BOARD_LABELS.get(board_port, board_port)}")

    def take_port(pin: PinDefinition) -> str:
        gpio = allocate_gpio(POOL_FAMILY.get(pin.role, "indicator"), None, set(gpio_map.values()))
        if gpio is None or not free_ports: raise _error("NO_FREE_PIN", "Not enough free safe ESP32 pins for these parts.")
        port = free_ports.pop(0); gpio_map[port] = gpio
        return port

    roles = {pin.role for pin in pins}
    if roles & set(I2C_ROLES): _claim_bus(gpio_map, I2C_PORTS, "I2C")
    if roles & set(SPI_ROLES) or "spi_cs" in roles: _claim_bus(gpio_map, SPI_PORTS, "SPI")
    if roles & {"uart_tx", "uart_rx"}:
        holder = next((e for e in graph.find(kind=EntityKind.COMPONENT) if e.id != entity_id and e.id != controller.id and _has_uart(e)), None)
        if holder or "uart" in claimed:
            raise _error("UART_IN_USE", f"{name} needs the serial port, but {holder.name if holder else 'another part in this selection'} already uses it.")
        claimed.add("uart")
    for pin in pins:
        if pin.role == "power_in":
            low, high = pin.voltage_range or (3.3, 3.3)
            if low <= 3.3 <= high: connect(pin, "vcc-out", "power")
            elif low <= 5.0 <= high: connect(pin, "power", "power")
            else: raise _error("NEEDS_EXTERNAL_SUPPLY", f"{name} needs {low:g}–{high:g} V; add a supply first")
            if pin.voltage_range is None:
                checks.append({"state": "WARNING", "message": f"{name}: supply range unknown; wired to 3V3, check its datasheet."})
        elif pin.role == "ground": connect(pin, "ground", "ground")
        elif pin.role in BUS_PORT: connect(pin, BUS_PORT[pin.role], "signal" if pin.role in PART_DRIVES else "control")
        elif pin.role in GPIO_ROLES:
            port = take_port(pin)
            connect(pin, port, "signal" if pin.role in PART_DRIVES else "control", f"{port} (GPIO{gpio_map[port]})")
    if wires: checks.insert(0, {"state": "PASSED", "message": f"{name} wired: {', '.join(notes)}"})
    return wires, checks
