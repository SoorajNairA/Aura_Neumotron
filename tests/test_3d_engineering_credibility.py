from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.planner.schemas import ConnectionSpec, ProjectRequest
from aura.planner.service import PlannerService
from aura.verification.service import VerificationService
from aura.workspace.assembly import engineering_assembly
from aura.workspace.bridge import WorkspaceBridge
from aura.workspace.representation_service import representation_specs
from aura.workspace.representations import RepresentationType
from aura.workspace.server import create_app


def compile_project(objective: str):
    plan = PlannerService().plan(ProjectRequest("3D credibility", objective, ("Use isolated low-voltage DC",)))
    verification = VerificationService().verify(plan)
    assert verification.accepted, [(item.check, item.message) for item in verification.findings if item.severity == "critical"]
    graph = WorkspaceBridge().commit(EngineeringGraph(plan.entities[0].id), verification)
    assembly = engineering_assembly(graph)
    circuit = next(spec for spec in representation_specs(graph) if spec.kind is RepresentationType.CIRCUIT_SCHEMATIC)
    return plan, verification, graph, assembly, circuit


@pytest.mark.parametrize(("objective", "definition", "name", "visual"), (
    ("Build a temperature monitor. Use an Arduino Nano.", "arduino-nano-v3", "Arduino Nano", "arduino_nano"),
    ("Build a temperature monitor. Use an ESP32 DevKit.", "esp32-devkit-v1", "ESP32 DevKit", "esp32_devkit"),
    ("Build a one-axis platform using an SG90 servo.", "sg90-servo", "SG90 Servo", "sg90"),
    ("Build a distance alarm using HC-SR04.", "hc-sr04-class", "HC-SR04 Ultrasonic Sensor", "hc_sr04"),
))
def test_named_hardware_survives_graph_schematic_and_3d(objective, definition, name, visual):
    _, _, graph, assembly, circuit = compile_project(objective)
    entity = next(item for item in graph.find(kind=EntityKind.COMPONENT)
                  if item.metadata.get("parameters", {}).get("component_definition_id") == definition)
    assert entity.name == name
    assert entity.metadata["parameters"]["resolution_quality"] == "EXACT"
    schematic = next(item for item in circuit.payload["components"] if item["semanticId"] == entity.id)
    part = next(item for item in assembly["parts"] if item["semanticId"] == entity.id)
    assert schematic["displayName"] == name and schematic["componentDefinitionId"] == definition
    assert part["label"] == name and part["visualKind"] == visual


def test_solar_tracker_has_directional_sensor_network_and_graph_derived_wires():
    objective = "Build a tabletop two-axis solar tracker that automatically points a small solar panel toward the brightest light source using an Arduino Nano."
    _, _, graph, assembly, circuit = compile_project(objective)
    components = graph.find(kind=EntityKind.COMPONENT)
    assert next(item for item in components if item.name == "Arduino Nano").metadata["parameters"]["resolution_quality"] == "EXACT"
    assert len([item for item in components if item.metadata.get("family") == "light_sensor"]) == 4
    assert len([item for item in components if item.metadata.get("family") == "resistor"]) == 4
    assert len([item for item in components if item.metadata.get("family") == "servo"]) == 2
    assert not assembly["unresolvedPrimaryMechanism"]
    assert not assembly["visualConnectivity"]["severeIntersections"]
    assert circuit.payload["fidelity"] == {"portsComplete": True, "netsComplete": True}
    assert_wire_fidelity(graph, assembly)


@pytest.mark.parametrize(("objective", "load_family"), (
    ("Build an Arduino Nano controlled tabletop DC fan with adjustable speed.", "fan"),
    ("Build an Arduino Nano system that turns on a small DC water pump when soil moisture becomes low.", "small_dc_pump"),
))
def test_inductive_loads_receive_driver_protection_and_no_direct_gpio(objective, load_family):
    plan, _, graph, assembly, _ = compile_project(objective)
    families = {item.metadata.get("family") for item in graph.find(kind=EntityKind.COMPONENT)}
    assert {load_family, "mosfet_driver", "flyback_diode"} <= families
    if load_family == "small_dc_pump": assert "soil_moisture_sensor" in families
    controller = next(item.id for item in graph.find(kind=EntityKind.COMPONENT) if item.metadata.get("family") == "microcontroller_board")
    load = next(item.id for item in graph.find(kind=EntityKind.COMPONENT) if item.metadata.get("family") == load_family)
    assert not any({connection.source_id, connection.target_id} == {controller, load} for connection in plan.connections)
    assert_wire_fidelity(graph, assembly)


