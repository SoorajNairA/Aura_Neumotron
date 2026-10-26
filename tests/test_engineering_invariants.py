from aura.engineering_graph.electrical import electrical_nets
from aura.engineering_graph.invariants import check_engineering_invariants
import pytest
from dataclasses import replace

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind
from aura.engineering_graph.serialization import graph_from_dict, graph_to_dict
from aura.planner.schemas import ProjectRequest
from aura.planner.service import PlannerService
from aura.verification.service import VerificationService
from aura.workspace.bridge import WorkspaceBridge


def build(objective: str) -> EngineeringGraph:
    plan = PlannerService().plan(ProjectRequest(objective, objective, ("low voltage",)))
    return WorkspaceBridge().commit(EngineeringGraph(plan.entities[0].id), VerificationService().verify(plan))


def test_robotic_arm_has_graph_owned_complete_servo_nets():
    graph = build("make a robotic arm")
    assert electrical_nets(graph)
    assert not check_engineering_invariants(graph)
    terminals = {f'{item["componentId"]}:{item["interfaceId"]}' for net in electrical_nets(graph) for item in net["terminals"]}
    servo_ids = [
        entity.id for entity in graph.find()
        if dict(entity.metadata).get("family") == "servo"
    ]
    assert servo_ids
    for servo in servo_ids:
        assert {f"{servo}:power", f"{servo}:ground", f"{servo}:signal"} <= terminals


def test_servo_lid_uses_same_net_compiler():
    graph = build("make a servo lid mechanism")
    assert electrical_nets(graph)
    assert not check_engineering_invariants(graph)


@pytest.mark.parametrize("objective,family,quantity",[
    ("make two independently controlled fans","fan",2),
    ("make three temperature sensors","temperature_sensor",3),
    ("make three pumps controlled independently","small_dc_pump",3),
    ("make a rover with four independently driven wheels","drive_wheel",4),
])
def test_objective_quantities_survive_normalization(objective: str, family: str, quantity: int):
    plan=PlannerService().plan(ProjectRequest(objective,objective,("low voltage",)))
    matching=[component for component in plan.components if component.role==family]
    assert len(matching)==quantity
    assert len({component.id for component in matching})==quantity
    assert VerificationService().verify(plan).accepted


def test_graph_deserialization_rejects_unknown_schema_duplicates_cycles_and_bad_dimensions():
    project=EngineeringEntity("project",EntityKind.PROJECT,"Project")
    graph=EngineeringGraph("project",entities={"project":project})
    payload=graph_to_dict(graph)
    payload["schema_version"]="99"
    with pytest.raises(ValueError,match="schema version"): graph_from_dict(payload)
    payload=graph_to_dict(graph);payload["entities"].append(dict(payload["entities"][0]))
    with pytest.raises(ValueError,match="duplicate entity"): graph_from_dict(payload)
    a=EngineeringEntity("a",EntityKind.COMPONENT,"A","b")
    b=EngineeringEntity("b",EntityKind.COMPONENT,"B","a")
    with pytest.raises(ValueError,match="parent cycle"): EngineeringGraph("project",entities={"project":project,"a":a,"b":b}).validate()
    bad=EngineeringEntity("bad",EntityKind.COMPONENT,"Bad","project",{"dimensions":{"width":{"value":float("inf"),"unit":"mm"}}})
    with pytest.raises(ValueError,match="NaN or Infinity"): EngineeringGraph("project",entities={"project":project,"bad":bad}).validate()


def test_component_definition_version_mismatch_is_detected():
    objective="make a temperature-controlled fan"
    plan=PlannerService().plan(ProjectRequest(objective,objective,("low voltage",)))
    index=next(i for i,c in enumerate(plan.components) if c.parameters.get("component_definition_id"))
    components=list(plan.components);parameters=dict(components[index].parameters);parameters["component_definition_version"]="catalogue-obsolete"
    components[index]=replace(components[index],parameters=parameters)
    result=VerificationService().verify(replace(plan,components=tuple(components)))
    assert not result.accepted
    assert any(f.check=="component-definition-version" and f.state.value=="failed" for f in result.findings)


def test_requested_motor_turntable_does_not_inherit_a_phantom_default_servo():
    objective="Build a rotating camera turntable"
    plan=PlannerService().plan(ProjectRequest(objective,objective,("Use low voltage",),components=("controller","motor","motor driver","camera platform","mounting plate","power source")))
    roles=[component.role for component in plan.components]
    assert "small_dc_motor" in roles and "servo" not in roles
    assert VerificationService().verify(plan).accepted
    mechanical=[connection for connection in plan.connections if connection.connection_type=="mechanical"]
    assert any(connection.source_id=="component-motor" and connection.target_id=="component-camera-platform" for connection in mechanical)


def _with_dimensions_in_cm(graph: EngineeringGraph) -> EngineeringGraph:
    entities = dict(graph.entities)
    for entity in graph.find(kind=EntityKind.COMPONENT):
        dims = {key: {"value": value["value"] / 10, "unit": "cm"} for key, value in entity.metadata["dimensions"].items()}
        entities[entity.id] = replace(entity, metadata=entity.metadata | {"dimensions": dims})
    converted = replace(graph, entities=entities)
    converted.validate()
    return converted


def test_centimetre_dimensions_render_like_equivalent_millimetres():
    from aura.workspace.assembly import engineering_assembly
    from aura.workspace.representation_service import representation_specs
    graph = build("Build a temperature controlled fan with a servo lid.")
    in_cm = _with_dimensions_in_cm(graph)
    mechanical = lambda value: {spec.semantic_ids: spec.payload for spec in representation_specs(value) if spec.kind.value == "mechanical_3d"}
    assert mechanical(in_cm) == mechanical(graph)
    assert engineering_assembly(in_cm)["parts"] == engineering_assembly(graph)["parts"]
    assert check_engineering_invariants(in_cm) == check_engineering_invariants(graph)


@pytest.mark.parametrize("dimension", [{"value": None, "unit": "mm"}, {"value": "80", "unit": "mm"}, {"value": 80}, {"value": 80, "unit": "V"}])
def test_invalid_dimension_is_a_clear_validation_error(dimension):
    graph = build("Build a temperature controlled fan.")
    fan = graph.get("component-fan")
    graph.entities[fan.id] = replace(fan, metadata=fan.metadata | {"dimensions": {"width": dimension}})
    with pytest.raises(ValueError, match="component-fan dimension width"):
        graph.validate()
