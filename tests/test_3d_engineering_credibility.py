from __future__ import annotations

import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.planner.schemas import ConnectionSpec, ProjectRequest
from aura.planner.service import PlannerService
from aura.verification.service import VerificationService
from aura.workspace.assembly import _representation_parameters, engineering_assembly
from aura.workspace.bridge import WorkspaceBridge
from aura.workspace.representation_service import CircuitGeneratorAdapter, representation_specs
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


def test_fan_schematic_preserves_semantic_labels_without_undefined_values():
    _, _, _, _, circuit = compile_project(
        "Build an Arduino Nano controlled tabletop DC fan with adjustable speed."
    )
    result = CircuitGeneratorAdapter().generate(circuit)
    payload = json.loads(result.artifact)
    schematic = [item for item in payload if item.get("type") == "schematic_component"]
    labels = {item.get("aura_display_name") for item in schematic}
    assert {"Arduino Nano", "Logic-level N-channel MOSFET switch", "Desk fan", "D1 Flyback Diode", "Low-voltage power source"} <= labels
    assert "undefined" not in json.dumps(payload).lower()
    assert circuit.payload["fidelity"] == {"portsComplete": True, "netsComplete": True}


def test_remote_car_has_two_driven_wheels_and_shared_motor_driver():
    _, _, graph, assembly, _ = compile_project("Build a remote-controlled two-wheel car with wireless control.")
    components = graph.find(kind=EntityKind.COMPONENT)
    assert len([item for item in components if item.metadata.get("family") == "small_dc_motor"]) == 2
    assert len([item for item in components if item.metadata.get("family") == "drive_wheel"]) == 2
    assert any(item.metadata.get("family") == "motor_driver" for item in components)
    assert any(item.metadata.get("family") == "wireless_module" for item in components)
    assert not assembly["unresolvedPrimaryMechanism"]
    assert_wire_fidelity(graph, assembly)


def test_four_wheel_mobile_system_is_compactly_assembled_on_its_chassis():
    objective = "Build a remote-controlled four-wheel rover with a microcontroller, motor driver, battery, and DC gear motors."
    _, _, graph, assembly, _ = compile_project(objective)
    parts = assembly["parts"]
    wheels = [item for item in parts if item["family"] == "drive_wheel"]
    motors = [item for item in parts if item["family"] == "small_dc_motor"]
    chassis = next(item for item in parts if item["family"] == "mounting_plate")
    electronics = [item for item in parts if item["family"] in {"microcontroller_board", "motor_driver", "low_voltage_power_source", "wireless_module"}]
    assert len(wheels) == len(motors) == 4
    assert all({"rounded_tire", "rim", "hub", "axle_bore", "bounded_tread"} <= set(item["representationFeatures"]) for item in wheels)
    for wheel in wheels:
        parameters = wheel["representationParameters"]
        assert parameters["outerDiameter"] == max(wheel["dimensions"][:2])
        assert 0 < parameters["axleBore"] < parameters["hubDiameter"] < parameters["rimDiameter"] < parameters["outerDiameter"]
        assert 0 < parameters["treadDepth"] < parameters["tireWidth"]
    assert len([item for item in electronics if item["family"] == "motor_driver"]) == 1
    assert len({round(item["assembledTransform"]["position"][0]) for item in wheels}) == 2
    assert len({round(item["assembledTransform"]["position"][1]) for item in wheels}) == 2
    assert all(abs(item["assembledTransform"]["position"][0] - chassis["assembledTransform"]["position"][0]) <= chassis["dimensions"][0] / 2 for item in electronics)
    assert all(abs(item["assembledTransform"]["position"][1] - chassis["assembledTransform"]["position"][1]) <= chassis["dimensions"][1] / 2 for item in electronics)
    assert all(item["mountSource"].startswith("semantic_support:") for item in electronics)
    assert all(item["assembledTransform"] != item["explodedTransform"] for item in wheels + motors + electronics)
    assert not assembly["unresolvedPrimaryMechanism"]
    assert_wire_fidelity(graph, assembly)


