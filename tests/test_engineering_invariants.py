from aura.engineering_graph.electrical import electrical_nets
from aura.engineering_graph.invariants import check_engineering_invariants
from aura.engineering_graph.model import EngineeringGraph
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
