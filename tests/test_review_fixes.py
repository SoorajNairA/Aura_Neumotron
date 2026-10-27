import json

from fastapi.testclient import TestClient

from aura.engineering_graph.serialization import graph_from_dict
from aura.firmware.generic import generate_generic_sketch
from aura.firmware.io import default_rules, io_points
from aura.infrastructure.llm.provider import ModelGenerationResult
from aura.workspace.ideas import TURN_SCHEMA, wants_breadboard
from aura.workspace.server import create_app

FAN = "Build a temperature-controlled desk fan"
PLANT = "Build an automatic plant watering system with a soil moisture sensor and a pump"


def client_for(tmp_path, provider=None):
    return TestClient(create_app(provider=provider, storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a"))


def graph_dict(client, objective):
    project_id = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()["projectId"]
    return project_id, client.get(f"/api/projects/{project_id}/graph").json()


def test_relay_switching_a_fan_is_named_for_its_load_and_motor_family_is_known(tmp_path):
    with client_for(tmp_path) as client:
        _, data = graph_dict(client, FAN)
    driver = next(e for e in data["entities"] if e["id"] == "component-driver")
    driver["metadata"]["parameters"]["component_definition_id"] = "relay-module-5v"
    ios = {io.id: io for io in io_points(graph_from_dict(data))}
    assert "fan_1" in ios and ios["fan_1"].definition_id == "relay-module-5v"
    from aura.firmware.io import LOAD_SLUGS
    assert LOAD_SLUGS["small_dc_motor"] == "motor"


def test_relay_level_is_an_explicit_assumption_and_light_rail_is_not_a_fault(tmp_path):
    with client_for(tmp_path) as client:
        project_id, _ = graph_dict(client, FAN)
        for ids in (["relay-module-5v"], ["photoresistor-module"]):
            base = len(client.get(f"/api/projects/{project_id}/revisions").json())
            proposal = client.post(f"/api/projects/{project_id}/component-proposals", json={"baseRevision": base, "componentDefinitionIds": ids}).json()
            assert client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit").status_code == 200
        graph = graph_from_dict(client.get(f"/api/projects/{project_id}/graph").json())
    source = generate_generic_sketch(graph, default_rules(io_points(graph))).source
    assert "#define RELAY_1_ON HIGH  // assumption" in source and "RELAY_1_ON : !RELAY_1_ON" in source
    assert "S.light_1_ok = true;" in source and "S.soil" not in source


def test_breadboard_check_reads_plurals_boxes_and_the_whole_conversation():
    slots = {"function": {"value": "water my plant"}}
    for text in ("two PCBs", "IP65 enclosures", "a printed circuit board", "a 3D printed box"):
        assert not wants_breadboard({"function": {"value": f"water my plant on {text}"}}, ["soil_moisture_sensor"])
    assert not wants_breadboard(slots, ["soil_moisture_sensor"], ["water my plant", "put it on a custom PCB please"])
    assert wants_breadboard(slots, ["soil_moisture_sensor"], ["water my plant"])


READY_FAN = {"slots": [{"slot": "function", "value": "switch a fan on when the room is hot", "source": "user", "status": "agreed", "tradeoff": ""},
                       {"slot": "power", "value": "USB 5 V", "source": "user", "status": "agreed", "tradeoff": ""}],
             "questions": [], "families": ["temperature_sensor", "fan"], "scope": {"status": "IN_SCOPE", "reasons": [], "alternative": None}, "reply": "Ready."}


class Provider:
    def __init__(self): self.rule_calls = 0
    def generate_structured(self, messages, *, system_prompt=None, max_tokens=1200, response_schema=None):
        if response_schema == TURN_SCHEMA: return ModelGenerationResult(json.dumps(READY_FAN))
        self.rule_calls += 1
        return ModelGenerationResult(json.dumps({"rules": [], "explanation": "x"}))
    def get_diagnostics(self): return {"backend": "fake"}


def test_fan_workflow_card_does_not_claim_rule_list_firmware(tmp_path):
    provider = Provider()
    with client_for(tmp_path, provider) as client:
        session_id = client.post("/api/ideas", json={"idea": "a fan for a hot room", "planningMode": "deterministic_test"}).json()["sessionId"]
        card = client.post(f"/api/ideas/{session_id}/proposal").json()
    assert card["controlRules"]["source"] == "fan_workflow" and card["controlRules"]["rules"] == [] and provider.rule_calls == 0


def test_rules_bound_to_a_replaced_part_are_dropped(tmp_path):
    with client_for(tmp_path) as client:
        project_id, _ = graph_dict(client, PLANT)
        rule = {"input": "soil_1", "when": "below", "threshold": 30, "release": 45, "output": "pump_1", "onValue": True, "offValue": False, "minOnSeconds": None}
        client.app.state.workspace.repository.save_control_rules(project_id, {"rules": [rule], "source": "live_model", "explanation": "x",
                                                                               "bindings": {"soil_1": "component-old-sensor", "pump_1": "component-driver"}})
        firmware = client.get(f"/api/projects/{project_id}/firmware").json()
    assert firmware["rules"] == [] and firmware["droppedRules"] == [rule]