def test_live_style_solar_rc_car_restores_objective_components_and_one_chassis_layout():
    request = ProjectRequest(
        "Solar-Powered RC Rover",
        "make a solar powered rc car",
        ("Use low-voltage power",),
        components=(
            "microcontroller_board", "small_dc_motor", "motor_driver",
            "low_voltage_power_source", "enclosure", "mounting_plate",
            "diode", "resistor",
        ),
    )
    plan = PlannerService().plan(request)
    verification = VerificationService().verify(plan)
    assert verification.accepted
    graph = WorkspaceBridge().commit(EngineeringGraph(plan.entities[0].id), verification)
    assembly = engineering_assembly(graph)
    parts = assembly["parts"]

    wheels = [item for item in parts if item["family"] == "drive_wheel"]
    motors = [item for item in parts if item["family"] == "small_dc_motor"]
    chassis = [item for item in parts if item["family"] == "mounting_plate"]
    solar_panel = next(item for item in parts if "energy_collection" in item["functionalRoles"])

    assert len(wheels) == len(motors) == 4
    assert len(chassis) == 1
    assert any(item["family"] == "wireless_module" for item in parts)
    assert all(item["family"] != "enclosure" for item in parts)
    assert solar_panel["label"] == "Solar panel"
    assert solar_panel["mechanicalParents"] == [chassis[0]["semanticId"]]
    assert solar_panel["transformSource"] == "MATE_SOLVED"
    assert assembly["transformSourceCounts"]["FIXED_ROOT"] == 1
    assert not assembly["unresolvedPrimaryMechanism"]
    assert assembly["visualConnectivity"]["allMateOriginsWithinTolerance"]
    assert not assembly["visualConnectivity"]["severeIntersections"]


def test_explicit_solar_panel_wording_does_not_require_a_moving_vehicle_panel():
    request = ProjectRequest(
        "Solar car",
        "make a solar panel powered rc car",
        ("Use low-voltage power",),
    )
    verification = VerificationService().verify(PlannerService().plan(request))
    assert verification.accepted, [
        (item.check, item.message) for item in verification.findings if item.severity == "critical"
    ]


def test_explicit_two_wheel_vehicle_count_caps_conflicting_planner_components():
    request = ProjectRequest(
        "Two-wheel solar car",
        "make a two-wheel solar powered rc car",
        ("Use low-voltage power",),
        components=(
            "drive wheel", "drive wheel", "drive wheel", "drive wheel",
            "small dc motor", "small dc motor", "small dc motor", "small dc motor",
            "mounting plate", "structural support",
        ),
    )
    plan = PlannerService().plan(request)
    assert len([item for item in plan.components if item.role == "drive_wheel"]) == 2
    assert len([item for item in plan.components if item.role == "small_dc_motor"]) == 2
    assert len([item for item in plan.components if item.role == "mounting_plate"]) == 1
    trace = dict(plan.entities[0].metadata)["plannerIntentTrace"]
    assert any(item["resolutionQuality"] == "UNRESOLVED" and "exceeds" in item["reason"] for item in trace)


def test_generated_project_name_cannot_override_unspecified_four_wheel_car_default():
    request = ProjectRequest(
        "Two-wheel solar car",
        "make a solar powered rc car",
        ("Use low-voltage power",),
    )
    plan = PlannerService().plan(request)
    assert len([item for item in plan.components if item.role == "drive_wheel"]) == 4
    assert len([item for item in plan.components if item.role == "small_dc_motor"]) == 4