def test_remote_car_has_two_driven_wheels_and_shared_motor_driver():
    _, _, graph, assembly, _ = compile_project("Build a remote-controlled two-wheel car with wireless control.")
    components = graph.find(kind=EntityKind.COMPONENT)
    assert len([item for item in components if item.metadata.get("family") == "small_dc_motor"]) == 2
    assert len([item for item in components if item.metadata.get("family") == "drive_wheel"]) == 2
    assert any(item.metadata.get("family") == "motor_driver" for item in components)
    assert any(item.metadata.get("family") == "wireless_module" for item in components)
    assert not assembly["unresolvedPrimaryMechanism"]
    assert_wire_fidelity(graph, assembly)


def test_relay_module_avoids_duplicate_transistor_but_bare_relay_gets_support():
    module = compile_project("Build an Arduino system that uses a relay module to switch a low-voltage lamp.")[2]
    module_families = {item.metadata.get("family") for item in module.find(kind=EntityKind.COMPONENT)}
    assert "relay_module" in module_families and "mosfet_driver" not in module_families

    bare = compile_project("Build an Arduino system that uses a bare relay to switch a low-voltage lamp.")[2]
    bare_families = {item.metadata.get("family") for item in bare.find(kind=EntityKind.COMPONENT)}
    assert {"bare_relay", "mosfet_driver", "flyback_diode", "indicator"} <= bare_families


def test_direct_controller_to_fan_is_a_critical_architecture_error():
    plan = PlannerService().plan(ProjectRequest("unsafe", "Build an Arduino Nano controlled tabletop DC fan.", ("Use low voltage",)))
    controller = next(item for item in plan.components if item.role == "microcontroller_board")
    fan = next(item for item in plan.components if item.role == "fan")
    unsafe = ConnectionSpec("connection-unsafe-gpio-fan", controller.id, fan.id, "signal-8", "power", "control", "Unsafe direct GPIO load")
    result = VerificationService().verify(replace(plan, connections=plan.connections + (unsafe,)))
    assert not result.accepted
    assert any(item.check == "direct-pump-gpio" and item.severity == "critical" for item in result.findings)


def test_identity_net_ids_and_wire_routes_survive_reopen(tmp_path):
    database = tmp_path / "aura.db"
    artifacts = tmp_path / "artifacts"
    app = create_app(storage_mode="sqlite", db_path=database, artifact_dir=artifacts)
    with TestClient(app) as client:
        created = client.post("/api/projects", json={"objective": "Build an Arduino Nano controlled tabletop DC fan with adjustable speed.", "planningMode": "deterministic_test"})
        assert created.status_code == 201
        project_id = created.json()["projectId"]
        before_graph = client.get(f"/api/projects/{project_id}/graph").json()
        before_assembly = client.get(f"/api/projects/{project_id}/assembly").json()
    with TestClient(create_app(storage_mode="sqlite", db_path=database, artifact_dir=artifacts)) as client:
        after_graph = client.get(f"/api/projects/{project_id}/graph").json()
        after_assembly = client.get(f"/api/projects/{project_id}/assembly").json()
    identity = lambda graph: sorted((item["id"], item["metadata"].get("parameters", {}).get("component_definition_id")) for item in graph["entities"] if item["kind"] == "component")
    net_ids = lambda graph: sorted(item["id"] for item in graph["entities"] if item["metadata"].get("semantic_type") == "electrical_net")
    assert identity(after_graph) == identity(before_graph)
    assert net_ids(after_graph) == net_ids(before_graph)
    assert after_assembly["wires"] == before_assembly["wires"]


def assert_wire_fidelity(graph, assembly):
    nets = {item.id for item in graph.find(kind=EntityKind.CONNECTION)
            if item.metadata.get("semantic_type") == "electrical_net"}
    connector_positions = {item["interfaceId"]: item["worldPosition"] for item in assembly["connectors"]}
    assert assembly["wires"] and {item["netId"] for item in assembly["wires"]} <= nets
    assert engineering_assembly(graph)["wires"] == assembly["wires"]
    starts_by_net = {}
    for wire in assembly["wires"]:
        assert wire["source"] == "ENGINEERING_GRAPH_NET"
        assert wire["points"][0] in connector_positions.values()
        starts_by_net.setdefault(wire["netId"], set()).add(tuple(wire["points"][0]))
        if len(wire["terminalInterfaceIds"]) == 2:
            assert wire["points"][-1] in connector_positions.values()
    for wire in assembly["wires"]:
        if len(wire["terminalInterfaceIds"]) > 2:
            expected = {tuple(connector_positions[item]) for item in wire["terminalInterfaceIds"]}
            assert starts_by_net[wire["netId"]] == expected
