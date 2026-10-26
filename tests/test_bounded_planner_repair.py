from __future__ import annotations

from dataclasses import replace
import json

from fastapi.testclient import TestClient

from aura.planner.live import PlanningOutcome
from aura.planner.schemas import ConnectionSpec, ProjectRequest
from aura.planner.service import PlannerRepairAttempt, PlannerService
from aura.verification.service import VerificationService
from aura.workspace.server import create_app


CAR_OBJECTIVE = "can u make a remote control car using arduino nano"


def _plan(objective: str, components: tuple[str, ...] = ()):  # intentionally creates a candidate before repair
    return PlannerService().plan(ProjectRequest("Repair candidate", objective, ("Use low-voltage control",), components=components))


def _create_from_candidate(candidate, objective: str, operation_id: str):
    app = create_app(storage_mode="memory")
    app.state.workspace.plan = lambda _body: PlanningOutcome(candidate, "deterministic_test")
    return app, TestClient(app), operation_id


def test_remote_car_candidate_is_repaired_once_with_structured_context():
    initial = _plan(CAR_OBJECTIVE)
    broken = replace(initial, connections=tuple(connection for connection in initial.connections if connection.connection_type != "mechanical"))
    assert not VerificationService().verify(broken).accepted
    app, client, operation_id = _create_from_candidate(broken, CAR_OBJECTIVE, "repair-car")
    with client:
        response = client.post("/api/projects", json={"objective": CAR_OBJECTIVE, "planningMode": "deterministic_test", "operationId": operation_id})
        assert response.status_code == 201, response.text
        project = response.json()
        assert project["status"] == "ready_with_limitations"
        graph = client.get(f"/api/projects/{project['projectId']}/graph").json()
        families = {entity["metadata"].get("family") for entity in graph["entities"] if entity["kind"] == "component"}
        assert {"microcontroller_board", "motor_driver", "small_dc_motor", "drive_wheel", "mounting_plate"} <= families
        assembly = client.get(f"/api/projects/{project['projectId']}/assembly").json()
        assert any("motor:shaft" in mate["from"] and "drive-wheel" in mate["to"] for mate in assembly["relationships"])
        provenance = client.get(f"/api/projects/{project['projectId']}/provenance").json()["planner"]["repair"]
        assert provenance["repairAttempted"] and provenance["repairSucceeded"]
        assert len(provenance["verificationFindingsBefore"]) == 1 and not provenance["verificationFindingsAfter"]
        assert provenance["repairContext"]["criticalFindings"][0]["code"] == "MECH_301"
        assert provenance["repairContext"]["relevantComponentInterfaces"][0]["family"] == "small_dc_motor"
        assert client.post("/api/projects", json={"objective": CAR_OBJECTIVE, "planningMode": "deterministic_test", "operationId": operation_id}).json()["projectId"] == project["projectId"]
    app.state.workspace.repository.close()


def test_servo_missing_power_candidate_is_repaired():
    objective = "Build a small servo lid mechanism"
    initial = _plan(objective)
    broken = replace(initial, connections=tuple(connection for connection in initial.connections if not (connection.target_id == "component-servo" and connection.connection_type in {"power", "ground"})))
    assert not VerificationService().verify(broken).accepted
    app, client, _ = _create_from_candidate(broken, objective, "repair-servo-power")
    with client:
        project = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()
        assert project["status"] in {"ready", "ready_with_limitations"}
        repair = client.get(f"/api/projects/{project['projectId']}/provenance").json()["planner"]["repair"]
        assert repair["repairSucceeded"] and repair["verificationFindingsBefore"]
    app.state.workspace.repository.close()


def test_direct_fan_gpio_candidate_is_repaired_through_driver_stage():
    objective = "Build a low-voltage fan controller"
    initial = _plan(objective)
    direct = ConnectionSpec("connection-controller-fan-control", "component-controller", "component-fan", "signal-1", "signal", "control", "Unsafe direct GPIO fan control.")
    broken = replace(initial, connections=tuple(connection for connection in initial.connections if connection.source_id != "component-driver" and connection.target_id != "component-driver") + (direct,))
    assert not VerificationService().verify(broken).accepted
    app, client, _ = _create_from_candidate(broken, objective, "repair-fan")
    with client:
        project = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()
        assert project["status"] in {"ready", "ready_with_limitations"}
        graph = client.get(f"/api/projects/{project['projectId']}/graph").json()
        connections = [entity["metadata"] for entity in graph["entities"] if entity["kind"] == "connection" and entity["metadata"].get("connection_type") == "switched-power"]
        assert any(item["target_id"] == "component-fan" and item["source_id"] != "component-controller" for item in connections)
    app.state.workspace.repository.close()


def test_disconnected_servo_candidate_is_repaired():
    objective = "Build a small servo lid mechanism"
    initial = _plan(objective)
    broken = replace(initial, connections=tuple(connection for connection in initial.connections if connection.connection_type != "mechanical"))
    assert not VerificationService().verify(broken).accepted
    app, client, _ = _create_from_candidate(broken, objective, "repair-servo-mechanical")
    with client:
        project = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()
        assert project["status"] in {"ready", "ready_with_limitations"}
        assert client.get(f"/api/projects/{project['projectId']}/assembly").json()["relationships"]
    app.state.workspace.repository.close()


