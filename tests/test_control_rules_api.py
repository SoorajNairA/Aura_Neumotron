import json

from fastapi.testclient import TestClient

from aura.firmware.io import RULES_SCHEMA
from aura.infrastructure.llm.provider import ModelGenerationResult
from aura.workspace.ideas import TURN_SCHEMA
from aura.workspace.server import create_app

READY = {"slots": [{"slot": "function", "value": "water my plant when the soil moisture is low using a pump", "source": "user", "status": "agreed", "tradeoff": ""},
                   {"slot": "power", "value": "USB 5 V", "source": "user", "status": "agreed", "tradeoff": ""}],
         "questions": [], "families": ["soil_moisture_sensor", "small_dc_pump"],
         "scope": {"status": "IN_SCOPE", "reasons": [], "alternative": None}, "reply": "Ready to propose."}
LIVE_RULE = {"input": "soil_1", "when": "below", "threshold": 25, "release": 50, "output": "pump_1", "onValue": True, "offValue": False, "minOnSeconds": 3}


class Provider:
    def __init__(self, rules):
        self.rules, self.rule_prompts = rules, []

    def generate_structured(self, messages, *, system_prompt=None, max_tokens=1200, response_schema=None):
        if response_schema == TURN_SCHEMA: return ModelGenerationResult(json.dumps(READY))
        assert response_schema == RULES_SCHEMA
        self.rule_prompts.append(system_prompt)
        return ModelGenerationResult(json.dumps(self.rules))

    def get_diagnostics(self): return {"backend": "fake"}


def client_for(provider, tmp_path):
    return TestClient(create_app(provider=provider, storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a"))


def propose(client):
    session_id = client.post("/api/ideas", json={"idea": "water my plant", "planningMode": "deterministic_test"}).json()["sessionId"]
    response = client.post(f"/api/ideas/{session_id}/proposal")
    assert response.status_code == 200, response.text
    return session_id, response.json()


def test_live_rules_on_card_and_in_firmware(tmp_path):
    provider = Provider({"rules": [LIVE_RULE], "explanation": "Water below 25 %."})
    with client_for(provider, tmp_path) as client:
        session_id, card = propose(client)
        assert card["controlRules"]["source"] == "live_model" and card["controlRules"]["rules"] == [LIVE_RULE]
        assert {io["id"] for io in card["ios"]} == {"soil_1", "pump_1"}
        assert "soil_1" in provider.rule_prompts[0] and "0–100 %" in provider.rule_prompts[0]
        project_id = client.post(f"/api/ideas/{session_id}/approve", json={"proposalId": card["proposalId"]}).json()["projectId"]
        firmware = client.get(f"/api/projects/{project_id}/firmware").json()
        assert firmware["supported"] and firmware["kind"] == "generic" and firmware["rules"] == [LIVE_RULE]
        assert firmware["rulesSource"] == "live_model" and firmware["droppedRules"] == [] and "analogRead(SOIL_1_PIN)" in firmware["source"]


def test_invalid_model_rules_fall_back_to_labelled_default(tmp_path):
    with client_for(Provider({"rules": [LIVE_RULE | {"output": "valve_9"}], "explanation": "x"}), tmp_path) as client:
        _, card = propose(client)
        rules = card["controlRules"]
        assert rules["source"] == "default" and "UNKNOWN_IO" in rules["reason"]
        assert rules["rules"][0]["input"] == "soil_1" and rules["rules"][0]["threshold"] == 30


def test_rules_for_missing_io_are_dropped_and_listed(tmp_path):
    with client_for(Provider({"rules": [LIVE_RULE], "explanation": "x"}), tmp_path) as client:
        session_id, card = propose(client)
        project_id = client.post(f"/api/ideas/{session_id}/approve", json={"proposalId": card["proposalId"]}).json()["projectId"]
        stale = LIVE_RULE | {"output": "led_1"}
        client.app.state.workspace.repository.save_control_rules(project_id, {"rules": [LIVE_RULE, stale], "source": "live_model", "explanation": "x"})
        firmware = client.get(f"/api/projects/{project_id}/firmware").json()
        assert firmware["rules"] == [LIVE_RULE] and firmware["droppedRules"] == [stale]
        assert client.post(f"/api/projects/{project_id}/firmware/compile").status_code == 200


def test_fan_demo_firmware_kind(tmp_path):
    with client_for(None, tmp_path) as client:
        project_id = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()["projectId"]
        assert client.get(f"/api/projects/{project_id}/firmware").json()["kind"] == "fan"


def test_project_without_stored_rules_uses_defaults(tmp_path):
    with client_for(None, tmp_path) as client:
        project_id = client.post("/api/projects", json={"objective": "Build an automatic plant watering system with a soil moisture sensor and a pump", "planningMode": "deterministic_test"}).json()["projectId"]
        firmware = client.get(f"/api/projects/{project_id}/firmware").json()
        assert firmware["kind"] == "generic" and firmware["rulesSource"] == "default" and firmware["rules"][0]["output"] == "pump_1"