def test_unspecified_car_caps_excess_planner_wheels_motors_and_structures():
    request = ProjectRequest(
        "Solar car",
        "make a solar powered rc car with a protective enclosure",
        ("Use low-voltage power",),
        components=(
            *("drive wheel",) * 6,
            *("small dc motor",) * 6,
            "mounting plate", "structural support",
            "enclosure", "protective housing",
            "solar panel", "photovoltaic panel",
        ),
    )
    plan = PlannerService().plan(request)
    verification = VerificationService().verify(plan)
    assert verification.accepted
    graph = WorkspaceBridge().commit(EngineeringGraph(plan.entities[0].id), verification)
    assembly = engineering_assembly(graph)
    assert len([item for item in assembly["parts"] if item["family"] == "drive_wheel"]) == 4
    assert len([item for item in assembly["parts"] if item["family"] == "small_dc_motor"]) == 4
    assert len([item for item in assembly["parts"] if item["family"] == "mounting_plate"]) == 1
    assert len([item for item in assembly["parts"] if item["family"] == "enclosure"]) == 1
    assert len([item for item in assembly["parts"] if "energy_collection" in item["functionalRoles"]]) == 1
    assert assembly["transformSourceCounts"]["FIXED_ROOT"] == 1
    assert not assembly["visualConnectivity"]["severeIntersections"]


def test_explicit_vehicle_enclosure_is_mated_to_the_single_chassis_root():
    request = ProjectRequest(
        "Enclosed solar car",
        "make a solar powered rc car with a protective enclosure",
        ("Use low-voltage power",),
    )
    plan = PlannerService().plan(request)
    verification = VerificationService().verify(plan)
    assert verification.accepted
    graph = WorkspaceBridge().commit(EngineeringGraph(plan.entities[0].id), verification)
    assembly = engineering_assembly(graph)
    enclosure = next(item for item in assembly["parts"] if item["family"] == "enclosure")
    chassis = next(item for item in assembly["parts"] if item["family"] == "mounting_plate")
    assert enclosure["mechanicalParents"] == [chassis["semanticId"]]
    assert assembly["transformSourceCounts"]["FIXED_ROOT"] == 1
    assert not assembly["visualConnectivity"]["severeIntersections"]


def test_rc_servo_planner_label_does_not_invent_remote_control_for_solar_tracker():
    request = ProjectRequest(
        "Solar tracker",
        "design a dual-axis solar tracker",
        ("Use two RC servo motors",),
        components=("RC servo motor", "RC servo motor", "solar panel"),
    )
    plan = PlannerService().plan(request)
    assert all(item.role != "wireless_module" for item in plan.components)
    requirements = dict(plan.entities[0].metadata)["semanticRequirements"]
    assert all(item["key"] != "remote-control-input" for item in requirements)


@pytest.mark.parametrize("label", ("solar panel mounting bracket", "photovoltaic charge controller"))
def test_compound_photovoltaic_labels_are_not_misclassified_as_panels(label):
    resolution = PlannerService._resolve_component_intent(label, "build a battery powered monitor")
    assert resolution["normalizedFamily"] != "panel"


@pytest.mark.parametrize("dimensions", ((36.0, 36.0, 10.0), (64.0, 64.0, 18.0), (120.0, 120.0, 34.0)))
def test_drive_wheel_representation_parameters_scale_with_part_dimensions(dimensions):
    parameters = _representation_parameters("drive_wheel", dimensions)
    assert parameters["outerDiameter"] == dimensions[0]
    assert parameters["tireWidth"] == dimensions[2]
    assert parameters["rimDiameter"] == pytest.approx(dimensions[0] * 0.58)
    assert parameters["hubDiameter"] == pytest.approx(dimensions[0] * 0.21)
    assert parameters["axleBore"] == pytest.approx(dimensions[0] * 0.08)
    assert parameters["treadDepth"] == pytest.approx(max(1.4, dimensions[0] * 0.026))


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


def test_generated_schematic_renders_real_hardware_name():
    circuit = compile_project("Build a temperature monitor. Use an Arduino Nano.")[4]
    artifact = json.loads(CircuitGeneratorAdapter().generate(circuit).artifact)
    controller = next(item for item in artifact if item.get("type") == "source_component" and item.get("aura_reference") == "U1")
    assert controller["name"] == "U1 Arduino Nano"
    assert controller["display_name"] == "Arduino Nano"


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