def test_unrepairable_candidate_persists_safe_build_incomplete(monkeypatch):
    objective = "Build a low-voltage fan controller"
    initial = _plan(objective)
    direct = ConnectionSpec("connection-controller-fan-control", "component-controller", "component-fan", "signal-1", "signal", "control", "Unsafe direct GPIO fan control.")
    broken = replace(initial, connections=tuple(connection for connection in initial.connections if connection.source_id != "component-driver" and connection.target_id != "component-driver") + (direct,))
    calls = 0
    def no_repair(_self, plan, _verification):
        nonlocal calls
        calls += 1
        return PlannerRepairAttempt(plan, {"test": "unrepairable"}, {"repairAttempted": True, "repairProvider": "test"})
    monkeypatch.setattr(PlannerService, "repair", no_repair)
    app, client, _ = _create_from_candidate(broken, objective, "repair-fails")
    with client:
        response = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"})
        assert response.status_code == 201
        project = response.json()
        assert calls == 1 and project["status"] == "build_incomplete"
        assert project["generationMessage"] == "AURA couldn't resolve this engineering architecture reliably."
        assert all("connection-" not in message and "GPIO" not in message for message in project["userIssues"])
        assert not project["representations"]
        verification = client.get(f"/api/projects/{project['projectId']}/verification").json()
        assert any(item.get("userMessage") == "Motor requires a driver between the controller and motor." for item in verification["findings"])
    app.state.workspace.repository.close()


def test_live_repair_reuses_the_provider_with_the_structured_context():
    initial = _plan(CAR_OBJECTIVE)
    broken = replace(initial, connections=tuple(connection for connection in initial.connections if connection.connection_type != "mechanical"))

    class Provider:
        def __init__(self): self.prompts=[]
        def generate(self, messages, **_kwargs):
            self.prompts.append(messages[0]["content"])
            return json.dumps({"projectName":"Remote car","objective":CAR_OBJECTIVE,"requirements":["Use low-voltage control"],"assumptions":["Conceptual fit"],"components":["Arduino Nano","motor driver","DC motor","drive wheel","chassis","wireless receiver","power supply"]})
        def stream_generate(self, *_args, **_kwargs): return iter(())
        def is_available(self): return True
        def get_diagnostics(self): return {"backend":"test"}

    provider=Provider()
    app, client, _ = _create_from_candidate(broken, CAR_OBJECTIVE, "repair-live")
    app.state.workspace.provider=provider
    with client:
        # Mark the injected candidate as live so the server must invoke the same provider for repair.
        app.state.workspace.plan = lambda _body: PlanningOutcome(broken, "live_model")
        response=client.post("/api/projects",json={"objective":CAR_OBJECTIVE,"planningMode":"live_model"})
        assert response.status_code == 201 and response.json()["status"] in {"ready","ready_with_limitations"}
        assert len(provider.prompts)==1 and "Repair context:" in provider.prompts[0] and "MECH_301" in provider.prompts[0]
        repair=client.get(f"/api/projects/{response.json()['projectId']}/provenance").json()["planner"]["repair"]
        assert repair["repairProvider"] == "live_model" and repair["repairSucceeded"]
    app.state.workspace.repository.close()


def test_structured_planner_text_fields_are_bounded_against_context_echo():
    # Nemotron sometimes copies the repair context graph into a text field until it hits max_tokens.
    import pytest
    from pydantic import ValidationError
    from aura.planner.live import StructuredPlannerResponse
    echoed = json.dumps({"components": [{"family": "articulated_link", "id": f"component-{index}"} for index in range(40)]})
    with pytest.raises(ValidationError):
        StructuredPlannerResponse(projectName="Arm", objective="Make a robotic arm", requirements=[echoed], assumptions=[], components=["servo", "controller", "power"])
    schema = StructuredPlannerResponse.model_json_schema()["properties"]
    assert all(schema[field]["items"].get("maxLength") for field in ("requirements", "assumptions", "components"))


def test_live_planner_gives_structured_output_enough_token_headroom():
    from aura.infrastructure.llm.provider import ModelGenerationResult
    from aura.planner.live import LivePlanner
    seen = []

    class Recorder:
        def generate_structured(self, messages, *, system_prompt=None, max_tokens=0, response_schema=None):
            seen.append(max_tokens)
            return ModelGenerationResult(json.dumps({"projectName": "Arm", "objective": "Make a robotic arm", "requirements": ["Move"], "assumptions": [], "components": ["microcontroller board", "servo", "low-voltage power supply"]}), 1, 1, 2, "test", {})

    LivePlanner(Recorder()).plan(ProjectRequest("Arm", "Make a robotic arm", ("Move",)))
    # Valid replies were observed up to ~1050 tokens; 1200 truncated them.
    assert seen and min(seen) >= 2400


def test_live_prompts_ask_for_only_needed_component_families():
    # Without this, Nemotron copied the whole capability manifest (a robotic arm got a reservoir, tube and lid).
    from aura.planner.live import LivePlanner
    request = ProjectRequest("Arm", "Make a robotic arm", ("Move",))
    for prompt in (LivePlanner._prompt(request, ""), LivePlanner._repair_prompt(request, {})):
        assert "only the component families this objective physically needs" in prompt


def test_fan_objective_drops_redundant_planner_motor_and_motor_driver():
    # Live Nemotron listed a bare DC motor and an H-bridge beside the fan; the fan family already includes its motor.
    plan = _plan("Design a temperature-controlled desk fan",
                 ("microcontroller_board", "temperature_sensor", "fan", "small_dc_motor", "motor_driver", "mosfet_driver", "low_voltage_power_source", "enclosure"))
    families = [component.role for component in plan.components]
    assert "fan" in families and "mosfet_driver" in families
    assert "small_dc_motor" not in families and "motor_driver" not in families
    assert VerificationService().verify(plan).accepted


def test_fan_objective_keeps_an_explicitly_requested_motor():
    plan = _plan("Design a desk fan driven by a separate dc motor through a belt", ("fan", "small_dc_motor", "motor_driver"))
    assert "small_dc_motor" in [component.role for component in plan.components]
