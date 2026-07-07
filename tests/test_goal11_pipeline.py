from fastapi.testclient import TestClient
from aura.capabilities import CapabilityStatus, classify_objective
from aura.engineering_graph.model import EntityKind
from aura.planner.live import LivePlanner
from aura.planner.schemas import ProjectRequest
from aura.workspace.server import create_app

class Provider:
    def generate_structured(self,*_args,**_kwargs):
        return '{"projectName":"Servo Arm","objective":"make a robotic arm","requirements":["Use low-voltage servo actuation"],"assumptions":["Payload remains conceptual"],"components":["controller","shoulder servo","arm links"]}'

def test_robotic_arm_is_bounded_nonempty_and_visually_structured():
    assert classify_objective("make a robotic arm")["status"]==CapabilityStatus.SUPPORTED_WITH_LIMITATIONS.value
    with TestClient(create_app(storage_mode="memory")) as client:
        response=client.post("/api/projects",json={"objective":"make a robotic arm","planningMode":"deterministic_test"})
        assert response.status_code==201,response.text
        project=response.json();graph=client.get(f'/api/projects/{project["projectId"]}/graph').json()
        components=[x for x in graph["entities"] if x["kind"]==EntityKind.COMPONENT.value]
        assert {"component-base","component-shoulder-servo","component-upper-arm","component-elbow-servo","component-forearm","component-end-effector"}<={x["id"] for x in components}
        assembly=client.get(f'/api/projects/{project["projectId"]}/assembly').json()
        assert assembly["layoutStatus"]=="conceptual mechanical assembly" and len(assembly["parts"])>=8

def test_live_structured_components_reach_planner_boundary():
    request=ProjectRequest("Bounded System","Create a low voltage controller mechanism",("Operate safely",))
    outcome=LivePlanner(Provider()).plan(request)
    assert outcome.mode=="live_model"
    assert len([x for x in outcome.plan.entities if x.kind is EntityKind.COMPONENT])==3

def test_supported_ready_project_can_never_have_zero_components():
    with TestClient(create_app(storage_mode="memory")) as client:
        response=client.post("/api/projects",json={"objective":"Create a low voltage robotic controller","planningMode":"deterministic_test"})
        assert response.status_code==422
        assert "component" in response.text.lower()
